"""
Módulo 08: Asignación con transacciones
======================================

Procesa órdenes pendientes y las asigna a depósitos usando transacciones seguras.
"""

import logging
import re
import sys
import time
import requests
import os
import importlib.util
from typing import Optional, List, Dict, Tuple
import json
from sqlalchemy import text

# Cargar módulos con nombre de archivo que comienzan con dígitos usando importlib
BASE_DIR = os.path.dirname(__file__)
# Asegurar que el paquete 'modules' sea importable desde los submódulos cargados dinámicamente
PARENT_DIR = os.path.dirname(BASE_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

def _load_module(filename: str, alias: str):
    path = os.path.join(BASE_DIR, filename)
    spec = importlib.util.spec_from_file_location(alias, path)
    if not spec or not spec.loader:
        raise ImportError(f"No se pudo cargar {filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_mod_filter_ready = _load_module('06_filter_ready.py', 'modules.06_filter_ready')
get_pending_ready = _mod_filter_ready.get_pending_ready

# Deshabilitado: el cliente de PIPELINE_6 importa config desde otra ruta y provoca 400/401
get_stock_by_sku = None

# Fallback al módulo 07 si por alguna razón no se puede cargar el de v6
_mod_dragon_api = _load_module('07_dragon_api.py', 'modules.07_dragon_api')
get_stock_per_deposit = getattr(_mod_dragon_api, 'get_stock_per_deposit', None)
get_last_method = getattr(_mod_dragon_api, 'get_last_method', lambda: 'API')

_mod_assigner = _load_module('07_assigner.py', 'modules.07_assigner')
choose_winner = _mod_assigner.choose_winner

# Config con clusters y flags de multiventa
_mod_cfg = _load_module('config.py', 'modules.config')

# Para base local y modelos usamos los alias sin prefijo numérico si existen
_mod_local_db = _load_module('03_local_db.py', 'modules.03_local_db')
SessionLocal = _mod_local_db.SessionLocal

_mod_notifier = _load_module('11_notifier.py', 'modules.11_notifier')
alert_stock_zero = _mod_notifier.alert_stock_zero

_mod_move = _load_module('09_dragon_movement.py', 'modules.09_dragon_movement')
move_stock_woo_to_woo = _mod_move.move_stock_woo_to_woo

# Publicador de notas ML (idempotente)
_mod_notes = _load_module('10_note_publisher.py', 'modules.10_note_publisher')
publish_note_upsert = _mod_notes.publish_note_upsert

logger = logging.getLogger(__name__)


def _available(vals: dict) -> int:
    try:
        return int(vals.get('total') or 0) - int(vals.get('reserved') or 0)
    except Exception:
        return 0


def _cluster_sum(stock: dict, deps: list[str]) -> int:
    tot = 0
    for d in deps:
        v = stock.get(d) or {}
        tot += max(_available(v), 0)
    return tot


def _distribute_within_cluster(stock: dict, qty: int, deps: list[str]) -> list[dict]:
    """Greedy: asigna qty dentro de deps por disponible desc."""
    remaining = int(qty or 0)
    dist = []
    # ordenar por disponible desc
    ordered = sorted(deps, key=lambda d: _available(stock.get(d) or {}), reverse=True)
    for d in ordered:
        if remaining <= 0:
            break
        av = max(_available(stock.get(d) or {}), 0)
        if av <= 0:
            continue
        take = min(av, remaining)
        dist.append({"depo": d, "qty": int(take)})
        remaining -= take
    return dist if remaining == 0 else []


def _format_dist_str(dist: list[dict]) -> str:
    # Ej: DEP:2 + MTGBBPS:1
    try:
        parts = [f"{d['depo']}:{int(d['qty'])}" for d in dist if int(d['qty']) > 0]
        return ' + '.join(parts)
    except Exception:
        return ''


def _detect_seller_id(order) -> Optional[int]:
    """Obtiene el user_id de la cuenta ML para esta orden.
    Prioridad: order.seller_id -> ONLY_ML_USER_IDS -> TOKEN_PATH.user_id
    """
    try:
        sid = getattr(order, 'seller_id', None)
        if sid:
            try:
                return int(sid)
            except Exception:
                pass
        # 2) Variable de entorno forzada por Pipeline 10
        env_id = os.getenv('ONLY_ML_USER_IDS')
        if env_id:
            try:
                return int(env_id.strip())
            except Exception:
                pass
        # 3) TOKEN_PATH -> leer user_id del JSON
        tp = os.getenv('TOKEN_PATH')
        if tp and os.path.exists(tp):
            try:
                with open(tp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                uid = data.get('user_id') or data.get('userId') or data.get('seller_id')
                if uid:
                    return int(str(uid))
            except Exception:
                pass
    except Exception:
        pass
    return None


def assign_pending() -> int:
    """
    Asigna depósitos a todas las órdenes pendientes.
    
    Returns:
        int: Número de órdenes procesadas exitosamente
    """
    processed = 0
    pending_orders = get_pending_ready()

    # Agrupar por pack_id y separar en 'packs' reales (>1 ítem) vs 'individuales'
    tmp_groups: Dict[str, List] = {}
    singles: List = []
    for o in pending_orders:
        pid = getattr(o, 'pack_id', None)
        if pid:
            tmp_groups.setdefault(str(pid), []).append(o)
        else:
            singles.append(o)

    packs: Dict[str, List] = {}
    for pid, items in tmp_groups.items():
        if len(items) > 1:
            packs[pid] = items
        else:
            # Grupos de tamaño 1 se procesan como individuales
            singles.extend(items)

    total_units = len(pending_orders)
    logger.info(f"Procesando {total_units} órdenes pendientes (packs={len(packs)}, individuales={len(singles)})")

    # Primero procesar packs multiventa
    for pid, items in packs.items():
        try:
            if len(items) <= 1:
                # Tratar como individual si el pack tiene sólo 1 ítem pendiente
                if assign_single_order(items[0]):
                    processed += 1
                continue
            ok = assign_pack_multiventa(pid, items)
            processed += (len(items) if ok else 0)
        except Exception as e:
            logger.error(f"Error procesando pack {pid}: {e}")
            continue

    # Luego procesar individuales
    for order in singles:
        try:
            if assign_single_order(order):
                processed += 1
        except Exception as e:
            logger.error(f"Error procesando orden {order.order_id}: {e}")
            continue
    
    logger.info(f"Procesadas exitosamente: {processed}/{len(pending_orders)} órdenes")
    return processed


def _get_stock_with_reserves(sku: str) -> dict:
    """Obtiene stock por depósito para un SKU aplicando reservas activas en DB.
    También marca como agotados los depósitos que ya tienen resultante=0.
    """
    if get_stock_per_deposit is None:
        raise RuntimeError('No hay cliente Dragonfish disponible')
    stock = get_stock_per_deposit(sku, timeout=120)
    
    # aplicar reservas de DB para ese SKU y detectar depósitos agotados
    try:
        with SessionLocal() as session:
            # Obtener reservas activas por depósito (todas las órdenes asignadas y no impresas)
            rows = session.execute(
                text(
                    """
                    SELECT deposito_asignado AS depot, SUM(qty) AS qty_res
                    FROM orders_meli WITH (READPAST)
                    WHERE sku = :sku
                      AND asignado_flag = 1
                      AND ISNULL(shipping_subestado, '') NOT IN ('printed','shipped','delivered','canceled')
                      AND ISNULL(shipping_estado, '') NOT IN ('printed','shipped','delivered','canceled')
                    GROUP BY deposito_asignado
                    """
                ),
                {"sku": sku},
            ).fetchall()
            
            # Obtener depósitos ya agotados (resultante <= 0)
            agotados = session.execute(
                text(
                    """
                    SELECT DISTINCT deposito_asignado AS depot
                    FROM orders_meli WITH (READPAST)
                    WHERE sku = :sku
                      AND asignado_flag = 1
                      AND ISNULL(agotamiento_flag, 0) = 1
                      AND ISNULL(resultante, 1) <= 0
                    """
                ),
                {"sku": sku},
            ).fetchall()
            
        # Aplicar reservas (agregado por depósito) normalizando alias BBPS -> MTGBBPS
        for r in rows:
            if r.depot:
                dep = str(r.depot).strip().upper()
                if dep == 'BBPS':
                    dep = 'MTGBBPS'
                vals = stock.get(dep) or {}
                cur = int(vals.get('reserved') or 0)
                stock[dep] = {**vals, 'reserved': cur + int(r.qty_res or 0)}
                
        # Marcar depósitos agotados como no disponibles (normalizando alias)
        for r in agotados:
            if r.depot:
                dep = str(r.depot).strip().upper()
                if dep == 'BBPS':
                    dep = 'MTGBBPS'
                if dep in stock:
                    vals = stock[dep] or {}
                    total = int(vals.get('total') or 0)
                    # Forzar reserved = total para que available = 0
                    stock[dep] = {**vals, 'reserved': total}
                    logger.info(f"Depósito {dep} marcado como agotado para SKU {sku} (resultante <= 0)")
                    
    except Exception as e:
        logger.warning(f"Error aplicando reservas/agotamiento para SKU {sku}: {e}")
        
    return stock


def _sanitize_obs_for_note(s: Optional[str]) -> Optional[str]:
    """Quita order_id y pack_id del texto para la nota de ML, manteniendo el resto.
    No afecta el texto usado para la observación del movimiento.
    """
    if not s:
        return s
    try:
        t = str(s)
        # Remover segmentos con tuberías y claves específicas
        t = re.sub(r"\s*\|\s*order_id=\d+", "", t)
        t = re.sub(r"\s*\|\s*pack_id=\d+", "", t)
        # Remover si aparecen sin separadores
        t = re.sub(r"order_id=\d+", "", t)
        t = re.sub(r"pack_id=\d+", "", t)
        # Normalizar separadores y espacios
        t = re.sub(r"\s+\|\s+", " | ", t)
        t = re.sub(r"\s{2,}", " ", t).strip(" |")
        return t
    except Exception:
        return s


def assign_pack_multiventa(pack_id: str, items: List) -> bool:
    """
    Intenta asignar un pack completo siguiendo prioridades:
    1) Un solo depósito que tenga disponible para TODOS los SKUs del pack.
    2) Un solo cluster (A o B) que permita cubrir cada SKU dentro del cluster (sin mezclar clusters).
    3) Si no es posible, marcar split_required a TODO el pack, sin reservar ni mover.
    """
    logger.info(f"🧺 Pack {pack_id}: {len(items)} ítems pendientes")
    # Preparar stocks por SKU
    sku_list = [(it, it.sku, int(it.qty or 0)) for it in items]
    stocks: Dict[str, dict] = {}
    for _, sku, _qty in sku_list:
        stocks[sku] = _get_stock_with_reserves(sku)
    # Descripción compacta de ítems para observaciones multiventa
    try:
        _items_desc = ", ".join([f"{s}:{int(q)}" for _, s, q in sku_list])
    except Exception:
        _items_desc = ""

    # Regla especial por cuenta 756086955: asignar SIEMPRE a MUNDOCAB (sin buscar ganador/cluster)
    try:
        all_caba = all(int(_detect_seller_id(it) or 0) == 756086955 for it, _, _ in sku_list)
    except Exception:
        all_caba = False
    if all_caba:
        logger.info(f"Pack {pack_id}: regla seller=756086955 → asignar MUNDOCAB sin evaluar clusters")
        for it, sku, qty in sku_list:
            vals = (stocks.get(sku) or {}).get('MUNDOCAB') or {}
            total = int(vals.get('total') or 0)
            reserved = int(vals.get('reserved') or 0)
            _assign_with_values(
                it,
                depot='MUNDOCAB',
                stock=stocks.get(sku) or {},
                total=total,
                reserved=reserved,
                asignacion_detalle=json.dumps({
                    "opcion": 1,
                    "tipo": "single",
                    "depo": "MUNDOCAB",
                    "qty": int(qty),
                    "method": str(get_last_method() or 'API'),
                }, ensure_ascii=False),
                opcion_elegida=1,
            )
            # Movimiento
            observacion = f"MULTIVENTA OPCION:1 | pack_id={pack_id} | items={_items_desc} | " \
                          f"MATIAPP MELI A MELI | order_id={it.order_id} | pack_id={pack_id} | op=1"
            try:
                _titulo = (getattr(it, 'nombre', None) or '').strip()
                if _titulo:
                    observacion += f" | nombre={_titulo[:120]}"
            except Exception:
                pass
            sid_eff = _detect_seller_id(it)
            mv = move_stock_woo_to_woo(
                sku=sku,
                qty=qty,
                observacion=observacion,
                tipo=2,
                barcode=getattr(it, 'barcode', None) or None,
                articulo_detalle=getattr(it, 'nombre', None) or "",
            )
            # Marcar movimiento
            with SessionLocal() as session:
                with session.begin():
                    numero = mv.get('numero') or None
                    numero_str = str(numero) if numero is not None else ''
                    nota_mov = observacion + (f" | numero_movimiento={numero_str}" if numero_str else '')
                    if mv.get('ok'):
                        session.execute(
                            text(
                                """
                                UPDATE orders_meli
                                SET movimiento_realizado = 1,
                                    fecha_movimiento = SYSUTCDATETIME(),
                                    fecha_actualizacion = SYSUTCDATETIME(),
                                    observacion_movimiento = LEFT(:nota, 500),
                                    numero_movimiento = LEFT(:num, 100)
                                WHERE id = :id AND (movimiento_realizado = 0 OR movimiento_realizado IS NULL)
                                """
                            ),
                            {"id": it.id, "nota": nota_mov, "num": numero_str},
                        )
                        # Publicar nota ML idempotente
                        try:
                            # Calcular agotado con los valores usados en la asignación
                            vals = (stocks.get(sku) or {}).get('MUNDOCAB') or {}
                            total = int(vals.get('total') or 0)
                            reserved = int(vals.get('reserved') or 0)
                            new_reserved = reserved + int(qty or 0)
                            agotado = (total - new_reserved) <= 0
                            res_note = publish_note_upsert(
                                order_id=str(it.order_id),
                                seller_id=(_detect_seller_id(it) or getattr(it, 'seller_id', None)),
                                deposito_asignado='MUNDOCAB',
                                qty=int(qty or 0),
                                agotado=agotado,
                                observacion_mov=_sanitize_obs_for_note(observacion),
                                numero_mov=numero if numero is not None else None,
                            )
                            try:
                                logger.info(
                                    f"Nota ML (pack regla 756086955) order_id={it.order_id} seller_id={getattr(it, 'seller_id', None)} "
                                    f"depo=MUNDOCAB qty={int(qty or 0)} status={res_note.get('status')} ok={res_note.get('ok')} err={res_note.get('error')}"
                                )
                            except Exception:
                                pass
                            # Persistir bandera y texto si la publicación fue OK (columnas opcionales)
                            try:
                                if res_note.get('ok'):
                                    session.execute(
                                        text(
                                            """
                                            UPDATE orders_meli
                                            SET nota_hecha = 1,
                                                nota_texto_publicada = COALESCE(:texto, nota_texto_publicada),
                                                fecha_nota = SYSUTCDATETIME()
                                            WHERE id = :id
                                            """
                                        ),
                                        {"id": it.id, "texto": (res_note.get('note') or '')[:2000]},
                                    )
                            except Exception:
                                # Columnas pueden no existir aún; ignorar
                                pass
                        except Exception as e:
                            logger.warning(f"Nota ML (pack regla 756086955) falló para {it.order_id}: {e}")
                    else:
                        session.execute(
                            text(
                                """
                                UPDATE orders_meli
                                SET observacion_movimiento = LEFT(:nota, 500)
                                WHERE id = :id
                                """
                            ),
                            {"id": it.id, "nota": f"{observacion} | ERROR: {mv.get('error')}"},
                        )
        return True

    # 1) Un único depósito que cubra todos
    allowed = set(getattr(_mod_assigner, 'PUNTOS', {}).keys())
    candidate_depots = [d for d in list(allowed) if str(d).upper() != 'MELI']
    def _avail(depot: str, sku: str) -> int:
        d = stocks[sku].get(depot) or {}
        return max(int(d.get('total') or 0) - int(d.get('reserved') or 0), 0)

    single_ok: Optional[str] = None
    for depot in candidate_depots:
        if all(_avail(depot, sku) >= qty for _, sku, qty in sku_list):
            single_ok = depot
            break

    if single_ok:
        logger.info(f"Pack {pack_id}: opción 1 (single) en {single_ok}")
        # Asignar cada ítem al mismo depósito, con detalle opción 1 + movimiento
        for it, sku, qty in sku_list:
            _assign_with_values(
                it,
                depot=single_ok,
                stock=stocks[sku],
                total=int(stocks[sku].get(single_ok, {}).get('total') or 0),
                reserved=int(stocks[sku].get(single_ok, {}).get('reserved') or 0),
                asignacion_detalle=json.dumps({
                    "opcion": 1,
                    "tipo": "single",
                    "depo": str(single_ok),
                    "qty": int(qty),
                    "method": str(get_last_method() or 'API'),
                }, ensure_ascii=False),
                opcion_elegida=1,
            )
            # Movimiento
            observacion = f"MULTIVENTA OPCION:1 | pack_id={pack_id} | items={_items_desc} | " \
                          f"MATIAPP MELI A MELI | order_id={it.order_id} | pack_id={pack_id} | op=1"
            try:
                _titulo = (getattr(it, 'nombre', None) or '').strip()
                if _titulo:
                    observacion += f" | nombre={_titulo[:120]}"
            except Exception:
                pass
            sid_eff = _detect_seller_id(it)
            mv = move_stock_woo_to_woo(
                sku=sku,
                qty=qty,
                observacion=observacion,
                tipo=2,
                barcode=getattr(it, 'barcode', None) or None,
                articulo_detalle=getattr(it, 'nombre', None) or "",
            )
            # Marcar movimiento
            with SessionLocal() as session:
                with session.begin():
                    numero = mv.get('numero') or None
                    numero_str = str(numero) if numero is not None else ''
                    nota_mov = observacion + (f" | numero_movimiento={numero_str}" if numero_str else '')
                    if mv.get('ok'):
                        session.execute(
                            text(
                                """
                                UPDATE orders_meli
                                SET movimiento_realizado = 1,
                                    fecha_movimiento = SYSUTCDATETIME(),
                                    fecha_actualizacion = SYSUTCDATETIME(),
                                    observacion_movimiento = LEFT(:nota, 500),
                                    numero_movimiento = LEFT(:num, 100)
                                WHERE id = :id AND (movimiento_realizado = 0 OR movimiento_realizado IS NULL)
                                """
                            ),
                            {"id": it.id, "nota": nota_mov, "num": numero_str},
                        )
                        # Publicar nota ML idempotente (pack opción single_ok)
                        try:
                            tot = int(stocks[sku].get(single_ok, {}).get('total') or 0)
                            res = int(stocks[sku].get(single_ok, {}).get('reserved') or 0)
                            new_reserved = res + int(qty or 0)
                            agotado = (tot - new_reserved) <= 0
                            res_note = publish_note_upsert(
                                order_id=str(it.order_id),
                                seller_id=(sid_eff or getattr(it, 'seller_id', None)),
                                deposito_asignado=str(single_ok),
                                qty=int(qty or 0),
                                agotado=agotado,
                                observacion_mov=_sanitize_obs_for_note(observacion),
                                numero_mov=numero if numero is not None else None,
                            )
                            try:
                                logger.info(
                                    f"Nota ML (pack single) order_id={it.order_id} seller_id={getattr(it, 'seller_id', None)} "
                                    f"depo={str(single_ok)} qty={int(qty or 0)} status={res_note.get('status')} ok={res_note.get('ok')} err={res_note.get('error')}"
                                )
                            except Exception:
                                pass
                            # Persistir bandera y texto si la publicación fue OK (columnas opcionales)
                            try:
                                if res_note.get('ok'):
                                    session.execute(
                                        text(
                                            """
                                            UPDATE orders_meli
                                            SET nota_hecha = 1,
                                                nota_texto_publicada = COALESCE(:texto, nota_texto_publicada),
                                                fecha_nota = SYSUTCDATETIME()
                                            WHERE id = :id
                                            """
                                        ),
                                        {"id": it.id, "texto": (res_note.get('note') or '')[:2000]},
                                    )
                            except Exception:
                                pass
                        except Exception as e:
                            logger.warning(f"Nota ML (pack single_ok) falló para {it.order_id}: {e}")
                    else:
                        session.execute(
                            text(
                                """
                                UPDATE orders_meli
                                SET observacion_movimiento = LEFT(:nota, 500)
                                WHERE id = :id
                                """
                            ),
                            {"id": it.id, "nota": f"{observacion} | ERROR: {mv.get('error')}"},
                        )
        return True

    # 2) Un solo cluster que cubra todos (pueden ser distintos depósitos dentro del cluster)
    if getattr(_mod_cfg, 'MULTIVENTA_MODE', 'off') == 'clustered':
        clusters = getattr(_mod_cfg, 'CLUSTERS', {})
        for cname in ['A', 'B']:
            deps = clusters.get(cname) or []
            if not deps:
                continue
            # para cada SKU elegir un deposito del cluster que tenga disponible
            choices: List[Tuple[object, str, int, str]] = []  # (order, sku, qty, chosen_depot)
            possible = True
            for it, sku, qty in sku_list:
                # elegir depósito con mayor disponible dentro del cluster
                candidates = sorted(deps, key=lambda d: _avail(d, sku), reverse=True)
                if not candidates or _avail(candidates[0], sku) <= 0:
                    possible = False
                    break
                chosen = None
                for d in candidates:
                    if _avail(d, sku) >= qty:
                        chosen = d
                        break
                if not chosen:
                    possible = False
                    break
                choices.append((it, sku, qty, chosen))
            if possible and choices:
                logger.info(f"Pack {pack_id}: opción 2 (cluster {cname})")
                # Asignar cada ítem en su depósito elegido dentro del cluster + movimiento
                for it, sku, qty, d in choices:
                    det = {
                        "opcion": 2,
                        "tipo": "cluster",
                        "cluster": cname,
                        "qty": int(qty),
                        "distribucion": [{"depo": d, "qty": int(qty)}],
                        "method": str(get_last_method() or 'API'),
                    }
                    vals = stocks[sku].get(d) or {}
                    _assign_with_values(
                        it,
                        depot=d,
                        stock=stocks[sku],
                        total=int(vals.get('total') or 0),
                        reserved=int(vals.get('reserved') or 0),
                        asignacion_detalle=json.dumps(det, ensure_ascii=False),
                        opcion_elegida=2,
                    )
                    # Movimiento con dist info
                    observacion = f"MULTIVENTA OPCION:2 | pack_id={pack_id} | items={_items_desc} | " \
                                  f"MATIAPP MELI A MELI | order_id={it.order_id} | pack_id={pack_id} | dist={d}:{int(qty)} | op=2"
                    try:
                        _titulo = (getattr(it, 'nombre', None) or '').strip()
                        if _titulo:
                            observacion += f" | nombre={_titulo[:120]}"
                    except Exception:
                        pass
                    sid_eff2 = _detect_seller_id(it)
                    mv = move_stock_woo_to_woo(
                        sku=sku,
                        qty=qty,
                        observacion=observacion,
                        tipo=2,
                        barcode=getattr(it, 'barcode', None) or None,
                        articulo_detalle=getattr(it, 'nombre', None) or "",
                    )
                    with SessionLocal() as session:
                        with session.begin():
                            numero = mv.get('numero') or None
                            numero_str = str(numero) if numero is not None else ''
                            nota_mov = observacion + (f" | numero_movimiento={numero_str}" if numero_str else '')
                            if mv.get('ok'):
                                session.execute(
                                    text(
                                        """
                                        UPDATE orders_meli
                                        SET movimiento_realizado = 1,
                                            fecha_movimiento = SYSUTCDATETIME(),
{{ ... }}
                                            fecha_actualizacion = SYSUTCDATETIME(),
                                            observacion_movimiento = LEFT(:nota, 500),
                                            numero_movimiento = LEFT(:num, 100)
                                        WHERE id = :id AND (movimiento_realizado = 0 OR movimiento_realizado IS NULL)
                                        """
                                    ),
                                    {"id": it.id, "nota": nota_mov, "num": numero_str},
                                )
                                # Publicar nota ML idempotente
                                try:
                                    vals2 = stocks[sku].get(d) or {}
                                    tot2 = int(vals2.get('total') or 0)
                                    res2 = int(vals2.get('reserved') or 0)
                                    new_reserved2 = res2 + int(qty or 0)
                                    agotado2 = (tot2 - new_reserved2) <= 0
                                    res_note = publish_note_upsert(
                                        order_id=str(it.order_id),
                                        seller_id=(sid_eff2 or getattr(it, 'seller_id', None)),
                                        deposito_asignado=str(d),
                                        qty=int(qty or 0),
                                        agotado=agotado2,
                                        observacion_mov=_sanitize_obs_for_note(observacion),
                                        numero_mov=numero if numero is not None else None,
                                    )
                                    try:
                                        logger.info(
                                            f"Nota ML (pack cluster) order_id={it.order_id} seller_id={getattr(it, 'seller_id', None)} "
                                            f"depo={str(d)} qty={int(qty or 0)} status={res_note.get('status')} ok={res_note.get('ok')} err={res_note.get('error')}"
                                        )
                                    except Exception:
                                        pass
                                    # Persistir bandera y texto si la publicación fue OK (columnas opcionales)
                                    try:
                                        if res_note.get('ok'):
                                            session.execute(
                                                text(
                                                    """
                                                    UPDATE orders_meli
                                                    SET nota_hecha = 1,
                                                        nota_texto_publicada = COALESCE(:texto, nota_texto_publicada),
                                                        fecha_nota = SYSUTCDATETIME()
                                                    WHERE id = :id
                                                    """
                                                ),
                                                {"id": it.id, "texto": (res_note.get('note') or '')[:2000]},
                                            )
                                    except Exception:
                                        pass
                                except Exception as e:
                                    logger.warning(f"Nota ML (pack cluster) falló para {it.order_id}: {e}")
                            else:
                                session.execute(
                                    text(
                                        """
                                        UPDATE orders_meli
                                        SET observacion_movimiento = LEFT(:nota, 500)
                                        WHERE id = :id
                                        """
                                    ),
                                    {"id": it.id, "nota": f"{observacion} | ERROR: {mv.get('error')}"},
                                )
                return True

    # 3) No se puede sin partir. Si está habilitado, generar split detallado por SKU y publicar nota; si ni dividido alcanza, opción 4
    split_detailed = str(os.getenv('PIPE08_SPLIT_DETAILED', '1')).strip() == '1'
    if not split_detailed:
        # Comportamiento legacy: solo marcar split_required sin detalle
        try:
            detalle = json.dumps({
                "opcion": 3,
                "tipo": "split_required",
                "motivo": "multi_cluster",
                "method": str(get_last_method() or 'API'),
            }, ensure_ascii=False)
        except Exception:
            detalle = None
        with SessionLocal() as session:
            with session.begin():
                for it, _, _ in sku_list:
                    session.execute(
                        text("""
                            UPDATE orders_meli
                            SET DEBE_PARTIRSE = 1,
                                deposito_asignado = 'DIVIDIDO',
                                asignacion_detalle = COALESCE(:detalle, asignacion_detalle),
                                opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida)
                            WHERE id = :id
                        """),
                        {"id": it.id, "detalle": detalle, "opcion_elegida": 3}
                    )
        logger.info(f"Pack {pack_id}: opción 3 (split_required) marcado en todos los ítems (legacy)")
        return False
    
    # Nuevo: por cada SKU del pack, armar distribución sin prioridad (greedy por disponible) y publicar nota
    for it, sku, qty in sku_list:
        try:
            stock_sku = stocks.get(sku) or {}
            # calcular disponible total
            sum_total = sum(max(_available(v or {}), 0) for v in stock_sku.values())
            if sum_total < int(qty or 0):
                # Opción 4: imposible asignar ni dividido
                try:
                    detalle_it = json.dumps({
                        "opcion": 4,
                        "tipo": "imposible",
                        "motivo": "sin_stock_total",
                        "qty": int(qty),
                        "available": int(sum_total),
                        "method": str(get_last_method() or 'API'),
                    }, ensure_ascii=False)
                except Exception:
                    detalle_it = None
                with SessionLocal() as session:
                    with session.begin():
                        session.execute(
                            text("""
                                UPDATE orders_meli
                                SET DEBE_PARTIRSE = 0,
                                    deposito_asignado = 'SIN_STOCK',
                                    asignacion_detalle = COALESCE(:detalle, asignacion_detalle),
                                    opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida)
                                WHERE id = :id
                            """),
                            {"id": it.id, "detalle": detalle_it, "opcion_elegida": 4}
                        )
                logger.info(f"Pack {pack_id}: opción 4 (imposible) marcado para SKU {sku}")
                continue

            # Se puede cubrir dividido: ordenar todos los depósitos por disponible
            all_deps = sorted(list(stock_sku.keys()), key=lambda d: _available(stock_sku.get(d) or {}), reverse=True)
            dist = _distribute_within_cluster(stock_sku, int(qty or 0), all_deps)
            try:
                detalle_it = json.dumps({
                    "opcion": 3,
                    "tipo": "split_required",
                    "motivo": "multi_cluster",
                    "qty": int(qty),
                    "distribucion": dist,
                    "method": str(get_last_method() or 'API'),
                }, ensure_ascii=False)
            except Exception:
                detalle_it = None

            # Persistir split sugerido
            with SessionLocal() as session:
                with session.begin():
                    session.execute(
                        text("""
                            UPDATE orders_meli
                            SET DEBE_PARTIRSE = 1,
                                deposito_asignado = 'DIVIDIDO',
                                asignacion_detalle = COALESCE(:detalle, asignacion_detalle),
                                opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida)
                            WHERE id = :id
                        """),
                        {"id": it.id, "detalle": detalle_it, "opcion_elegida": 3}
                    )

            # Publicar nota ML con split sugerido por ítem
            try:
                dist_str = _format_dist_str(dist)
                observacion = f"SPLIT SUGERIDO | order_id={it.order_id} | pack_id={pack_id} | sku={sku} | qty={int(qty)} | dist={dist_str} | op=3"
                res_note = publish_note_upsert(
                    order_id=str(it.order_id),
                    seller_id=(_detect_seller_id(it) or getattr(it, 'seller_id', None)),
                    deposito_asignado='DIVIDIDO',
                    qty=0,
                    agotado=False,
                    observacion_mov=_sanitize_obs_for_note(observacion),
                    numero_mov=None,
                )
                # Persistir bandera y texto si la publicación fue OK (columnas opcionales)
                try:
                    if res_note.get('ok'):
                        with SessionLocal() as session:
                            with session.begin():
                                session.execute(
                                    text(
                                        """
                                        UPDATE orders_meli
                                        SET nota_hecha = 1,
                                            nota_texto_publicada = COALESCE(:texto, nota_texto_publicada),
                                            fecha_nota = SYSUTCDATETIME()
                                        WHERE id = :id
                                        """
                                    ),
                                    {"id": it.id, "texto": (res_note.get('note') or '')[:2000]},
                                )
                except Exception:
                    pass
                try:
                    logger.info(
                        f"Nota ML (pack op3 split sugerido) order_id={it.order_id} seller_id={getattr(it, 'seller_id', None)} dist={dist_str} status={res_note.get('status')} ok={res_note.get('ok')}"
                    )
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Nota ML (op3) falló para {it.order_id}: {e}")
        except Exception as e:
            logger.error(f"Error generando split detallado para order_id={getattr(it,'order_id',None)} sku={sku}: {e}")
            continue

    logger.info(f"Pack {pack_id}: opción 3 (split detallado/op4) procesada por ítem")
    return False


def _assign_with_values(order, depot: str, stock: dict, total: int, reserved: int, asignacion_detalle: Optional[str], opcion_elegida: Optional[int] = None) -> None:
    """Internal helper to perform the DB update like assign_single_order does, but using provided values and JSON.
    Adds writing to opcion_elegida when provided.
    """
    new_reserved = reserved + int(order.qty or 0)
    resultante = total - new_reserved
    agotamiento_flag = (resultante <= 0)
    def _tot(depot_code: str) -> int:
        try:
            d = stock.get(depot_code) or {}
            return int(d.get('total') or 0)
        except Exception:
            return 0
    stock_cols = {
        'stock_dep': _tot('DEP'),
        'stock_mundoal': _tot('MUNDOAL'),
        'stock_monbahia': _tot('MONBAHIA'),
        'stock_mtgbbps': _tot('MTGBBPS'),
        'stock_mundocab': _tot('MUNDOCAB'),
        'stock_nqnshop': _tot('NQNSHOP'),
        'stock_mtgcom': _tot('MTGCOM'),
        'stock_mtgroca': _tot('MTGROCA'),
        'stock_mundoroc': _tot('MUNDOROC'),
    }
    with SessionLocal() as session:
        with session.begin():
            locked_row = session.execute(
                text("SELECT * FROM orders_meli WITH (UPDLOCK,ROWLOCK) WHERE id=:id"),
                {"id": order.id}
            ).first()
            if not locked_row:
                raise RuntimeError(f"No se encontró la orden {order.id} para lock")

            # Si ya estaba asignada, NO pisar asignación ni reservas/resultante
            # Método con el que se calculó el stock (API|SQL)
            try:
                method_val = str(get_last_method() or 'API')
            except Exception:
                method_val = 'API'

            if getattr(locked_row, 'asignado_flag', None):
                session.execute(
                    text("""
                        UPDATE orders_meli 
                        SET asignacion_detalle = COALESCE(:asignacion_detalle, asignacion_detalle),
                            opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida),
                            asignacion_metodo = COALESCE(:asignacion_metodo, asignacion_metodo),
                            stock_mundoal = :stock_mundoal,
                            stock_dep = :stock_dep,
                            stock_monbahia = :stock_monbahia,
                            stock_mtgbbps = :stock_mtgbbps,
                            stock_mundocab = :stock_mundocab,
                            stock_nqnshop = :stock_nqnshop,
                            stock_mtgcom = :stock_mtgcom,
                            stock_mtgroca = :stock_mtgroca,
                            stock_mundoroc = :stock_mundoroc
                        WHERE id = :id
                    """),
                    {
                        "id": order.id,
                        "asignacion_detalle": asignacion_detalle,
                        "opcion_elegida": int(opcion_elegida) if opcion_elegida is not None else None,
                        "asignacion_metodo": method_val,
                        **stock_cols,
                    }
                )
                logger.info(f"Orden {order.order_id} ya estaba asignada (pack-aware). Se preserva depósito={locked_row.deposito_asignado}")
            else:
                session.execute(
                    text("""
                        UPDATE orders_meli 
                        SET deposito_asignado = COALESCE(:depot, deposito_asignado),
                            stock_real = COALESCE(:total, stock_real),
                            stock_reservado = COALESCE(:new_reserved, stock_reservado),
                            resultante = COALESCE(:resultante, resultante),
                            asignado_flag = 1,
                            agotamiento_flag = COALESCE(:agotamiento_flag, agotamiento_flag),
                            fecha_asignacion = SYSUTCDATETIME(),
                            asignacion_detalle = COALESCE(:asignacion_detalle, asignacion_detalle),
                            opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida),
                            asignacion_metodo = COALESCE(:asignacion_metodo, asignacion_metodo),
                            stock_mundoal = :stock_mundoal,
                            stock_dep = :stock_dep,
                            stock_monbahia = :stock_monbahia,
                            stock_mtgbbps = :stock_mtgbbps,
                            stock_mundocab = :stock_mundocab,
                            stock_nqnshop = :stock_nqnshop,
                            stock_mtgcom = :stock_mtgcom,
                            stock_mtgroca = :stock_mtgroca,
                            stock_mundoroc = :stock_mundoroc
                        WHERE id = :id
                    """),
                    {
                        "depot": depot,
                        "total": total,
                        "new_reserved": new_reserved,
                        "resultante": resultante,
                        "agotamiento_flag": agotamiento_flag,
                        "id": order.id,
                        "asignacion_detalle": asignacion_detalle,
                        "opcion_elegida": int(opcion_elegida) if opcion_elegida is not None else None,
                        "asignacion_metodo": method_val,
                        **stock_cols,
                    }
                )
                logger.info(f"✅ Orden {order.order_id} asignada a {depot} (pack-aware)")


def assign_single_order(order) -> bool:
    """
    Asigna un depósito a una orden específica.
    
    Args:
        order: Objeto OrderItem de la orden a procesar
        
    Returns:
        bool: True si se asignó exitosamente
    """
    logger.debug(f"Procesando orden {order.order_id}, SKU: {order.sku}, qty: {order.qty}")
    
    # Reintentos para obtener stock (manejo de timeouts)
    max_retries = 3
    retry_delay = 60  # segundos
    
    for attempt in range(max_retries):
        try:
            # Obtener stock con reservas aplicadas y depósitos agotados marcados
            stock = _get_stock_with_reserves(order.sku)
            break
        except requests.Timeout:
            logger.warning(f"Timeout obteniendo stock para {order.sku}, intento {attempt + 1}/{max_retries}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"Timeout final para orden {order.order_id}")
                return False
        except Exception as e:
            logger.error(f"Error obteniendo stock para {order.sku}: {e}")
            return False

    # Regla especial por cuenta 756086955: forzar ganador = MUNDOCAB
    forced_winner = None
    try:
        if int(getattr(order, 'seller_id', 0)) == 756086955:
            md_vals = stock.get('MUNDOCAB') or {}
            forced_winner = ('MUNDOCAB', int(md_vals.get('total') or 0), int(md_vals.get('reserved') or 0))
            logger.info(f"Orden {order.order_id}: regla seller=756086955 → forzar MUNDOCAB")
    except Exception:
        forced_winner = None

    # Elegir ganador con reservas ya aplicadas (single depot)
    winner = choose_winner(stock, order.qty)
    cluster_used = None
    dist_for_json = None
    obs_dist_str = ''
    if forced_winner is not None:
        winner = forced_winner
    if not winner:
        # Intento clustered (sin partir) si está habilitado
        try:
            if getattr(_mod_cfg, 'MULTIVENTA_MODE', 'off') == 'clustered':
                clusters = getattr(_mod_cfg, 'CLUSTERS', {})
                # Probar A, luego B
                for cname in ['A', 'B']:
                    deps = clusters.get(cname) or []
                    if not deps:
                        continue
                    if _cluster_sum(stock, deps) >= int(order.qty or 0):
                        # Construir distribución
                        dist = _distribute_within_cluster(stock, int(order.qty or 0), deps)
                        if dist:
                            # Elegir como 'depot' el de mayor disponible (primero de la lista ordenada)
                            main_depot = max(deps, key=lambda d: _available(stock.get(d) or {}))
                            # Crear un 'winner' sintético con los números del main_depot
                            md_vals = stock.get(main_depot) or {}
                            winner = (main_depot, int(md_vals.get('total') or 0), int(md_vals.get('reserved') or 0))
                            cluster_used = cname
                            dist_for_json = dist
                            obs_dist_str = _format_dist_str(dist)
                            logger.info(f"Asignación clustered {cname} para orden {order.order_id}: {obs_dist_str}")
                            break
        except Exception as e:
            logger.warning(f"Fallo path clustered para {order.order_id}: {e}")
    if not winner:
        # Evaluar si se podría cumplir solo partiéndola (lejanos o mezcla)
        try:
            lejanos = getattr(_mod_cfg, 'LEJANOS', []) or []
            # suma disponibles
            sum_lejanos = _cluster_sum(stock, lejanos) if lejanos else 0
            sum_total = sum(max(_available(v or {}), 0) for v in (stock or {}).values())
            motivo = None
            dist_preview = []
            if sum_lejanos >= int(order.qty or 0):
                motivo = 'lejanos'
                dist_preview = _distribute_within_cluster(stock, int(order.qty or 0), lejanos)
            elif sum_total >= int(order.qty or 0):
                motivo = 'multi_cluster'
                # ordenar por disponible sobre todos
                all_deps = sorted(list((stock or {}).keys()), key=lambda d: _available(stock.get(d) or {}), reverse=True)
                dist_preview = _distribute_within_cluster(stock, int(order.qty or 0), all_deps)

            if motivo:
                # Persistir marca DEBE_PARTIRSE y detalle
                try:
                    detalle = json.dumps({
                        "opcion": 3,
                        "tipo": "split_required",
                        "motivo": motivo,
                        "qty": int(order.qty or 0),
                        "distribucion": dist_preview,
                        "method": str(get_last_method() or 'API'),
                    }, ensure_ascii=False)
                except Exception:
                    detalle = None
                try:
                    with SessionLocal() as session:
                        with session.begin():
                            session.execute(
                                text("""
                                    UPDATE orders_meli
                                    SET DEBE_PARTIRSE = 1,
                                        deposito_asignado = 'DIVIDIDO',
                                        asignacion_detalle = COALESCE(:detalle, asignacion_detalle),
                                        opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida)
                                    WHERE id = :id
                                """),
                                {"id": order.id, "detalle": detalle, "opcion_elegida": 3}
                            )
                    logger.info(f"Marcado DEBE_PARTIRSE=1 para orden {order.order_id} (motivo={motivo})")
                except Exception as e:
                    logger.error(f"Error marcando DEBE_PARTIRSE en orden {order.order_id}: {e}")

        except Exception as e:
            logger.error(f"Error evaluando split para orden {order.order_id}: {e}")

        logger.warning(f"No hay stock suficiente (single/cluster) para orden {order.order_id}, SKU: {order.sku}, qty: {order.qty}")
        # Publicar nota en ML indicando falta de stock
        try:
            observacion = f"NO SE ENCUENTRA STOCK | order_id={order.order_id} | sku={order.sku} | qty={int(order.qty or 0)}"
            res_note = publish_note_upsert(
                order_id=str(order.order_id),
                seller_id=getattr(order, 'seller_id', None),
                deposito_asignado='SIN_STOCK',
                qty=0,
                agotado=True,
                observacion_mov=_sanitize_obs_for_note(observacion),
                numero_mov=None,
            )
            # Persistir bandera y texto si la publicación fue OK (columnas opcionales)
            try:
                if res_note.get('ok'):
                    with SessionLocal() as session:
                        with session.begin():
                            session.execute(
                                text(
                                    """
                                    UPDATE orders_meli
                                    SET nota_hecha = 1,
                                        nota_texto_publicada = COALESCE(:texto, nota_texto_publicada),
                                        fecha_nota = SYSUTCDATETIME(),
                                        opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida)
                                    WHERE id = :id
                                    """
                                ),
                                {"id": order.id, "texto": (res_note.get('note') or '')[:2000], "opcion_elegida": 4},
                            )
            except Exception:
                # Columnas pueden no existir; ignorar
                pass
        except Exception as e:
            logger.warning(f"No-stock: publicación de nota falló para {order.order_id}: {e}")
        return False
    
    depot, total, reserved = winner
    assigned_ok = False
    
    # Transacción segura con lock
    try:
        with SessionLocal() as session:
            with session.begin():
                # Lock exclusivo en la fila
                locked_row = session.execute(
                    text("SELECT * FROM orders_meli WITH (UPDLOCK,ROWLOCK) WHERE id=:id"),
                    {"id": order.id}
                ).first()
                
                if not locked_row:
                    logger.error(f"No se encontró la orden {order.id} para lock")
                    return False
                
                # Verificar que no haya sido asignada por otro proceso
                if locked_row.asignado_flag:
                    logger.info(f"Orden {order.order_id} ya estaba asignada. Se preserva depósito={locked_row.deposito_asignado}")
                
                # Recalcular dentro de la transacción el reservado agregado por sku+depósito (excluye impresas)
                # Sumar reservas previas incluyendo alias si el depósito es MTGBBPS
                if str(depot).upper() == 'MTGBBPS':
                    row_res = session.execute(
                        text(
                            """
                            SELECT ISNULL(SUM(qty), 0) AS qty_res
                            FROM orders_meli WITH (UPDLOCK, HOLDLOCK)
                            WHERE sku = :sku
                              AND asignado_flag = 1
                              AND (deposito_asignado = 'MTGBBPS' OR deposito_asignado = 'BBPS')
                              AND ISNULL(shipping_subestado, '') NOT IN ('printed','shipped','delivered','canceled')
                              AND ISNULL(shipping_estado, '') NOT IN ('printed','shipped','delivered','canceled')
                            """
                        ),
                        {"sku": order.sku}
                    ).first()
                else:
                    row_res = session.execute(
                        text(
                            """
                            SELECT ISNULL(SUM(qty), 0) AS qty_res
                            FROM orders_meli WITH (UPDLOCK, HOLDLOCK)
                            WHERE sku = :sku
                              AND deposito_asignado = :depo
                              AND asignado_flag = 1
                              AND ISNULL(shipping_subestado, '') NOT IN ('printed','shipped','delivered','canceled')
                              AND ISNULL(shipping_estado, '') NOT IN ('printed','shipped','delivered','canceled')
                            """
                        ),
                        {"sku": order.sku, "depo": depot}
                    ).first()
                reserved_agg_pre = int((row_res.qty_res if row_res and row_res.qty_res is not None else 0))

                # Calcular valores usando el agregado post-asignación
                new_reserved = reserved_agg_pre + int(order.qty or 0)
                resultante = int(total) - int(new_reserved)
                agotamiento_flag = (resultante <= 0)

                logger.debug(
                    f"Orden {order.order_id} sku={order.sku} depo={depot} total={total} "
                    f"reserved_agg_pre={reserved_agg_pre} new_reserved={new_reserved} resultante={resultante}"
                )
                
                # Mapear stock por depósito (totales) a columnas
                def _tot(depot_code: str) -> int:
                    try:
                        d = stock.get(depot_code) or {}
                        return int(d.get('total') or 0)
                    except Exception:
                        return 0
                stock_cols = {
                    'stock_dep': _tot('DEP'),
                    'stock_mundoal': _tot('MUNDOAL'),
                    'stock_monbahia': _tot('MONBAHIA'),
                    'stock_mtgbbps': _tot('MTGBBPS'),
                    'stock_mundocab': _tot('MUNDOCAB'),
                    'stock_nqnshop': _tot('NQNSHOP'),
                    'stock_mtgcom': _tot('MTGCOM'),
                    'stock_mtgroca': _tot('MTGROCA'),
                    'stock_mundoroc': _tot('MUNDOROC'),
                }
                
                # Detalle de asignación (single) para auditoría JSON
                try:
                    if dist_for_json and cluster_used:
                        asignacion_detalle = json.dumps({
                            "opcion": 2,
                            "tipo": "cluster",
                            "cluster": cluster_used,
                            "qty": int(order.qty or 0),
                            "distribucion": dist_for_json,
                            "method": str(get_last_method() or 'API'),
                        }, ensure_ascii=False)
                    else:
                        asignacion_detalle = json.dumps({
                            "opcion": 1,
                            "tipo": "single",
                            "depo": str(depot),
                            "qty": int(order.qty or 0),
                            "winner_total": int(total),
                            "winner_reserved": int(reserved),
                            "winner_available": int(total - reserved),
                            "method": str(get_last_method() or 'API'),
                        }, ensure_ascii=False)
                except Exception:
                    asignacion_detalle = None

                # Actualizar la orden: evitar pisar asignación si ya estaba asignada
                if locked_row.asignado_flag:
                    session.execute(
                        text("""
                            UPDATE orders_meli 
                            SET asignacion_detalle = COALESCE(:asignacion_detalle, asignacion_detalle),
                                opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida),
                                stock_mundoal = :stock_mundoal,
                                stock_dep = :stock_dep,
                                stock_monbahia = :stock_monbahia,
                                stock_mtgbbps = :stock_mtgbbps,
                                stock_mundocab = :stock_mundocab,
                                stock_nqnshop = :stock_nqnshop,
                                stock_mtgcom = :stock_mtgcom,
                                stock_mtgroca = :stock_mtgroca,
                                stock_mundoroc = :stock_mundoroc
                            WHERE id = :id
                        """),
                        {
                            "id": order.id,
                            "asignacion_detalle": asignacion_detalle,
                            "opcion_elegida": (2 if (dist_for_json and cluster_used) else 1),
                            **stock_cols,
                        }
                    )
                else:
                    session.execute(
                        text("""
                            UPDATE orders_meli 
                            SET deposito_asignado = COALESCE(:depot, deposito_asignado),
                                stock_real = COALESCE(:total, stock_real),
                                stock_reservado = COALESCE(:new_reserved, stock_reservado),
                                resultante = COALESCE(:resultante, resultante),
                                asignado_flag = 1,
                                agotamiento_flag = COALESCE(:agotamiento_flag, agotamiento_flag),
                                fecha_asignacion = SYSUTCDATETIME(),
                                asignacion_detalle = COALESCE(:asignacion_detalle, asignacion_detalle),
                                opcion_elegida = COALESCE(:opcion_elegida, opcion_elegida),
                                nota = LEFT(:nota, 300),
                                stock_mundoal = :stock_mundoal,
                                stock_dep = :stock_dep,
                                stock_monbahia = :stock_monbahia,
                                stock_mtgbbps = :stock_mtgbbps,
                                stock_mundocab = :stock_mundocab,
                                stock_nqnshop = :stock_nqnshop,
                                stock_mtgcom = :stock_mtgcom,
                                stock_mtgroca = :stock_mtgroca,
                                stock_mundoroc = :stock_mundoroc
                            WHERE id = :id
                        """),
                        {
                            "depot": depot,
                            "total": total,
                            "new_reserved": new_reserved,
                            "resultante": resultante,
                            "agotamiento_flag": agotamiento_flag,
                            "id": order.id,
                            "asignacion_detalle": asignacion_detalle,
                            "opcion_elegida": (2 if (dist_for_json and cluster_used) else 1),
                            "nota": f"[APPMATI: {depot} qty={int(order.qty or 0)} agotado={'SI' if agotamiento_flag else 'NO'} | MATIAPP MELI A MELI | op={'2' if (dist_for_json and cluster_used) else '1'}]",
                            **stock_cols,
                        }
                    )
                    logger.info(f"✅ Orden {order.order_id} asignada a {depot} "
                               f"(stock: {total}, reservado: {new_reserved}, resultante: {resultante})")
                
                # Notificar si hay agotamiento
                if agotamiento_flag:
                    try:
                        alert_stock_zero({
                            "sku": order.sku,
                            "depot": depot,
                            "order_id": order.order_id,
                            "total": total,
                            "reserved": new_reserved
                        })
                    except Exception as e:
                        logger.error(f"Error enviando alerta de agotamiento: {e}")
                
                # Solo marcamos como asignada si la acabamos de asignar
                assigned_ok = False if locked_row.asignado_flag else True
                
    except Exception as e:
        logger.error(f"Error en transacción para orden {order.order_id}: {e}")
        return False

    # Si la asignación no se realizó (ya estaba asignada), no continuar con movimiento
    if not assigned_ok:
        return True

    # Fuera de la transacción: ejecutar movimiento MELI→MELI en Dragonfish
    # Observación para idempotencia (debe ser estable por orden)
    observacion = f"MATIAPP MELI A MELI | order_id={order.order_id} | pack_id={order.pack_id or '-'}"
    try:
        _titulo = (getattr(order, 'nombre', None) or '').strip()
        if _titulo:
            observacion += f" | nombre={_titulo[:120]}"
    except Exception:
        pass
    if obs_dist_str:
        observacion += f" | dist={obs_dist_str}"
    # Marcar la opción en la observación para lectura rápida
    try:
        if dist_for_json and cluster_used:
            observacion += " | op=2"
        else:
            observacion += " | op=1"
    except Exception:
        pass
    mv = move_stock_woo_to_woo(
        sku=order.sku,
        qty=order.qty,
        observacion=observacion,
        tipo=2,
        barcode=order.barcode or None,
        articulo_detalle=getattr(order, 'nombre', None) or "",
    )

    # Segunda transacción para marcar flags de movimiento de forma idempotente
    with SessionLocal() as session:
        with session.begin():
            locked_row2 = session.execute(
                text("SELECT * FROM orders_meli WITH (UPDLOCK,ROWLOCK) WHERE id=:id"),
                {"id": order.id}
            ).first()

            if not locked_row2:
                logger.error(f"No se encontró la orden {order.id} para marcar movimiento")
                return False

        # Nota de movimiento a almacenar: observación + número de movimiento si vino
        numero = mv.get('numero') or None
        numero_str = str(numero) if numero is not None else ''
        nota_mov = observacion
        if numero_str:
            nota_mov = f"{observacion} | numero_movimiento={numero_str}"
        # Anexar auditoría de origen/base si está disponible
        try:
            od = mv.get('od')
            bdb = mv.get('base_db')
            if od:
                nota_mov += f" | od={od}"
            if bdb:
                nota_mov += f" | base={bdb}"
        except Exception:
            pass

        with session.begin():
            if mv.get('ok'):
                session.execute(
                    text(
                        """
                        UPDATE orders_meli
                        SET movimiento_realizado = 1,
                            fecha_movimiento = SYSUTCDATETIME(),
                            fecha_actualizacion = SYSUTCDATETIME(),
                            observacion_movimiento = LEFT(:nota, 500),
                            numero_movimiento = LEFT(:num, 100)
                        WHERE id = :id AND (movimiento_realizado = 0 OR movimiento_realizado IS NULL)
                        """
                    ),
                    {"id": order.id, "nota": nota_mov, "num": numero_str}
                )
                logger.info(f"✅ Movimiento MELI→MELI registrado para orden {order.order_id}")
                # Publicar nota ML idempotente para la orden individual
                try:
                    # Usar los valores calculados previamente en la asignación
                    # agotamiento_flag se calculó antes de mover
                    res_note = publish_note_upsert(
                        order_id=str(order.order_id),
                        seller_id=getattr(order, 'seller_id', None),
                        deposito_asignado=str(depot),
                        qty=int(order.qty or 0),
                        agotado=bool(agotamiento_flag),
                        observacion_mov=_sanitize_obs_for_note(observacion),
                        numero_mov=(mv.get('numero') or None),
                    )
                    try:
                        logger.info(
                            f"Nota ML (single) order_id={order.order_id} seller_id={getattr(order, 'seller_id', None)} "
                            f"depo={str(depot)} qty={int(order.qty or 0)} status={res_note.get('status')} ok={res_note.get('ok')} err={res_note.get('error')}"
                        )
                    except Exception:
                        pass
                    # Persistir bandera y texto si la publicación fue OK (columnas opcionales)
                    try:
                        if res_note.get('ok'):
                            session.execute(
                                text(
                                    """
                                    UPDATE orders_meli
                                    SET nota_hecha = 1,
                                        nota_texto_publicada = COALESCE(:texto, nota_texto_publicada),
                                        fecha_nota = SYSUTCDATETIME()
                                    WHERE id = :id
                                    """
                                ),
                                {"id": order.id, "texto": (res_note.get('note') or '')[:2000]},
                            )
                    except Exception:
                        pass
                except Exception as e:
                    logger.warning(f"Nota ML (single) falló para {order.order_id}: {e}")
                return True
            else:
                # Registrar solo la nota de error, sin marcar el flag, para reintento manual/posterior
                session.execute(
                    text(
                        """
                        UPDATE orders_meli
                        SET observacion_movimiento = LEFT(:nota, 500)
                        WHERE id = :id
                        """
                    ),
                    {"id": order.id, "nota": f"{observacion} | ERROR: {mv.get('error')}"}
                )
                logger.error(f"❌ Error en movimiento MELI→MELI para orden {order.order_id}: {mv.get('error')}")
                return False


def backfill_stock_columns(max_rows: int = 20) -> int:
    """
    Completa columnas de stock por depósito para órdenes ya asignadas que aún
    tienen 0 en dichas columnas. No modifica flags ni reasigna, solo completa visibilidad.
    """
    updated = 0
    with SessionLocal() as session:
        # Buscar órdenes asignadas con columnas de stock en 0
        rows = session.execute(
            text(
                """
                SELECT TOP(:maxr) id, order_id, sku
                FROM orders_meli WITH (READPAST)
                WHERE asignado_flag = 1
                  AND ISNULL(stock_dep,0)=0 AND ISNULL(stock_mundoal,0)=0 AND ISNULL(stock_monbahia,0)=0
                  AND ISNULL(stock_mtgbbps,0)=0 AND ISNULL(stock_mundocab,0)=0 AND ISNULL(stock_nqnshop,0)=0
                  AND ISNULL(stock_mtgcom,0)=0 AND ISNULL(stock_mtgroca,0)=0 AND ISNULL(stock_mundoroc,0)=0
                ORDER BY id DESC
                """
            ),
            {"maxr": max_rows},
        ).fetchall()

        for r in rows:
            oid = r.id
            sku = r.sku
            try:
                # Obtener stock actual por depósito para el SKU
                if get_stock_by_sku is not None:
                    stock = get_stock_by_sku(sku)
                elif get_stock_per_deposit is not None:
                    stock = get_stock_per_deposit(sku, timeout=120)
                else:
                    logger.error("No hay cliente Dragonfish disponible para backfill")
                    continue

                def _tot(code: str) -> int:
                    try:
                        d = stock.get(code) or {}
                        return int(d.get('total') or 0)
                    except Exception:
                        return 0

                session.execute(
                    text(
                        """
                        UPDATE orders_meli
                        SET stock_mundoal = :stock_mundoal,
                            stock_dep = :stock_dep,
                            stock_monbahia = :stock_monbahia,
                            stock_mtgbbps = :stock_mtgbbps,
                            stock_mundocab = :stock_mundocab,
                            stock_nqnshop = :stock_nqnshop,
                            stock_mtgcom = :stock_mtgcom,
                            stock_mtgroca = :stock_mtgroca,
                            stock_mundoroc = :stock_mundoroc,
                            last_update = SYSUTCDATETIME()
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": oid,
                        "stock_dep": _tot('DEP'),
                        "stock_mundoal": _tot('MUNDOAL'),
                        "stock_monbahia": _tot('MONBAHIA'),
                        "stock_mtgbbps": _tot('MTGBBPS'),
                        "stock_mundocab": _tot('MUNDOCAB'),
                        "stock_nqnshop": _tot('NQNSHOP'),
                        "stock_mtgcom": _tot('MTGCOM'),
                        "stock_mtgroca": _tot('MTGROCA'),
                        "stock_mundoroc": _tot('MUNDOROC'),
                    },
                )
                session.commit()
                updated += 1
                logger.info(f"🧩 Backfill stock por depósito actualizado para orden {r.order_id}")
            except Exception as e:
                logger.error(f"Error en backfill de {sku} (id={oid}): {e}")
                session.rollback()

    return updated


if __name__ == "__main__":
    # Test básico
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        print("🚀 Iniciando asignación de órdenes pendientes...")
        processed = assign_pending()
        print(f"✅ Procesadas: {processed} órdenes")
        # Completar columnas de stock por depósito para órdenes ya asignadas
        bf = backfill_stock_columns(max_rows=50)
        print(f"🧩 Backfill aplicado a: {bf} órdenes")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
