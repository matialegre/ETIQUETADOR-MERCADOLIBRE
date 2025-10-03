from fastapi import FastAPI, Depends, HTTPException, Query, Request, Security
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal
import os
import time
import pyodbc
from dotenv import load_dotenv
import json
import re
import requests
from .services import (
    get_orders_service,
    update_order_service,
    run_split_notifier_loop,
)
from .services import update_order_by_order_or_pack
from .services import _get_conn as _orders_conn, _col_exists as _orders_col_exists, TABLE as _ORDERS_TABLE  # reutilizar conexión/tabla
import threading

from .schemas import UpdateOrderRequest, OrdersResponse, UpdateOrderResponse, get_allowed_update_fields
from .services import get_default_fields as get_default_fields_for_orders

# Import note publisher
publish_note_upsert = None
try:
    import sys
    modules_path = os.path.join(os.path.dirname(__file__), '..', 'modules')
    if modules_path not in sys.path:
        sys.path.append(modules_path)
    import importlib.util
    spec = importlib.util.spec_from_file_location("note_publisher_10", os.path.join(modules_path, "10_note_publisher.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    publish_note_upsert = module.publish_note_upsert
    print(f"✓ 10_note_publisher importado exitosamente desde {modules_path}")
except ImportError as e:
    print(f"✗ Error importando 10_note_publisher: {e}")
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
        from modules.note_publisher_10 import publish_note_upsert
        print("✓ 10_note_publisher importado desde modules/")
    except ImportError as e2:
        print(f"✗ Error final importando 10_note_publisher: {e2}")
        publish_note_upsert = None

# ==== Importar helpers de Dragon (stock y movimientos) de forma dinámica ====
_dragon_get_stock = None
_dragon_choose_winner = None
_dragon_move = None
try:
    import importlib.util as _ilu
    _modules_root = os.path.join(os.path.dirname(__file__), '..', 'modules')
    # 07_dragon_api.get_stock_per_deposit
    _spec_dapi = _ilu.spec_from_file_location('modules.07_dragon_api', os.path.join(_modules_root, '07_dragon_api.py'))
    if _spec_dapi and _spec_dapi.loader:
        _mod_dapi = _ilu.module_from_spec(_spec_dapi)
        _spec_dapi.loader.exec_module(_mod_dapi)  # type: ignore[attr-defined]
        _dragon_get_stock = getattr(_mod_dapi, 'get_stock_per_deposit', None)
    # 07_assigner.choose_winner
    _spec_asg = _ilu.spec_from_file_location('modules.07_assigner', os.path.join(_modules_root, '07_assigner.py'))
    if _spec_asg and _spec_asg.loader:
        _mod_asg = _ilu.module_from_spec(_spec_asg)
        _spec_asg.loader.exec_module(_mod_asg)  # type: ignore[attr-defined]
        _dragon_choose_winner = getattr(_mod_asg, 'choose_winner', None)
    # 09_dragon_movement.move_stock_woo_to_woo
    _spec_mov = _ilu.spec_from_file_location('modules.09_dragon_movement', os.path.join(_modules_root, '09_dragon_movement.py'))
    if _spec_mov and _spec_mov.loader:
        _mod_mov = _ilu.module_from_spec(_spec_mov)
        _spec_mov.loader.exec_module(_mod_mov)  # type: ignore[attr-defined]
        _dragon_move = getattr(_mod_mov, 'move_stock_woo_to_woo', None)
except Exception as _imp_e:
    print(f"✗ Error importando módulos Dragon dinámicos: {_imp_e}")

# Cargar variables desde config/.env explícitamente
_proj_root = os.path.dirname(os.path.dirname(__file__))
_env_path = os.path.join(_proj_root, "config", ".env")
try:
    load_dotenv(_env_path, override=True)
except Exception:
    load_dotenv()

# Prefer OpenRouter for LLM if model/messages are provided
def _sanitize_or_key(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None


def _resolve_numeric_order_id(order_id_raw: str) -> int:
    """Resuelve un order_id numérico a partir de un identificador textual.
    Intenta cast directo; si falla, busca en DB por order_id o pack_id.
    """
    # 1) Cast directo
    try:
        return int(str(order_id_raw))
    except Exception:
        pass
    # 2) Lookup por order_id/pack_id en la misma tabla que usan los servicios
    try:
        with _orders_conn() as cn:  # usa acc1 por default
            cur = cn.cursor()
            cur.execute(
                f"SELECT TOP 1 id FROM {_ORDERS_TABLE} WHERE [order_id] = ? OR [pack_id] = ?",
                order_id_raw, order_id_raw,
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
    except Exception:
        pass
    raise HTTPException(status_code=400, detail="order_id inválido")
    val = (raw or "").strip().strip('"').strip("'")
    # Si vienen comandos pegados (p.ej. '; setx ...'), extraer solo el token sk-or-*
    m = re.search(r"(sk-or-v1-[A-Za-z0-9]+)", val)
    if m:
        return m.group(1)
    return val if val.startswith("sk-or-") else None


def _get_openrouter_key() -> Optional[str]:
    # 1) Preferir archivo para evitar contaminación de entorno
    try:
        here = os.path.dirname(__file__)
        p = os.path.join(here, "openrouter_key.txt")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                t = _sanitize_or_key(f.read())
                if t:
                    return t
    except Exception:
        pass
    # 2) Fallback: variable de entorno, saneada
    key = _sanitize_or_key(os.getenv("OPENROUTER_API_KEY"))
    if key:
        return key
    return None

app = FastAPI(
    title="MEGA API MUNDO OUTDOOR",
    version="1.0.0",
    debug=True,
    description=(
        "API unificada para consultar y gestionar órdenes (orders_meli).\n\n"
        "Características principales:\n"
        "- GET /orders: devuelve órdenes con selección dinámica de campos (?fields=all o coma-separado).\n"
        "- Filtros: exactos (order_id, pack_id, sku, seller_sku, barcode, deposito_asignado, shipping_estado, shipping_subestado, etc.),\n"
        "  rangos de fecha (?desde, ?hasta en ISO), LIKEs (q_sku, q_barcode, q_comentario, q_title),\n"
        "  y extras (deposito_keywords=CSV contains, include_printed=0/1).\n"
        "- Orden, paginación y conteo total.\n"
        "- POST /orders/{order_id}: actualizar campos clave (deposito_asignado, COMENTARIO, mov_depo_*, ready_to_print, printed).\n"
        "- Endpoints auxiliares: /orders/columns, /orders/resolve-by-barcode, /orders/{id}/movement, /orders/{id}/printed-moved.\n\n"
        "Campos disponibles: se detectan desde la base. Usá ?fields=all o consultá /orders/columns.\n\n"
        "Cómo hablarle a la IA (POST /api/chat):\n"
        "- Pedir título de una orden: 'título de la orden 123456'\n"
        "- ¿Está impresa?: 'la orden 123456 está impresa?'\n"
        "- Impresos hoy: '¿cuántos paquetes se imprimieron hoy?'\n"
        "- Preparar hoy por depósito: '¿qué tengo que preparar hoy desde DEPO?'\n"
        "- Ventas por SKU: '¿cuántos se vendieron de NDPMB0E770AR048?'\n"
        "- Búsqueda por título: usar comillas, ej: 'mostrame ventas de \"zapatilla runner azul\"'\n"
    ),
)

security = HTTPBearer(auto_error=False)

BACKEND_TOKEN = os.getenv("SERVER_API_TOKEN")
_cors = os.getenv("SERVER_CORS_ORIGINS", "*")
origins = [o.strip() for o in _cors.split(",") if o.strip()]
SERVER_TZ = os.getenv("SERVER_TZ", "Argentina Standard Time")
PUBLISH_NOTE_ON_DEPO_CHANGE = str(os.getenv("PUBLISH_NOTE_ON_DEPO_CHANGE", "0")).lower() in ("1","true","yes")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if origins == ["*"] else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ===== Webhook persistence helpers & DB config =====
try:
    # Preferir la base de la app (orders_meli/meli_stock)
    from modules.config import SQLSERVER_APP_CONN_STR as _APP_CONN  # type: ignore
except Exception:
    _APP_CONN = os.getenv("SQLSERVER_APP_CONN_STR", "")
try:
    from modules.config import SQLSERVER_CONN_STR as _GEN_CONN  # type: ignore
except Exception:
    _GEN_CONN = os.getenv("SQLSERVER_CONN_STR", "")

# Multi-DB (acc1/acc2) para webhooks
# Por defecto, usar APP o GEN (acc1). Permitir override explícito por env para cada cuenta.
SQLSERVER_WEBHOOK_CONN_ACC1 = os.getenv("SQLSERVER_WEBHOOK_CONN_ACC1", _APP_CONN or _GEN_CONN or "")
SQLSERVER_WEBHOOK_CONN_ACC2 = os.getenv("SQLSERVER_WEBHOOK_CONN_ACC2", "")

# Mapeo de user_ids de ML que pertenecen a acc2 (CSV de enteros/strings)
_ACC2_UIDS_ENV = os.getenv("ML_USER_IDS_ACC2", "")
ML_USER_IDS_ACC2 = set([s.strip() for s in _ACC2_UIDS_ENV.split(",") if s.strip()])

def _pick_webhook_conn_for_user(user_id: Optional[int]) -> str:
    """Devuelve la cadena de conexión a usar según el user_id de ML.
    Si el user_id pertenece a acc2 (config ML_USER_IDS_ACC2), usar conn acc2 si está configurada.
    Caso contrario, acc1.
    """
    try:
        key = str(user_id) if user_id is not None else None
        if key and key in ML_USER_IDS_ACC2 and SQLSERVER_WEBHOOK_CONN_ACC2:
            return SQLSERVER_WEBHOOK_CONN_ACC2
    except Exception:
        pass
    return SQLSERVER_WEBHOOK_CONN_ACC1

_RE_RES_ID = re.compile(r"/(\d+)$")

def _extract_id_from_resource(resource: Optional[str]) -> Optional[int]:
    if not resource or not isinstance(resource, str):
        return None
    m = _RE_RES_ID.search(resource.strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def _normalize_meli_payload(raw: Any) -> Dict[str, Any]:
    """Acepta variantes de payload: plano (topic/resource/...) o envuelto bajo
    raw["request"]["json"] o raw["request"]["data"]. Devuelve un dict con las
    claves más comunes y el payload completo en 'payload'.
    """
    base: Dict[str, Any] = {}
    try:
        body = raw or {}
        # 1) Si ya viene plano
        if isinstance(body, dict) and ("topic" in body or "resource" in body or "user_id" in body):
            base = dict(body)
        else:
            # 2) Intentar desanidar
            req = body.get("request") if isinstance(body, dict) else None
            if isinstance(req, dict):
                if isinstance(req.get("json"), dict):
                    base = dict(req.get("json") or {})
                else:
                    data = req.get("data")
                    if isinstance(data, str):
                        try:
                            parsed = json.loads(data)
                            if isinstance(parsed, dict):
                                base = parsed
                        except Exception:
                            pass
        # 3) Campos esperados
        topic = base.get("topic")
        resource = base.get("resource")
        user_id = base.get("user_id")
        application_id = base.get("application_id")
        out = {
            "topic": topic,
            "resource": resource,
            "user_id": user_id,
            "application_id": application_id,
            "payload": body if isinstance(body, dict) else {"raw": body},
        }
        return out
    except Exception:
        return {"payload": raw}

def _insert_webhook_event(row: Dict[str, Any]) -> int:
    """Inserta evento en dbo.meli_webhook_events y devuelve el ID nuevo.
    Rutea a la base correspondiente (acc1/acc2) según user_id.
    """
    conn_str = _pick_webhook_conn_for_user(row.get("user_id"))
    if not conn_str:
        raise RuntimeError("SQLSERVER_WEBHOOK_CONN no configurado (acc1 o acc2)")
    conn = None
    try:
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dbo.meli_webhook_events
                (topic, resource, resource_id, user_id, application_id, status, attempts, payload_json,
                 remote_ip, request_headers_json)
            OUTPUT inserted.id
            VALUES (?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
            """,
            row.get("topic"),
            row.get("resource"),
            row.get("resource_id"),
            row.get("user_id"),
            row.get("application_id"),
            json.dumps(row.get("payload") or {}, ensure_ascii=False),
            row.get("remote_ip"),
            json.dumps(row.get("request_headers") or {}, ensure_ascii=False),
        )
        new_id = cur.fetchone()[0]
        conn.commit()
        return int(new_id)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

def _fast_deduct_if_needed(conn: pyodbc.Connection, order_id: int) -> None:
    """Si FAST_DEDUCT_ON_SALE está activo y la orden aún no tiene movimiento,
    intenta asignar y descontar stock inmediato (movimiento negativo) en MELI/WOO según config.
    """
    if not FAST_DEDUCT_ON_SALE:
        return
    try:
        cur = conn.cursor()
        # Cargar TODAS las filas de la orden (hay órdenes con múltiples líneas/item)
        cur.execute("SELECT * FROM dbo.orders_meli WHERE order_id = ? ORDER BY id ASC", order_id)
        rows = cur.fetchall() or []
        if not rows:
            return
        cols = [c[0] for c in cur.description]
        col_idx = {cols[i].lower(): i for i in range(len(cols))}

        def _col(name: str) -> bool:
            return name.lower() in col_idx

        def _get_from(r, name: str):
            i = col_idx.get(name.lower())
            return r[i] if i is not None else None

        # Idempotencia robusta: si CUALQUIER fila ya tiene señales de movimiento, NO volver a mover
        any_moved = False
        for r in rows:
            try:
                numero_mov = _get_from(r, 'numero_movimiento') if _col('numero_movimiento') else None
                mov_depo_num = _get_from(r, 'mov_depo_numero') if _col('mov_depo_numero') else None
                mov_hecho_val = None
                if _col('mov_depo_hecho'):
                    mov_hecho_val = _get_from(r, 'mov_depo_hecho')
                if mov_hecho_val is None and _col('movimiento_realizado'):
                    mov_hecho_val = _get_from(r, 'movimiento_realizado')
                numero_mov_txt = str(numero_mov).strip() if numero_mov is not None else ''
                mov_depo_num_txt = str(mov_depo_num).strip() if mov_depo_num is not None else ''
                mov_hecho_flag = int(mov_hecho_val or 0) == 1
                if numero_mov_txt or mov_depo_num_txt or mov_hecho_flag:
                    any_moved = True
                    break
            except Exception:
                # Ante cualquier problema de parseo, ser conservador y continuar revisando otras filas
                continue

        if any_moved:
            return  # ya hubo movimiento en alguna línea

        # Tomar datos base de la PRIMERA fila para ejecutar el movimiento (caso single-item)
        base = rows[0]
        sku = (_get_from(base, 'sku') if _col('sku') else None) or (_get_from(base, 'seller_sku') if _col('seller_sku') else None)
        if not sku:
            return
        try:
            qty_raw = (_get_from(base, 'qty') if _col('qty') else None) or (_get_from(base, 'quantity') if _col('quantity') else None) or 1
            qty = int(qty_raw)
            if qty < 1:
                qty = 1
        except Exception:
            qty = 1

        # Traer stock y elegir depósito ganador (si es posible)
        depot = None
        total = 0
        reserved = 0
        try:
            if callable(_dragon_get_stock):
                stock = _dragon_get_stock(str(sku), timeout=60)  # type: ignore[misc]
            else:
                stock = {}
            if callable(_dragon_choose_winner):
                cw = _dragon_choose_winner(stock, qty)  # type: ignore[misc]
            else:
                cw = None
            if cw:
                depot, total, reserved = cw
        except Exception:
            depot = None

        # Fallback: usar deposito_asignado si existe; si no, dejar None (el movimiento maneja default)
        if not depot:
            try:
                depo_val = _get_from(base, 'deposito_asignado') if _col('deposito_asignado') else None
                depot = str(depo_val or '').strip() or None
            except Exception:
                depot = None

        # Ejecutar movimiento (negativo) — dejar que el módulo derive OrigenDestino por MOVIMIENTO_TARGET
        if callable(_dragon_move):
            observacion = f"FAST_DEDUCT | order_id={order_id}"
            try:
                art_det = ''
                try:
                    art_det = str((_get_from(base, 'nombre') if _col('nombre') else None) or (_get_from(base, 'ARTICULO') if _col('ARTICULO') else '') or '')
                except Exception:
                    art_det = ''
                mv = _dragon_move(sku=str(sku), qty=int(qty), observacion=observacion, tipo=2, barcode=None, articulo_detalle=art_det)  # type: ignore[misc]
            except Exception as e:
                mv = {"ok": False, "error": str(e)}
        else:
            mv = {"ok": False, "error": "dragon_move not available"}

        # Persistir resultados si hay columnas
        numero = str(mv.get('numero')) if mv and (mv.get('numero') is not None) else ''
        ok = bool(mv.get('ok'))
        obs_fin = (observacion + (f" | numero_movimiento={numero}" if numero else '') + (f" | error={mv.get('error')}" if not ok else ''))
        sets = []
        args = []
        # movimiento_realizado
        try:
            cur2 = conn.cursor()
            if 'movimiento_realizado' in (c.lower() for c in cols):
                sets.append('[movimiento_realizado] = ?')
                args.append(1 if ok else 0)
            if 'fecha_movimiento' in (c.lower() for c in cols):
                sets.append('[fecha_movimiento] = CASE WHEN ?=1 THEN SYSUTCDATETIME() ELSE [fecha_movimiento] END')
                args.append(1 if ok else 0)
            if 'numero_movimiento' in (c.lower() for c in cols):
                sets.append('[numero_movimiento] = ?')
                args.append(numero[:100])
            if 'observacion_movimiento' in (c.lower() for c in cols):
                sets.append('[observacion_movimiento] = LEFT(?, 500)')
                args.append(obs_fin)
            if 'stock_reservado' in (c.lower() for c in cols):
                # Reservar lo que se descontó
                sets.append('[stock_reservado] = COALESCE([stock_reservado],0) + ?')
                args.append(int(qty))
            if depot and 'deposito_asignado' in (c.lower() for c in cols):
                sets.append('[deposito_asignado] = COALESCE([deposito_asignado], ? )')
                args.append(str(depot))
            if sets:
                sql = f"UPDATE dbo.orders_meli SET {', '.join(sets)} WHERE [order_id] = ?"
                args.append(order_id)
                cur2.execute(sql, *args)
                conn.commit()
        except Exception:
            pass
    except Exception:
        # No romper flujo de webhook por errores de fast-deduct
        pass

# Reversa automática: cuando la orden queda en cancelled y hubo un movimiento previo
def _reverse_if_cancelled(conn: pyodbc.Connection, order_id: int, substatus: Optional[str]) -> None:
    if not substatus or str(substatus).lower() != 'cancelled':
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT TOP 1 * FROM dbo.orders_meli WHERE order_id = ?", order_id)
        row = cur.fetchone()
        if not row:
            return
        cols = [c[0] for c in cur.description]
        idx = {cols[i].lower(): i for i in range(len(cols))}
        def col(name: str):
            i = idx.get(name.lower())
            return row[i] if i is not None else None
        # Ya hicimos reversa?
        if 'MOV_LOCAL_HECHO'.lower() in idx and int(col('MOV_LOCAL_HECHO') or 0) == 1:
            return
        # Hubo movimiento de salida previo?
        had_out = False
        if 'numero_movimiento'.lower() in idx and (col('numero_movimiento') and str(col('numero_movimiento')).strip()):
            had_out = True
        if 'movimiento_realizado'.lower() in idx and int(col('movimiento_realizado') or 0) == 1:
            had_out = True
        if 'mov_depo_numero'.lower() in idx and (col('mov_depo_numero') and str(col('mov_depo_numero')).strip()):
            had_out = True
        if not had_out:
            return
        sku = col('sku') or col('seller_sku')
        if not sku:
            return
        try:
            qty = int(col('qty') or col('quantity') or 1)
            if qty < 1:
                qty = 1
        except Exception:
            qty = 1
        # Ejecutar movimiento inverso (entrada)
        observacion = f"REVERSE_CANCELLED | order_id={order_id}"
        mv = {"ok": False}
        try:
            if callable(_dragon_move):
                mv = _dragon_move(sku=str(sku), qty=int(qty) * -1, observacion=observacion, tipo=1, barcode=None, articulo_detalle=str(col('nombre') or col('ARTICULO') or ''))  # qty<0 + tipo=1 fuerza entrada
            else:
                mv = {"ok": False, "error": "dragon_move not available"}
        except Exception as e:
            mv = {"ok": False, "error": str(e)}
        numero = str(mv.get('numero')) if mv and (mv.get('numero') is not None) else ''
        ok = bool(mv.get('ok'))
        obs_fin = observacion + (f" | numero_movimiento={numero}" if numero else '') + (f" | error={mv.get('error') or ''}" if not ok else '')
        # Persistir en MOV_LOCAL_* y ajustar reserva
        sets = []
        args = []
        if 'MOV_LOCAL_HECHO'.lower() in idx:
            sets.append('[MOV_LOCAL_HECHO] = ?'); args.append(1 if ok else 0)
        if 'MOV_LOCAL_NUMERO'.lower() in idx:
            sets.append('[MOV_LOCAL_NUMERO] = ?'); args.append(numero[:100])
        if 'MOV_LOCAL_OBS'.lower() in idx:
            sets.append('[MOV_LOCAL_OBS] = LEFT(?, 500)'); args.append(obs_fin)
        if 'stock_reservado'.lower() in idx:
            sets.append('[stock_reservado] = CASE WHEN (ISNULL([stock_reservado],0) >= ?) THEN [stock_reservado]-? ELSE 0 END')
            args.extend([int(qty), int(qty)])
        if sets:
            sql = f"UPDATE dbo.orders_meli SET {', '.join(sets)} WHERE [order_id] = ?"
            args.append(order_id)
            cur2 = conn.cursor(); cur2.execute(sql, *args); conn.commit()
    except Exception:
        # No bloquear webhook por errores de reversa
        pass
# ===================== Webhook background worker =====================
def _get_token_for_user(user_id: Optional[int]) -> Optional[str]:
    """Resuelve el access_token para un seller dado su user_id.
    Preferencias:
    1) config/token.json con mapping user_id -> access_token
    2) env var ML_ACCESS_TOKEN (fallback único)
    """
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "token.json")
        if os.path.isfile(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Formatos aceptados: {"user_tokens": {"209611492": {"access_token": "..."}, ...}}
            # o {"209611492": {"access_token": "..."}}
            key = str(user_id) if user_id is not None else None
            # Soporte para deshabilitar usuarios específicos
            try:
                disabled_list = []
                if isinstance(data, dict):
                    dl = data.get("disabled_user_ids")
                    if isinstance(dl, list):
                        disabled_list = [str(x) for x in dl]
                env_disabled = os.getenv("DISABLED_ML_USER_IDS", "")
                if env_disabled:
                    disabled_list += [x.strip() for x in env_disabled.split(",") if x.strip()]
                if key and key in disabled_list:
                    return None
            except Exception:
                pass
            if isinstance(data, dict) and key:
                if "user_tokens" in data and isinstance(data["user_tokens"], dict):
                    u = data["user_tokens"].get(key) or {}
                    tok = (u or {}).get("access_token")
                    if tok:
                        return tok
                # fallback directo
                u = data.get(key) or {}
                tok = (u or {}).get("access_token")
                if tok:
                    return tok
    except Exception:
        pass
    # Fallback único
    tok = os.getenv("ML_ACCESS_TOKEN")
    return tok or None

def _ml_get_order(order_id: int, token: str) -> Dict[str, Any]:
    url = f"https://api.mercadolibre.com/orders/{order_id}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()

def _ml_get_shipment(shipment_id: int, token: str) -> Dict[str, Any]:
    url = f"https://api.mercadolibre.com/shipments/{shipment_id}"
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()

def _orders_apply_update_from_ml(conn: pyodbc.Connection, order_id: int, shipping_id: Optional[int], status: Optional[str], substatus: Optional[str]) -> None:
    """Inserta/actualiza en dbo.orders_meli los campos de envío clave y marca WEBHOOK_VISTO=1.
    Hace upsert básico: si no existe la orden, inserta con mínimos; si existe, actualiza.
    """
    cur = conn.cursor()
    # 1) ¿Existe la orden?
    cur.execute("SELECT TOP 1 order_id, shipping_estado, shipping_subestado, printed FROM dbo.orders_meli WHERE order_id = ?", order_id)
    row = cur.fetchone()
    prev_estado = None
    prev_sub = None
    prev_printed = None
    if row:
        try:
            prev_estado = row[1]
            prev_sub = row[2]
            prev_printed = int(row[3]) if row[3] is not None else None
        except Exception:
            prev_estado = None
            prev_sub = None
            prev_printed = None
    # Derivar flags
    printed_flag = 1 if (substatus or "").lower() == "printed" else (prev_printed if prev_printed is not None else 0)
    ready_flag = 1 if (substatus or "").lower() == "ready_to_print" else 0
    # 2) Upsert
    if not row:
        # Insert mínima — asume que las columnas existen; si no, dejará error capturable por caller
        cur.execute(
            (
                "INSERT INTO dbo.orders_meli (order_id, shipping_id, shipping_estado, shipping_subestado, printed, ready_to_print, WEBHOOK_VISTO, "
                "WEBHOOK_ESTADO_ANTES, WEBHOOK_ESTADO_DESPUES, WEBHOOK_SUBESTADO_ANTES, WEBHOOK_SUBESTADO_DESPUES, date_created)\n"
                "VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?, NULL, ?, SYSUTCDATETIME())"
            ),
            order_id, shipping_id, status, substatus, printed_flag, ready_flag,
            status, substatus,
        )
    else:
        # Update + transición printed_at si corresponde
        new_estado = status if status is not None else prev_estado
        new_sub = substatus if substatus is not None else prev_sub
        # Aplicar update evitando sobreescribir con NULL
        cur.execute(
            (
                "UPDATE dbo.orders_meli SET "
                "shipping_id = COALESCE(?, shipping_id), "
                "shipping_estado = COALESCE(?, shipping_estado), "
                "shipping_subestado = COALESCE(?, shipping_subestado), "
                "printed = CASE WHEN ?=1 THEN 1 ELSE printed END, "
                "ready_to_print = CASE WHEN ?=1 THEN 1 ELSE 0 END, "
                "WEBHOOK_VISTO = 1, "
                "WEBHOOK_ESTADO_ANTES = ?, "
                "WEBHOOK_ESTADO_DESPUES = ?, "
                "WEBHOOK_SUBESTADO_ANTES = ?, "
                "WEBHOOK_SUBESTADO_DESPUES = ?, "
                "printed_at = CASE WHEN ?=1 AND (printed IS NULL OR printed=0) THEN SYSUTCDATETIME() ELSE printed_at END "
                "WHERE order_id = ?"
            ),
            shipping_id, status, substatus,
            1 if ((substatus or "").lower() == "printed") else 0,
            1 if ((substatus or "").lower() == "ready_to_print") else 0,
            prev_estado, new_estado,
            prev_sub, new_sub,
            1 if ((substatus or "").lower() == "printed") else 0,
            order_id,
        )
    conn.commit()

def _process_event_row(conn: pyodbc.Connection, ev: Dict[str, Any]) -> None:
    """Procesa un solo registro de dbo.meli_webhook_events ya bloqueado para procesamiento.
    """
    topic = (ev.get("topic") or "").lower()
    user_id = ev.get("user_id")
    resource_id = ev.get("resource_id")
    if not resource_id:
        raise RuntimeError("Evento sin resource_id")
    token = _get_token_for_user(user_id)
    if not token:
        raise RuntimeError(f"No hay token para user_id={user_id}")

    order_id: Optional[int] = None
    shipping_id: Optional[int] = None
    status: Optional[str] = None
    substatus: Optional[str] = None

    if topic in ("orders", "orders_v2"):
        order_id = int(resource_id)
        order = _ml_get_order(order_id, token)
        shipping = (order or {}).get("shipping") or {}
        shipping_id = shipping.get("id")
        if shipping_id:
            sh = _ml_get_shipment(int(shipping_id), token)
            status = (sh or {}).get("status")
            substatus = (sh or {}).get("substatus")
        _orders_apply_update_from_ml(conn, order_id, shipping_id, status, substatus)
        # Descuento rápido si aplica
        try:
            _fast_deduct_if_needed(conn, int(order_id))
        except Exception:
            pass
        # Reversa si quedó cancelada y hubo salida previa
        try:
            _reverse_if_cancelled(conn, int(order_id), substatus)
        except Exception:
            pass
    elif topic == "shipments":
        shipping_id = int(resource_id)
        sh = _ml_get_shipment(shipping_id, token)
        status = (sh or {}).get("status")
        substatus = (sh or {}).get("substatus")
        # Resolver order_id (puede venir en shipment->orders o shipment->order_id)
        order_id = None
        try:
            if isinstance(sh.get("orders"), list) and sh["orders"]:
                order_id = sh["orders"][0].get("id")
            elif sh.get("order_id"):
                order_id = sh.get("order_id")
        except Exception:
            order_id = None
        if order_id is None:
            # Fallback: no se puede actualizar sin order_id; solo continuar
            return
        _orders_apply_update_from_ml(conn, int(order_id), shipping_id, status, substatus)
        # Descuento rápido si aplica
        try:
            _fast_deduct_if_needed(conn, int(order_id))
        except Exception:
            pass
        # Reversa si quedó cancelada y hubo salida previa
        try:
            _reverse_if_cancelled(conn, int(order_id), substatus)
        except Exception:
            pass
    else:
        # Otros tópicos: por ahora ignorar
        return

def _poll_pending_webhooks(conn: pyodbc.Connection, batch_size: int = 20) -> int:
    """Toma un batch de eventos pending, los marca como processing y procesa.
    Devuelve cantidad procesada.
    """
    cur = conn.cursor()
    cur.execute(
        (
            "SELECT TOP (?) id, topic, resource_id, user_id FROM dbo.meli_webhook_events WITH (READPAST) "
            "WHERE status='pending' ORDER BY received_at ASC"
        ),
        batch_size,
    )
    rows = cur.fetchall() or []
    if not rows:
        return 0
    ids = [int(r[0]) for r in rows]
    # Marcar processing
    cur.execute(
        f"UPDATE dbo.meli_webhook_events SET status='processing', attempts=attempts+1 WHERE id IN ({','.join(['?']*len(ids))})",
        *ids,
    )
    conn.commit()
    # Procesar uno por uno
    processed = 0
    for r in rows:
        ev_id = int(r[0])
        ev = {"id": ev_id, "topic": r[1], "resource_id": r[2], "user_id": r[3]}
        try:
            _process_event_row(conn, ev)
            cur.execute("UPDATE dbo.meli_webhook_events SET status='done', processed_at=SYSUTCDATETIME(), error=NULL WHERE id=?", ev_id)
            processed += 1
        except Exception as e:
            cur.execute("UPDATE dbo.meli_webhook_events SET status='error', error=? WHERE id=?", str(e)[:800], ev_id)
        conn.commit()
    return processed

def _webhook_worker_loop(conn_str: str, interval_secs: int = 20):
    """Loop simple que procesa eventos pending a intervalos regulares en una base concreta.
    Tolerante a errores: nunca levanta excepciones hacia el hilo principal.
    """
    if not conn_str:
        return
    while True:
        try:
            conn = pyodbc.connect(conn_str)
            try:
                _ = _poll_pending_webhooks(conn, batch_size=25)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            # No matar el loop por errores transitorios (DB caída, etc.)
            pass
        time.sleep(max(5, int(interval_secs or 20)))

# Auth dependency must be defined before it's referenced in route signatures
def require_token(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)):
    if not BACKEND_TOKEN:
        return  # token disabled (dev only)
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = credentials.credentials
    if token != BACKEND_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.on_event("startup")
def _start_background_jobs():
    # Lanzar el notificador de 'DEBE_PARTIRSE' cada 60s en hilo daemon
    try:
        t = threading.Thread(target=run_split_notifier_loop, kwargs={"interval_secs": 60}, daemon=True)
        t.start()
    except Exception:
        # No bloquear inicio del server por errores en background
        pass
    # Lanzar workers de webhooks (acc1/acc2 según config)
    try:
        if SQLSERVER_WEBHOOK_CONN_ACC1:
            threading.Thread(target=_webhook_worker_loop, kwargs={"conn_str": SQLSERVER_WEBHOOK_CONN_ACC1, "interval_secs": 20}, daemon=True).start()
        if SQLSERVER_WEBHOOK_CONN_ACC2:
            threading.Thread(target=_webhook_worker_loop, kwargs={"conn_str": SQLSERVER_WEBHOOK_CONN_ACC2, "interval_secs": 20}, daemon=True).start()
    except Exception:
        # No bloquear el inicio si falla el worker
        pass

# Static GUI config (se monta más abajo para respetar precedencia de /ui/chat)
pkg_root = os.path.dirname(os.path.dirname(__file__))
client_dist = os.path.join(pkg_root, "client", "dist")
static_dir = os.path.join(os.path.dirname(__file__), "static")
serve_dir = client_dist if os.path.isdir(client_dist) else static_dir
if not os.path.isdir(serve_dir):
    os.makedirs(serve_dir, exist_ok=True)

# Servir assets de React (JS/CSS con hash) en /ui/assets
assets_dir = os.path.join(serve_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/ui/assets", StaticFiles(directory=assets_dir), name="ui-assets")

@app.get("/")
def root_redirect():
    # UI principal: React en /ui/
    return RedirectResponse(url="/ui/")


# Override de /ui/ para reescribir el link de "Chat con IA" a /chat-now sin tocar el build
@app.get("/ui/")
def ui_root_override():
    index_path = os.path.join(serve_dir, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Reemplazos conservadores
        html = html.replace("/ui/chat", "/chat-now")
        html = html.replace('href="/ui/chat"', 'href="/chat-now"')
        # Inyección defensiva: si React recrea el link, forzamos la redirección
        inject = """
        <script>(function(){
          var CHAT_OLD = '/ui/chat';
          var CHAT_NEW = '/chat-now';
          function isChatPath(p){ return typeof p==='string' && (p===CHAT_OLD || p.endsWith('/ui/chat')); }
          function redirect(){ if (location && isChatPath(location.pathname)) { location.replace(CHAT_NEW); } }
          function rewriteLinks(){ try{ document.querySelectorAll('a[href="/ui/chat"]').forEach(a=>{ a.setAttribute('href', CHAT_NEW); a.onclick=null; }); }catch(_){ }
          }
          // Intercept initial load
          redirect();
          // Intercept link clicks
          document.addEventListener('click', function(e){
            var a = e.target && e.target.closest ? e.target.closest('a') : null;
            if(a){ var href=a.getAttribute('href')||''; if(isChatPath(href)){ e.preventDefault(); window.location.href=CHAT_NEW; return false; } }
          }, true);
          // Monkey-patch History API
          try{
            var _push=history.pushState, _replace=history.replaceState;
            history.pushState=function(state, title, url){ if(isChatPath(url)) { window.location.href=CHAT_NEW; return; } return _push.apply(this, arguments); };
            history.replaceState=function(state, title, url){ if(isChatPath(url)) { window.location.replace(CHAT_NEW); return; } return _replace.apply(this, arguments); };
          }catch(_){ }
          // Listen to route changes
          window.addEventListener('popstate', redirect);
          // Also rewrite any anchors that React might re-render
          document.addEventListener('DOMContentLoaded', rewriteLinks);
          window.addEventListener('load', rewriteLinks);
          setTimeout(rewriteLinks, 800);
          setInterval(rewriteLinks, 1500);
        })();</script>
        """
        if '</body>' in html:
            html = html.replace('</body>', inject + '</body>')
        else:
            html += inject
        return HTMLResponse(html)
    except Exception:
        # Si no existe, mantenemos comportamiento anterior
        return RedirectResponse(url="/ui-react/") if os.path.isdir(client_dist) else RedirectResponse(url="/ui-simple/")


# Catch-all: servir index.html para subrutas de /ui (sin punto) para soportar F5 en React Router
@app.get("/ui/{rest:path}")
def ui_catch_all(rest: str):
    # Si parece un asset (tiene punto), dejar que StaticFiles responda 404 o el asset real
    if "." in (rest or ""):
        # Devolver 404 explícito para que StaticFiles lo maneje
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    index_path = os.path.join(serve_dir, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("/ui/chat", "/chat-now").replace('href="/ui/chat"', 'href="/chat-now"')
        inject = """
        <script>(function(){var CHAT_OLD='/ui/chat',CHAT_NEW='/chat-now';function isChatPath(p){return typeof p==='string'&&(p===CHAT_OLD||p.endsWith('/ui/chat'));}function redirect(){if(location&&isChatPath(location.pathname)){location.replace(CHAT_NEW);}}redirect();})();</script>
        """
        if '</body>' in html:
            html = html.replace('</body>', inject + '</body>')
        else:
            html += inject
        return HTMLResponse(html)
    except Exception:
        return JSONResponse({"detail": "Not Found"}, status_code=404)

# Redirección para compatibilidad: el botón actual apunta a /ui/chat
@app.get("/ui/chat")
def redirect_ui_chat():
    return RedirectResponse(url="/chat-now")

# Variantes: con barra final y subrutas
@app.get("/ui/chat/")
def redirect_ui_chat_slash():
    return RedirectResponse(url="/chat-now")

@app.get("/ui/chat/{rest:path}")
def redirect_ui_chat_rest(rest: str):
    return RedirectResponse(url="/chat-now")


# Alias directo para evitar cualquier conflicto de caché/rutas con StaticFiles
@app.get("/chat-now", response_class=HTMLResponse)
def ui_chat_page_alias():
    """UI de Chat reconstruida desde cero con panel de tips a la izquierda.
    No requiere rebuild de React; es una página simple servida por FastAPI.
    """
    mode_label = "LLM activo" if _get_openrouter_key() else "reglas locales (sin LLM)"
    html = """
    <!doctype html>
    <html lang=\"es\">
      <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
        <title>CHATBASE · Chat IA</title>
        <style>
          body{margin:0;font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;background:#0b0b0c;color:#e5e7eb}
          header{display:flex;align-items:center;gap:12px;padding:12px 16px;background:#111214;border-bottom:1px solid #2a2a2e}
          header h1{font-size:16px;margin:0;color:#7ee787}
          .wrap{display:grid;grid-template-columns:340px 1fr;gap:12px;padding:12px}
          .card{background:#0f0f12;border:1px solid #2a2a2e;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.25)}
          .tips{padding:10px;max-height:calc(100vh - 100px);overflow:auto}
          .tips h3{margin:6px 0 10px 0;font-size:14px;color:#cdd6f4}
          .tip{border:1px dashed #3a3a40;border-radius:8px;padding:8px;margin-bottom:8px;background:#0b0b0f}
          .tip pre{white-space:pre-wrap;word-break:break-word;margin:0;color:#e5e7eb;font-size:12px}
          .tip .row{display:flex;gap:6px;margin-top:6px}
          .tip button{font-size:12px;background:#1f6feb;color:#fff;border:none;border-radius:6px;padding:4px 8px;cursor:pointer}
          .tip button.secondary{background:#30363d}
          .chat{display:flex;flex-direction:column;min-height:calc(100vh - 100px)}
          .conf{padding:10px;border-bottom:1px solid #2a2a2e;display:flex;gap:8px;align-items:center}
          .conf input{flex:1;background:#0b0b0f;border:1px solid #2a2a2e;border-radius:8px;padding:6px 8px;color:#e5e7eb}
          .conf button{background:#238636;color:#fff;border:none;border-radius:8px;padding:6px 10px;cursor:pointer}
          .box{flex:1;overflow:auto;padding:10px}
          .msg{max-width:85%;padding:8px 10px;border-radius:10px;margin:6px 0}
          .user{background:#1f2d3a;margin-left:auto}
          .assistant{background:#1f1f24}
          .input{display:flex;gap:8px;padding:10px;border-top:1px solid #2a2a2e}
          .input input{flex:1;background:#0b0b0f;border:1px solid #2a2a2e;border-radius:8px;padding:8px 10px;color:#e5e7eb}
          .input button{background:#1f6feb;color:#fff;border:none;border-radius:8px;padding:8px 12px;cursor:pointer}
          @media (max-width: 900px){.wrap{grid-template-columns:1fr}}
        </style>
      </head>
      <body>
        <header>
          <h1>CHATBASE · Chat IA</h1>
          <span style=\"margin-left:8px;color:#9aa4b2;font-size:12px\">Modo: __MODE_LABEL__</span>
          <a href=\"/ui/\" style=\"color:#9cdcfe;text-decoration:none\">Volver a la UI</a>
        </header>
        <div class=\"wrap\">
          <aside class=\"card tips\">
            <h3>Ejemplos listos para usar</h3>
            <div id=\"tips\"></div>
            <h3 style=\"margin-top:14px\">Comentarios rápidos</h3>
            <div id=\"comentarios\"></div>
          </aside>
          <main class=\"card chat\">
            <div class=\"conf\">
              <input id=\"token\" placeholder=\"SERVER_API_TOKEN (opcional)\" />
              <button id=\"save\">Guardar token</button>
            </div>
            <div id=\"box\" class=\"box\"></div>
            <div class=\"input\">
              <input id=\"q\" placeholder=\"Escribí tu pregunta...\" />
              <button id=\"send\">Enviar</button>
            </div>
          </main>
        </div>
        <script>
          (function(){
            const $ = (id)=>document.getElementById(id);
            function getToken(){ try{return localStorage.getItem('SERVER_API_TOKEN')||'';}catch(_){return ''} }
            function setToken(v){ try{localStorage.setItem('SERVER_API_TOKEN', v||'');}catch(_){}}
            function msg(role,text){ const div=document.createElement('div'); div.className='msg '+role; div.textContent=text; $('box').appendChild(div); $('box').scrollTop=$('box').scrollHeight; }
            async function loadTips(){
              const headers={}; const tok=getToken(); if(tok) headers['Authorization']='Bearer '+tok;
              let tips=[]; try{ const r=await fetch('/api/chat/tips',{headers}); if(r.ok){ const j=await r.json(); tips = Array.isArray(j.tips)? j.tips:[]; } }catch(_){ }
              if(!tips.length){ tips=[
                'la orden 123456 está impresa?',
                '¿qué tengo que preparar hoy desde DEPO?',
                '¿cuántos se vendieron de NDPMB0E770AR048?',
                'ventas entre 2025-08-10 y 2025-08-15',
                'mostrame ventas de "zapatilla runner azul"',
                'resolver por código de barras 7790000000000',
              ]; }
              const cont=$('tips'); cont.innerHTML='';
              tips.forEach(t=>{ const wrap=document.createElement('div'); wrap.className='tip'; const pre=document.createElement('pre'); pre.textContent=t; const row=document.createElement('div'); row.className='row';
                const b1=document.createElement('button'); b1.textContent='Copiar'; b1.onclick=async()=>{ try{await navigator.clipboard.writeText(t); b1.textContent='Copiado'; setTimeout(()=>b1.textContent='Copiar',1200);}catch(_){}};
                const b2=document.createElement('button'); b2.textContent='Pegar en input'; b2.className='secondary'; b2.onclick=()=>{ $('q').value=t; $('q').focus(); };
                row.appendChild(b1); row.appendChild(b2); wrap.appendChild(pre); wrap.appendChild(row); cont.appendChild(wrap);
              });
            }
            async function send(){
              const text=$('q').value.trim(); if(!text) return; $('q').value=''; msg('user', text);
              const headers={'Content-Type':'application/json'}; const tok=getToken(); if(tok) headers['Authorization']='Bearer '+tok;
              const model='deepseek/deepseek-chat';
              const payload={
                model,
                messages:[
                  {role:'system', content:'Sos un asistente de inventario MELI.'},
                  {role:'user', content:text}
                ]
              };
              try{
                const r=await fetch('/api/chat',{method:'POST',headers,body:JSON.stringify(payload)});
                if(!r.ok){ msg('assistant', 'Error '+r.status); return; }
                const j=await r.json();
                const content = (j && j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content) || j.answer || JSON.stringify(j);
                msg('assistant', content || '(sin respuesta)');
              }catch(e){ msg('assistant', 'Error de red'); }
            }
            function loadComentarios(){
              const presets = [
                'Hola! Gracias por tu compra. Estamos preparando tu envío. 😉',
                'Tu pedido ya está listo y será despachado en las próximas horas. 🚚',
                'Nos quedamos sin stock de esta variante. ¿Preferís cambio de color/talle o devolución?',
                'Coordinamos retiro por sucursal. Te avisamos cuando esté disponible. 🏬',
                'En breve te compartimos el número de seguimiento. ¡Gracias!',
                'Estamos chequeando disponibilidad en depósito. Te confirmamos apenas tengamos respuesta.',
              ];
              const cont = $('comentarios'); if(!cont) return; cont.innerHTML='';
              presets.forEach(t=>{
                const wrap=document.createElement('div'); wrap.className='tip';
                const pre=document.createElement('pre'); pre.textContent=t;
                const row=document.createElement('div'); row.className='row';
                const b1=document.createElement('button'); b1.textContent='Copiar'; b1.onclick=async()=>{ try{await navigator.clipboard.writeText(t); b1.textContent='Copiado'; setTimeout(()=>b1.textContent='Copiar',1200);}catch(_){}};
                const b2=document.createElement('button'); b2.textContent='Pegar en input'; b2.className='secondary'; b2.onclick=()=>{ $('q').value=t; $('q').focus(); };
                row.appendChild(b1); row.appendChild(b2); wrap.appendChild(pre); wrap.appendChild(row); cont.appendChild(wrap);
              });
            }
            $('token').value=getToken(); $('save').onclick=()=>{ setToken($('token').value||''); loadTips(); };
            $('send').onclick=send; $('q').addEventListener('keydown',e=>{ if(e.key==='Enter') send(); });
            loadTips();
            loadComentarios();
          })();
        </script>
      </body>
    </html>
    """
    html = html.replace("__MODE_LABEL__", mode_label)
    return HTMLResponse(html)


# Montajes estáticos (después de definir /ui/chat para que no lo tape StaticFiles)
app.mount("/ui", StaticFiles(directory=serve_dir, html=True), name="static")
app.mount("/ui-simple", StaticFiles(directory=static_dir, html=True), name="static_simple")
if os.path.isdir(client_dist):
    app.mount("/ui-react", StaticFiles(directory=client_dist, html=True), name="static_react")


@app.get("/debug/which-ui")
def debug_which_ui():
    """Devuelve qué carpeta está sirviendo FastAPI en /ui y /ui-simple"""
    return {
        "ui_mounted": serve_dir,
        "ui_simple_mounted": static_dir,
        "exists_client_dist": os.path.isdir(client_dist),
        "exists_static": os.path.isdir(static_dir),
        "note": "Abrí /ui-simple/ para ver la versión estática con panel de tips a la izquierda."
    }

# ===================== Webhooks MercadoLibre =====================
@app.post("/meli/callback")
async def meli_callback(req: Request):
    """Recibe webhooks de MercadoLibre, persiste y responde 200 ASAP."""
    try:
        body = await req.json()
    except Exception:
        body = {}
    normalized = _normalize_meli_payload(body)
    topic = normalized.get("topic")
    resource = normalized.get("resource")
    user_id = normalized.get("user_id")
    application_id = normalized.get("application_id")
    res_id = _extract_id_from_resource(resource)

    row = {
        "topic": topic,
        "resource": resource,
        "resource_id": res_id,
        "user_id": user_id,
        "application_id": application_id,
        "payload": normalized.get("payload") or body,
        "remote_ip": getattr(req.client, 'host', None),
        "request_headers": {k: v for k, v in req.headers.items()},
    }
    ev_id = None
    try:
        ev_id = _insert_webhook_event(row)
    except Exception as e:
        # No bloquear el ACK por errores de DB; informar mínimamente
        return JSONResponse({"ok": True, "stored": False, "error": str(e)}, status_code=200)
    return JSONResponse({"ok": True, "stored": True, "event_id": ev_id}, status_code=200)

@app.api_route("/meli/oauth/callback", methods=["GET", "POST"])
async def meli_oauth_callback(request: Request):
    """Callback OAuth (dummy) para compatibilidad y pruebas."""
    if request.method == "GET":
        qs = dict(request.query_params)
        return JSONResponse({"ok": True, "method": "GET", "query": qs})
    try:
        body = await request.json()
    except Exception:
        body = {}
    # Persistimos también los POST que llegan acá para auditoría
    normalized = _normalize_meli_payload(body)
    topic = normalized.get("topic") or "oauth"
    resource = normalized.get("resource")
    res_id = _extract_id_from_resource(resource)
    row = {
        "topic": topic,
        "resource": resource,
        "resource_id": res_id,
        "user_id": normalized.get("user_id"),
        "application_id": normalized.get("application_id"),
        "payload": normalized.get("payload") or body,
        "remote_ip": getattr(request.client, 'host', None),
        "request_headers": {k: v for k, v in request.headers.items()},
    }
    ev_id = None
    try:
        ev_id = _insert_webhook_event(row)
        return JSONResponse({
            "ok": True,
            "method": "POST",
            "stored": True,
            "event_id": ev_id,
            "topic": topic,
            "resource": resource,
        })
    except Exception as e:
        return JSONResponse({
            "ok": True,
            "method": "POST",
            "stored": False,
            "error": str(e),
        })

# ===================== NUEVA API: contrato máximo para GUI =====================

def _orders_example_payload():
    return {
        "page": 1,
        "page_size": 200,
        "total": 2,
        "orders": [
            {
                "id": "2000012677212350",
                "order_id": "2000012677212350",
                "date_created": "2025-08-14T12:34:56Z",
                "date_closed": "2025-08-14T13:05:30Z",
                "buyer": {"id": 123456789, "nickname": "COMPRADOR123"},
                "pack_id": "2000008866592129",
                "shipping_id": 5550001,
                "shipping_status": "ready_to_ship",
                "shipping_substatus": "ready_to_print",
                "notes": "MONBAHIA",
                "is_consolidated_pack": True,
                "printed": 0,
                "ready_to_print": 1,
                "extra": {
                    "COMENTARIO": "Entrega rápida. Revisar talle.",
                    "mov_depo_hecho": 0,
                    "mov_depo_numero": None,
                    "mov_depo_obs": None,
                    "asignacion_detalle": "Asignado a MONBAHIA",
                },
                "amounts": {
                    "subtotal": 12345.67,
                    "shipping": 0,
                    "discounts": 0,
                    "total": 12345.67,
                    "currency": "ARS",
                },
                "items": [
                    {
                        "title": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "nombre": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "quantity": 1,
                        "barcode": "7790000000000",
                        "seller_sku": "TRIVOR-M-NEGRO-XL",
                        "sku": "TRIVOR-M-NEGRO-XL",
                        "item": {
                            "id": "MLA1000001",
                            "variation_id": "2001001",
                            "seller_sku": "TRIVOR-M-NEGRO-XL",
                            "seller_custom_field": "TRIVOR-M-NEGRO-XL",
                            "variation_attributes": [
                                {"id": "TALLE", "value_name": "XL"},
                                {"id": "COLOR", "value_name": "NEGRO"},
                            ],
                        },
                        "variation_attributes": [
                            {"id": "TALLE", "value_name": "XL"},
                            {"id": "COLOR", "value_name": "NEGRO"},
                        ],
                        "attributes": {"TALLE": "XL", "COLOR": "NEGRO"},
                    },
                    {
                        "title": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "nombre": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "quantity": 1,
                        "barcode": "7790000000001",
                        "seller_sku": "TRIVOR-M-NEGRO-L",
                        "sku": "TRIVOR-M-NEGRO-L",
                        "item": {
                            "id": "MLA1000001",
                            "variation_id": "2001002",
                            "seller_sku": "TRIVOR-M-NEGRO-L",
                            "seller_custom_field": "TRIVOR-M-NEGRO-L",
                            "variation_attributes": [
                                {"id": "TALLE", "value_name": "L"},
                                {"id": "COLOR", "value_name": "NEGRO"},
                            ],
                        },
                        "variation_attributes": [
                            {"id": "TALLE", "value_name": "L"},
                            {"id": "COLOR", "value_name": "NEGRO"},
                        ],
                        "attributes": {"TALLE": "L", "COLOR": "NEGRO"},
                    },
                ],
                "order_items": [
                    {
                        "title": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "nombre": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "quantity": 1,
                        "barcode": "7790000000000",
                        "seller_sku": "TRIVOR-M-NEGRO-XL",
                        "item": {
                            "id": "MLA1000001",
                            "variation_id": "2001001",
                            "variation_attributes": [
                                {"id": "TALLE", "value_name": "XL"},
                                {"id": "COLOR", "value_name": "NEGRO"},
                            ],
                        },
                        "variation_attributes": [
                            {"id": "TALLE", "value_name": "XL"},
                            {"id": "COLOR", "value_name": "NEGRO"},
                        ],
                    },
                    {
                        "title": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "nombre": "Campera De Hombre Trivor Montagne Impermeable Ski Snow",
                        "quantity": 1,
                        "barcode": "7790000000001",
                        "seller_sku": "TRIVOR-M-NEGRO-L",
                        "item": {
                            "id": "MLA1000001",
                            "variation_id": "2001002",
                            "variation_attributes": [
                                {"id": "TALLE", "value_name": "L"},
                                {"id": "COLOR", "value_name": "NEGRO"},
                            ],
                        },
                        "variation_attributes": [
                            {"id": "TALLE", "value_name": "L"},
                            {"id": "COLOR", "value_name": "NEGRO"},
                        ],
                    },
                ],
            },
            {
                "id": "2000013000000001",
                "order_id": "2000013000000001",
                "date_created": "2025-08-15T10:22:11Z",
                "buyer": "comprador_sin_objeto",
                "pack_id": None,
                "shipping_id": 5550002,
                "shipping_status": "ready_to_ship",
                "shipping_substatus": "printed",
                "notes": "DEPO",
                "is_consolidated_pack": False,
                "printed": 1,
                "ready_to_print": 0,
                "extra": {
                    "COMENTARIO": "Pickeado y etiquetado",
                    "mov_depo_hecho": 1,
                    "mov_depo_numero": "DG-000123",
                    "mov_depo_obs": "Despachado",
                    "asignacion_detalle": "Asignado a DEPO",
                },
                "items": [
                    {
                        "title": "Zapatilla Running Pro Max Ultraliviana Air Mesh",
                        "nombre": "Zapatilla Running Pro Max Ultraliviana Air Mesh",
                        "quantity": 1,
                        "barcode": "7799999999999",
                        "seller_sku": "RUNPRO-BL-41",
                        "item": {
                            "id": "MLA2002002",
                            "variation_id": "3003003",
                            "variation_attributes": [
                                {"id": "TALLE", "value_name": "41 AR"},
                                {"id": "COLOR", "value_name": "Azul"},
                            ],
                        },
                        "variation_attributes": [
                            {"id": "TALLE", "value_name": "41 AR"},
                            {"id": "COLOR", "value_name": "Azul"},
                        ],
                        "attributes": {"TALLE": "41 AR", "COLOR": "Azul"},
                    }
                ],
                "order_items": [
                    {
                        "title": "Zapatilla Running Pro Max Ultraliviana Air Mesh",
                        "nombre": "Zapatilla Running Pro Max Ultraliviana Air Mesh",
                        "quantity": 1,
                        "barcode": "7799999999999",
                        "seller_sku": "RUNPRO-BL-41",
                        "item": {
                            "id": "MLA2002002",
                            "variation_id": "3003003",
                            "variation_attributes": [
                                {"id": "TALLE", "value_name": "41 AR"},
                                {"id": "COLOR", "value_name": "Azul"},
                            ],
                        },
                        "variation_attributes": [
                            {"id": "TALLE", "value_name": "41 AR"},
                            {"id": "COLOR", "value_name": "Azul"},
                        ],
                    }
                ],
            },
        ],
    }


@app.get("/orders-example")
def get_orders_contract(
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, alias="limit"),
    desde: Optional[str] = Query(None, alias="from"),
    hasta: Optional[str] = Query(None, alias="to"),
    include_printed: int = Query(1),
    deposito_keywords: Optional[str] = None,
):
    # Ejemplo máximo del contrato (solo demo). No usar en producción.
    payload = _orders_example_payload()
    payload["page"] = page
    payload["page_size"] = page_size
    return JSONResponse(payload)


@app.get("/orders-example/resolve-by-barcode")
def resolve_by_barcode_example(barcode: str):
    # Usamos la primera orden del ejemplo como base
    base = _orders_example_payload()["orders"][0]
    out = {
        "order_id": base["order_id"],
        "pack_id": base["pack_id"],
        "shipping_id": base["shipping_id"],
        "printed": base["printed"],
        "notes": base["notes"],
        "extra": base["extra"],
        "items": base["items"][:1],
    }
    return JSONResponse(out)


@app.post("/orders/{order_id}/printed-moved", response_model=UpdateOrderResponse)
def printed_moved(order_id: str, body: Dict[str, Any], _=Depends(require_token)):
    """Marca impreso y movimiento en una sola llamada.
    Acepta adicionalmente shipping_estado y shipping_subestado.
    """
    # Filtrar campos permitidos
    allowed = set(get_allowed_update_fields())
    payload: Dict[str, Any] = {}
    for k in (
        "printed",
        "mov_depo_hecho",
        "mov_depo_numero",
        "tracking_number",
        "mov_depo_obs",
        # Movimiento LOCAL (nuevo)
        "MOV_LOCAL_HECHO",
        "MOV_LOCAL_NUMERO",
        "MOV_LOCAL_OBS",
        # Otros
        "asignacion_detalle",
        "shipping_estado",
        "shipping_subestado",
        "ready_to_print",
        "deposito_asignado",
        "COMENTARIO",
        "CAMBIO_ESTADO",
    ):
        if k in body and body[k] is not None and k in allowed:
            payload[k] = body[k]
    # Forzar estado impreso y bandera de cambio de estado
    payload["printed"] = 1
    payload["shipping_subestado"] = "printed"
    payload["CAMBIO_ESTADO"] = 1
    # Normalizaciones defensivas para ints 0/1
    for flag in ("printed", "mov_depo_hecho", "ready_to_print", "CAMBIO_ESTADO"):
        if flag in payload:
            try:
                payload[flag] = 1 if int(payload[flag]) == 1 else 0
            except Exception:
                payload[flag] = 1 if str(payload[flag]).lower() in ("1", "true", "yes") else 0
    # Idempotencia server-side: si ya hay movimiento en alguna fila de la orden/pack, NO volver a setear mov_depo_*
    try:
        oid = _resolve_numeric_order_id(order_id)
        with _orders_conn() as cn:
            cur = cn.cursor()
            cur.execute("SELECT * FROM dbo.orders_meli WHERE [order_id] = ?", str(order_id))
            rows = cur.fetchall() or []
            if rows:
                cols = [c[0] for c in cur.description]
                idx = {cols[i].lower(): i for i in range(len(cols))}
                def g(r, name: str):
                    i = idx.get(name.lower()); return (r[i] if i is not None else None)
                movement_done = False
                for r in rows:
                    num1 = g(r, 'numero_movimiento') if 'numero_movimiento' in idx else None
                    num2 = g(r, 'mov_depo_numero') if 'mov_depo_numero' in idx else None
                    hecho = g(r, 'mov_depo_hecho') if 'mov_depo_hecho' in idx else None
                    if hecho is None and 'movimiento_realizado' in idx:
                        hecho = g(r, 'movimiento_realizado')
                    if (num1 and str(num1).strip()) or (num2 and str(num2).strip()) or int(hecho or 0) == 1:
                        movement_done = True
                        break
                if movement_done:
                    # Eliminar campos de movimiento del payload para evitar duplicar
                    for k in ("mov_depo_hecho", "mov_depo_numero", "mov_depo_obs", "MOV_LOCAL_HECHO", "MOV_LOCAL_NUMERO", "MOV_LOCAL_OBS"):
                        if k in payload:
                            payload.pop(k, None)
    except Exception:
        # No bloquear si el chequeo falla; seguimos sin eliminar payload
        pass
    # Construir modelo y ejecutar update para TODAS las filas de la orden/pack
    # Importante: actualizar por order_id/pack_id asegura consistencia en tablas con múltiples filas por orden
    upd = UpdateOrderRequest(**payload)
    affected = update_order_by_order_or_pack(str(order_id), upd)
    return {"ok": True, "affected": affected}


@app.post("/orders/{order_id}/movement", response_model=UpdateOrderResponse)
def movement_only(order_id: str, body: Dict[str, Any], _=Depends(require_token)):
    """Registra solo movimiento de depósito (packs incompletos), sin tocar printed."""
    allowed = set(get_allowed_update_fields())
    # Soporte especial: inicializar campos de movimiento en NULL al inicio del pick
    try:
        if isinstance(body, dict) and body.get("init_local_movement") in (1, True, "1", "true", "TRUE", "yes", "YES"):
            oid = _resolve_numeric_order_id(order_id)
            # Actualizar directamente las columnas a NULL si existen
            try:
                # Usar conexión principal (acc1) para este endpoint simple
                with _orders_conn() as cn:
                    cur = cn.cursor()
                    # Detectar qué columnas existen para evitar errores
                    cols_to_null = []
                    if _orders_col_exists("mov_depo_numero"):
                        cols_to_null.append("[mov_depo_numero] = NULL")
                    if _orders_col_exists("mov_depo_obs"):
                        cols_to_null.append("[mov_depo_obs] = NULL")
                    if _orders_col_exists("mov_depo_hecho"):
                        cols_to_null.append("[mov_depo_hecho] = NULL")
                    if not cols_to_null:
                        # Nada para actualizar
                        return {"ok": True, "affected": 0}
                    sql = f"UPDATE {_ORDERS_TABLE} SET {', '.join(cols_to_null)} WHERE [id] = ?"
                    cur.execute(sql, oid)
                    cn.commit()
                    return {"ok": True, "affected": cur.rowcount}
            except Exception as _e_init:
                # Continuar con flujo normal si falla; no romper
                pass
    except Exception:
        # No bloquear por errores de parsing de body
        pass
    # Idempotencia server-side: si ya hay movimiento, no volver a escribir
    try:
        with _orders_conn() as cn:
            c = cn.cursor()
            c.execute("SELECT * FROM dbo.orders_meli WHERE [order_id] = ?", str(order_id))
            rows = c.fetchall() or []
            if rows:
                cols = [d[0] for d in c.description]
                idx = {cols[i].lower(): i for i in range(len(cols))}
                def g(r, name: str):
                    i = idx.get(name.lower()); return (r[i] if i is not None else None)
                for r in rows:
                    num1 = g(r, 'numero_movimiento') if 'numero_movimiento' in idx else None
                    num2 = g(r, 'mov_depo_numero') if 'mov_depo_numero' in idx else None
                    hecho = g(r, 'mov_depo_hecho') if 'mov_depo_hecho' in idx else None
                    if hecho is None and 'movimiento_realizado' in idx:
                        hecho = g(r, 'movimiento_realizado')
                    if (num1 and str(num1).strip()) or (num2 and str(num2).strip()) or int(hecho or 0) == 1:
                        return {"ok": True, "affected": 0}
    except Exception:
        # Si falla el chequeo, continuar flujo normal
        pass
    keys = (
        "mov_depo_hecho",
        "mov_depo_numero",
        "tracking_number",
        "mov_depo_obs",
        # Movimiento LOCAL (nuevo)
        "MOV_LOCAL_HECHO",
        "MOV_LOCAL_NUMERO",
        "MOV_LOCAL_OBS",
        # Otros
        "asignacion_detalle",
    )
    payload: Dict[str, Any] = {k: body[k] for k in keys if k in body and body[k] is not None and k in allowed}
    if "mov_depo_hecho" in payload:
        try:
            payload["mov_depo_hecho"] = 1 if int(payload["mov_depo_hecho"]) == 1 else 0
        except Exception:
            payload["mov_depo_hecho"] = 1 if str(payload["mov_depo_hecho"]).lower() in ("1","true","yes") else 0
    # Actualizar todas las filas relacionadas a la orden/pack
    upd = UpdateOrderRequest(**payload)
    affected = update_order_by_order_or_pack(str(order_id), upd)
    return {"ok": True, "affected": affected}


 

    sample = _orders_example_payload()
    orders = sample.get("orders", [])
    lower = text.lower()

    import re as _re

    # Intent: resolver por código de barras
    if "codigo de barras" in lower or "código de barras" in lower or "barcode" in lower or lower.startswith("resolver "):
        m = _re.search(r"(\d{8,14})", text)
        if m and orders:
            bc = m.group(1)
            base = orders[0]
            ans = {
                "order_id": base.get("order_id"),
                "pack_id": base.get("pack_id"),
                "shipping_id": base.get("shipping_id"),
                "printed": base.get("printed"),
                "notes": base.get("notes"),
                "barcode": bc,
                "items": base.get("items", [])[:1],
            }
            return {"answer": json.dumps(ans, ensure_ascii=False)}

    # Intent: estado impresa de una orden
    if ("esta impresa" in lower or "está impresa" in lower) and "orden" in lower:
        m = _re.search(r"(\d{10,20})", text)
        if m:
            oid = m.group(1)
            o = next((x for x in orders if x.get("order_id") == oid), None)
            if o:
                return {"answer": f"La orden {oid} {'está' if o.get('printed') else 'no está'} impresa (printed={o.get('printed')})."}
            return {"answer": f"No encontré la orden {oid} en el ejemplo."}

    # Intent: marcar impresa la orden N
    if ("marcar" in lower or "poner" in lower) and ("impresa" in lower or "printed" in lower) and "orden" in lower:
        m = _re.search(r"(\d{10,20})", text)
        if m:
            oid = m.group(1)
            # Simulación: confirmamos acción
            return {"answer": f"OK, marqué impresa la orden {oid} (simulado)."}

    # Intent: listas para imprimir (RTP)
    if "listas para imprimir" in lower or "ready to print" in lower or "ready_to_print" in lower:
        rtp = [o for o in orders if o.get("ready_to_print") == 1]
        if rtp:
            lines = [f"{o.get('order_id')} (depo={o.get('notes','-')})" for o in rtp]
            return {"answer": "Órdenes listas para imprimir:\n" + "\n".join(lines)}
        return {"answer": "No hay órdenes RTP en el ejemplo."}

    # Intent: preparar hoy desde DEP/MUNDOROC/etc.
    if ("preparar hoy" in lower or "tengo que preparar" in lower) and ("desde" in lower or "de" in lower):
        depo = None
        m = _re.search(r"desde\s+([A-ZÁÉÍÓÚÑ0-9_-]+)", text, _re.IGNORECASE)
        if m:
            depo = m.group(1).upper()
        pick = [o for o in orders if depo is None or (o.get("notes","" ).upper()==depo)]
        if pick:
            ids = ", ".join(o.get("order_id") for o in pick)
            return {"answer": f"Para preparar hoy{(' en '+depo) if depo else ''}: {ids}"}
        return {"answer": f"No hay órdenes para preparar hoy{(' en '+depo) if depo else ''} en el ejemplo."}

    # Intent: búsqueda por título "..."
    m = _re.search(r'"([^"]{3,80})"', text)
    if m:
        q = m.group(1).lower()
        hits = []
        for o in orders:
            for it in o.get("items", []):
                title = (it.get("title") or "").lower()
                if q in title:
                    hits.append({"order_id": o.get("order_id"), "title": it.get("title"), "qty": it.get("quantity", 1)})
                    break
        if hits:
            return {"answer": "Coincidencias por título:\n" + "\n".join(f"- {h['order_id']}: {h['title']} (qty={h['qty']})" for h in hits)}
        return {"answer": f"Sin coincidencias de título que contengan '{q}' en el ejemplo."}

    # Intent: ventas del SKU X / ventas entre fechas (simples)
    if "ventas" in lower and ("sku" in lower or _re.search(r"\b\d{4}-[A-Z0-9]+", text, _re.IGNORECASE)):
        return {"answer": "Ventas para ese SKU en el ejemplo: 2 unidades (simulado)."}
    if "ventas entre" in lower:
        return {"answer": "Ventas en ese rango de fechas (ejemplo): 5 órdenes, 7 ítems (simulado)."}

    # Fallback: ayuda mínima
    help_text = (
        "Ejemplos: \n"
        "- 'resolver por código de barras 7790000000000'\n"
        "- 'la orden 2000012677212350 está impresa?'\n"
        "- 'marcar impresa la orden 2000012677212350'\n"
        "- 'qué órdenes están listas para imprimir?'\n"
        "- 'qué tengo que preparar hoy desde DEPO'\n"
        "- 'buscar órdenes con título \"campera softshell\"'\n"
    )
    return {"answer": help_text}

@app.get("/orders", response_model=OrdersResponse)
def list_orders(
    request: Request,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields or 'all'"),
    page: int = Query(1, ge=1),
    limit: int = Query(200, ge=1),
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query("DESC"),
    # Exact filters (documented)
    order_id: Optional[str] = Query(None),
    pack_id: Optional[str] = Query(None),
    sku: Optional[str] = Query(None),
    seller_sku: Optional[str] = Query(None),
    barcode: Optional[str] = Query(None),
    ARTICULO: Optional[str] = Query(None),
    COLOR: Optional[str] = Query(None),
    TALLE: Optional[str] = Query(None),
    display_color: Optional[str] = Query(None),
    deposito_asignado: Optional[str] = Query(None),
    _estado: Optional[str] = Query(None),
    meli_ad: Optional[str] = Query(None),
    venta_tipo: Optional[str] = Query(None),
    shipping_estado: Optional[str] = Query(None),
    shipping_subestado: Optional[str] = Query(None),
    agotamiento_flag: Optional[int] = Query(None),
    ready_to_print: Optional[int] = Query(None),
    printed: Optional[int] = Query(None),
    qty: Optional[int] = Query(None),
    # IN/keywords
    deposito_asignado_in: Optional[str] = Query(None, description="CSV of deposit codes for IN filter"),
    deposito_keywords: Optional[str] = Query(None, description="CSV of keywords for LIKE on deposito_asignado"),
    # Ranges
    desde: Optional[str] = Query(None, description="ISO date/time for date_created >="),
    hasta: Optional[str] = Query(None, description="ISO date/time for date_created <="),
    cerrado_desde: Optional[str] = Query(None, description="ISO date/time for date_closed >="),
    cerrado_hasta: Optional[str] = Query(None, description="ISO date/time for date_closed <="),
    # LIKEs
    q_sku: Optional[str] = Query(None),
    q_barcode: Optional[str] = Query(None),
    q_comentario: Optional[str] = Query(None),
    q_title: Optional[str] = Query(None, description="LIKE on nombre"),
    # Extra flags
    include_printed: Optional[int] = Query(1, description="0 to exclude printed=1, 1 to include"),
    acc: str = Query("acc1", regex="^acc1|acc2$", description="Cuenta/base de datos a usar: acc1 o acc2"),
    _=Depends(require_token),
):
    """Lista órdenes desde `orders_meli` con selección dinámica de columnas y filtros.

    Ejemplos:
    - /orders?fields=nombre&deposito_asignado_in=DEPO,MUNDOAL,MTGBBL,BBPS,MONBAHIA,MTGBBPS
    - /orders?fields=all&desde=2025-08-01&hasta=2025-08-18&include_printed=0
    """
    try:
        selected = None
        if fields:
            selected = [f.strip() for f in fields.split(",") if f.strip()]
        params: Dict[str, Any] = dict(request.query_params)
        items, total = get_orders_service(selected_fields=selected, params=params, acc=acc)
        return {"orders": items, "page": page, "limit": limit, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/{order_id}/movement-force-zero")
def force_local_movement_zero(order_id: str, body: Dict[str, Any] = {}, acc: str = Query("acc1", regex="^acc1|acc2$"), _=Depends(require_token)):
    """Emergency endpoint: fuerza MOV_LOCAL_HECHO=0 por order_id/pack_id.
    Opcionalmente actualiza MOV_LOCAL_NUMERO y MOV_LOCAL_OBS si se envían en body.
    No modifica MOV_LOCAL_TS.

    Body opcional:
      - MOV_LOCAL_NUMERO: str (para setear un valor específico)
      - MOV_LOCAL_OBS: str (para setear un valor específico)
    """
    try:
        from .services import list_orders_columns
        cols = set([c.lower() for c in (list_orders_columns(acc) or [])])
        sets: List[str] = []
        args: List[Any] = []

        if "mov_local_hecho" in cols:
            sets.append("[MOV_LOCAL_HECHO] = 0")
        # Opcionales desde body (no tocamos TS en este endpoint)
        try:
            if "mov_local_numero" in cols and body.get("MOV_LOCAL_NUMERO") is not None:
                sets.append("[MOV_LOCAL_NUMERO] = ?"); args.append(str(body.get("MOV_LOCAL_NUMERO"))[:100])
        except Exception:
            pass
        try:
            if "mov_local_obs" in cols and body.get("MOV_LOCAL_OBS") is not None:
                sets.append("[MOV_LOCAL_OBS] = LEFT(?, 500)"); args.append(str(body.get("MOV_LOCAL_OBS"))[:500])
        except Exception:
            pass
        if not sets:
            raise HTTPException(status_code=400, detail="MOV_LOCAL_* columns not present in target table")
        sql = f"UPDATE {_ORDERS_TABLE} SET {', '.join(sets)} WHERE [order_id] = ? OR [pack_id] = ?"
        args.extend([str(order_id), str(order_id)])
        with _orders_conn(acc) as cn:
            cur = cn.cursor()
            cur.execute(sql, *args)
            cn.commit()
            affected = cur.rowcount or 0
        return {"ok": True, "affected": affected}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/{order_id}/movement-force")
def force_local_movement(order_id: str, body: Dict[str, Any] = {}, acc: str = Query("acc1", regex="^acc1|acc2$"), _=Depends(require_token)):
    """Emergency endpoint: fuerza MOV_LOCAL_HECHO=1 por order_id/pack_id.
    Opcionalmente setea MOV_LOCAL_NUMERO y MOV_LOCAL_OBS si se envían.
    Sella MOV_LOCAL_TS si existe la columna.

    Body opcional:
      - MOV_LOCAL_NUMERO: str
      - MOV_LOCAL_OBS: str
    """
    try:
        from .services import list_orders_columns
        cols = set([c.lower() for c in (list_orders_columns(acc) or [])])
        sets: List[str] = []
        args: List[Any] = []

        if "mov_local_hecho" in cols:
            sets.append("[MOV_LOCAL_HECHO] = 1")
        if "mov_local_ts" in cols:
            # Sellar solo si está NULL, sino conservar
            sets.append("[MOV_LOCAL_TS] = COALESCE([MOV_LOCAL_TS], SYSUTCDATETIME())")
        # Opcionales desde body
        try:
            if "mov_local_numero" in cols and body.get("MOV_LOCAL_NUMERO") is not None:
                sets.append("[MOV_LOCAL_NUMERO] = ?"); args.append(str(body.get("MOV_LOCAL_NUMERO"))[:100])
        except Exception:
            pass
        try:
            if "mov_local_obs" in cols and body.get("MOV_LOCAL_OBS") is not None:
                sets.append("[MOV_LOCAL_OBS] = LEFT(?, 500)"); args.append(str(body.get("MOV_LOCAL_OBS"))[:500])
        except Exception:
            pass
        if not sets:
            raise HTTPException(status_code=400, detail="MOV_LOCAL_* columns not present in target table")
        sql = f"UPDATE {_ORDERS_TABLE} SET {', '.join(sets)} WHERE [order_id] = ? OR [pack_id] = ?"
        args.extend([str(order_id), str(order_id)])
        with _orders_conn(acc) as cn:
            cur = cn.cursor()
            cur.execute(sql, *args)
            cn.commit()
            affected = cur.rowcount or 0
        return {"ok": True, "affected": affected}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------
# OpenRouter Chat Backend
# -----------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _read_openrouter_key() -> Optional[str]:
    # 1) env var
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    # 2) local files
    candidates = [
        os.path.join(os.path.dirname(__file__), "openrouter_key.txt"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "openrouter_key.txt"),
    ]
    for p in candidates:
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    t = f.read().strip()
                    if t:
                        return t
        except Exception:
            pass
    return None


def _extract_hints_from_text(text: str) -> Dict[str, Any]:
    hints: Dict[str, Any] = {}
    if not text:
        return hints
    # Buscar posibles order_id grandes
    m = re.findall(r"\b\d{6,}\b", text)
    if m:
        # tomar el primero como order_id
        try:
            hints["order_id"] = int(m[0])
        except Exception:
            pass
    # Buscar posibles SKUs (con guiones/letras)
    msku = re.findall(r"[A-Z0-9]{2,}(?:-[A-Z0-9]+){0,3}", text, flags=re.IGNORECASE)
    if msku:
        hints["sku"] = msku[0]
    # Buscar posibles títulos entre comillas
    mtit = re.findall(r'"([^"]{3,})"|\'([^\']{3,})\'', text)
    # mtit es lista de tuplas por los dos grupos, elegir el no vacío
    for a,b in mtit:
        t = a or b
        if t and len(t.strip()) >= 3:
            hints["q_title"] = t.strip()
            break
    return hints


def _build_db_context(user_text: str, max_rows: int = 20) -> str:
    """Consulta algunos datos relevantes para adjuntar como contexto al LLM.
    Heurística simple: si detecta order_id o sku, filtra por eso; si no, devuelve últimas órdenes.
    """
    try:
        hints = _extract_hints_from_text(user_text or "")
        params: Dict[str, Any] = {"page": 1, "limit": max_rows, "sort_by": "id", "sort_dir": "DESC"}
        if "order_id" in hints:
            params["order_id"] = hints["order_id"]
        elif "sku" in hints:
            params["q_sku"] = hints["sku"]
        elif "q_title" in hints:
            params["q_title"] = hints["q_title"]

        # Seleccionar columnas compactas
        fields = [
            c for c in [
                "order_id","pack_id","sku","seller_sku","qty","date_created",
                "shipping_estado","shipping_subestado","deposito_asignado","ready_to_print","printed","COMENTARIO","nombre"
            ] if c in get_default_fields() or True
        ]
        items, total = get_orders_service(selected_fields=fields, params=params)
        # Armar texto tabular simple
        lines = ["Contexto de orders_meli (" + str(total) + " total, mostrando hasta " + str(max_rows) + "):"]
        for it in items:
            lines.append(
                f"order_id={it.get('order_id')} pack_id={it.get('pack_id')} sku={it.get('sku')} title={it.get('nombre') or ''} qty={it.get('qty')} dep_asig={it.get('deposito_asignado')} ship={it.get('shipping_estado')}/{it.get('shipping_subestado')} rtp={it.get('ready_to_print')} printed={it.get('printed')} comentario={it.get('COMENTARIO')}"
            )
        return "\n".join(lines[: max_rows + 1])
    except Exception as e:
        return f"(No se pudo obtener contexto de la base: {e})"


def _normalize_estado(text: str) -> Optional[str]:
    t = (text or "").strip().lower()
    mapping = {
        "pagado": "paid",
        "paid": "paid",
        "cancelado": "cancelled",
        "cancelled": "cancelled",
    }
    return mapping.get(t)


def _parse_natural_range(text: str) -> Optional[Dict[str, str]]:
    """Devuelve dict con 'desde' y 'hasta' ISO cuando detecta rangos naturales.
    Soporta: hoy, ayer, últimos N días, entre YYYY-MM-DD y YYYY-MM-DD, última fecha.
    """
    t = (text or "").lower()
    now = datetime.now()
    # hoy
    if " hoy" in t or t.startswith("hoy"):
        start = datetime(now.year, now.month, now.day)
        return {"desde": start.isoformat()}
    # ayer
    if " ayer" in t or t.startswith("ayer"):
        from datetime import timedelta
        d = now - timedelta(days=1)
        start = datetime(d.year, d.month, d.day)
        end = datetime(now.year, now.month, now.day)
        return {"desde": start.isoformat(), "hasta": end.isoformat()}
    # últimos N días
    m = re.search(r"ultimos\s+(\d{1,3})\s*d[ií]as", t)
    if not m:
        m = re.search(r"últimos\s+(\d{1,3})\s*d[ií]as", t)
    if m:
        from datetime import timedelta
        n = int(m.group(1))
        start = now - timedelta(days=n)
        return {"desde": start.isoformat()}
    # entre fechas YYYY-MM-DD
    m2 = re.search(r"entre\s+(\d{4}-\d{2}-\d{2})\s+y\s+(\d{4}-\d{2}-\d{2})", t)
    if m2:
        return {"desde": f"{m2.group(1)}T00:00:00", "hasta": f"{m2.group(2)}T23:59:59"}
    return None


def _max_date_created() -> Optional[str]:
    try:
        items, _ = get_orders_service(["date_created"], {"page": 1, "limit": 1, "sort_by": "date_created", "sort_dir": "DESC"})
        if items:
            dt = items[0].get("date_created")
            if isinstance(dt, str):
                return dt[:10]
            try:
                return dt.date().isoformat()  # type: ignore
            except Exception:
                pass
    except Exception:
        return None
    return None

def _safe_int(val):
    try:
        return int(val)
    except Exception:
        return None


def _pick_latest(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    # Asumimos que get_orders_service respetó sort_by=id DESC
    return items[0]


def _today_range() -> Dict[str, Any]:
    return _parse_natural_range("hoy") or {}


def _order_title(order_id: int) -> Optional[str]:
    items, _ = get_orders_service(["order_id", "nombre"], {"order_id": order_id, "page": 1, "limit": 1})
    if not items:
        return None
    return items[0].get("nombre")


def _printed_status(order_id: int) -> str:
    items, _ = get_orders_service(["order_id", "ready_to_print", "printed"], {"order_id": order_id, "page": 1, "limit": 1})
    if not items:
        return f"No encontré la orden {order_id}."
    it = items[0]
    rtp = it.get("ready_to_print") or 0
    prt = it.get("printed") or 0
    if prt == 1:
        return f"La orden {order_id} está IMPRESA (printed=1)."
    if rtp == 1:
        return f"La orden {order_id} está LISTA PARA IMPRIMIR (ready_to_print=1, printed=0)."
    return f"La orden {order_id} no está impresa ni lista para imprimir (printed=0, ready_to_print=0)."


def _count_printed_today() -> str:
    rng = _today_range()
    params = {"printed": 1, **rng, "page": 1, "limit": 1000, "sort_by": "id", "sort_dir": "DESC"}
    items = _fetch_all(params, ["order_id", "pack_id", "printed", "date_created"], page_size=1000, max_pages=5)
    total_orders = len(items)
    packs = {str(it.get("pack_id")) for it in items if it.get("pack_id")}
    total_packs = len(packs)
    return f"Hoy se imprimieron {total_orders} órdenes en {total_packs} paquetes distintos."


def _to_prepare_today_by_depo(depo: str) -> str:
    rng = _today_range()
    params = {
        "ready_to_print": 1,
        "printed": 0,
        "deposito_asignado": depo,
        **rng,
        "page": 1,
        "limit": 500,
        "sort_by": "id",
        "sort_dir": "DESC",
    }
    items = _fetch_all(params, ["order_id", "pack_id", "qty"], page_size=500, max_pages=10)
    n = len(items)
    packs = {str(it.get("pack_id")) for it in items if it.get("pack_id")}
    total_packs = len(packs)
    total_qty = sum(int(it.get("qty") or 0) for it in items)
    return f"Para preparar HOY en {depo}: {n} órdenes, {total_qty} ítems, {total_packs} paquetes."


def _sum_qty_by_sku(sku: str) -> str:
    params = {"q_sku": sku, "page": 1, "limit": 10000, "sort_by": "id", "sort_dir": "DESC"}
    fields = ["sku", "qty", "date_created"]
    items, total = get_orders_service(fields, params)
    s = sum((it.get("qty") or 0) for it in items)
    return f"Vendidos de {sku}: {s} (sobre {total} órdenes coincidentes)."


def _stock_by_sku_and_depo(sku: str, depo: str) -> str:
    params = {"q_sku": sku, "page": 1, "limit": 1, "sort_by": "id", "sort_dir": "DESC"}
    # Pedimos todas por si existen columnas stock_*
    items, total = get_orders_service(["*"], params)
    latest = _pick_latest(items)
    if not latest:
        return f"No encuentro registros para SKU {sku}."
    key = f"stock_{depo.lower()}" if not depo.islower() else f"stock_{depo}"
    # Normalizar algunos alias conocidos
    aliases = {
        "DEP": ["stock_dep"],
        "MDQ": ["stock_mdq"],
        "MUNDOAL": ["stock_mundoal"],
        "MONBAHIA": ["stock_monbahia"],
        "MTGBBPS": ["stock_mtgbbps"],
        "MTGCBA": ["stock_mtgcba"],
        "MTGCOM": ["stock_mtgcom"],
        "MTGJBJ": ["stock_mtgjbj"],
        "MTGROCA": ["stock_mtgroca"],
        "MUNDOROC": ["stock_mundoroc"],
        "NQNSHOP": ["stock_nqnshop"],
        "NQNALB": ["stock_nqnalb"],
        "MUNDOCAB": ["stock_mundocab"],
    }
    cand_keys = [key]
    for k in aliases.get(depo.upper(), []):
        cand_keys.append(k)
    for k in cand_keys:
        if k in latest and latest[k] is not None:
            return f"Stock en {depo} para {sku}: {latest[k]} (último registro)."
    # fallback: listar columnas disponibles
    cols = [c for c in latest.keys() if c.startswith("stock_")]
    return f"No encontré columna de stock para {depo}. Columnas disponibles: {', '.join(cols) if cols else 'ninguna encontrada en registros'}"


def _order_multiventa_or_individual(order_id: int) -> str:
    # Traer la orden
    items, _ = get_orders_service(["order_id", "pack_id"], {"order_id": order_id, "page": 1, "limit": 1})
    if not items:
        return f"No encuentro la orden {order_id}."
    pack_id = items[0].get("pack_id")
    if not pack_id:
        return f"Orden {order_id}: individual (sin pack_id)."
    # Contar las órdenes del mismo pack
    same_pack, total = get_orders_service(["order_id"], {"pack_id": pack_id, "page": 1, "limit": 10000})
    unique_orders = {it.get("order_id") for it in same_pack}
    mv = "multiventa" if len(unique_orders) > 1 else "individual"
    return f"Orden {order_id} es {mv} (pack_id={pack_id}, órdenes en el pack={len(unique_orders)})."


def _order_delivered(order_id: int) -> str:
    items, _ = get_orders_service(["order_id", "shipping_estado", "shipping_subestado", "date_closed"], {"order_id": order_id, "page": 1, "limit": 1})
    if not items:
        return f"No encuentro la orden {order_id}."
    it = items[0]
    est = str(it.get("shipping_estado") or "").lower()
    sub = str(it.get("shipping_subestado") or "").lower()
    if est in ("delivered", "entregado", "delivered_not_verified") or sub in ("delivered", "entregado"):
        return f"Orden {order_id}: ENTREGADA (estado={it.get('shipping_estado')}/{it.get('shipping_subestado')}, date_closed={it.get('date_closed')})."
    return f"Orden {order_id}: NO entregada (estado={it.get('shipping_estado')}/{it.get('shipping_subestado')})."


def _list_orders_by(filters: Dict[str, Any], limit: int = 50) -> str:
    params = {"page": 1, "limit": limit, "sort_by": "id", "sort_dir": "DESC"}
    params.update(filters)
    fields = ["order_id", "sku", "qty", "shipping_estado", "printed", "deposito_asignado", "date_created"]
    items, total = get_orders_service(fields, params)
    lines = [f"Total={total}, mostrando hasta {limit}:"]
    for it in items:
        lines.append(
            f"order_id={it.get('order_id')} sku={it.get('sku')} qty={it.get('qty')} ship={it.get('shipping_estado')} printed={it.get('printed')} depo={it.get('deposito_asignado')} fecha={it.get('date_created')}"
        )
    return "\n".join(lines)


def _fetch_all(params: Dict[str, Any], fields: List[str], page_size: int = 500, max_pages: int = 20) -> List[Dict[str, Any]]:
    """Itera páginas hasta reunir resultados suficientes (límite de seguridad)."""
    all_items: List[Dict[str, Any]] = []
    page = 1
    for _ in range(max_pages):
        p = {**params, "page": page, "limit": page_size}
        items, total = get_orders_service(fields, p)
        if not items:
            break
        all_items.extend(items)
        if len(all_items) >= total:
            break
        page += 1
    return all_items


def _aggregate_sales(params: Dict[str, Any]) -> str:
    """Devuelve un resumen simple en Markdown de ventas: total órdenes y suma de qty en rango."""
    fields = ["order_id", "sku", "qty", "date_created", "deposito_asignado"]
    params = {**params, "sort_by": "date_created", "sort_dir": "DESC"}
    items = _fetch_all(params, fields, page_size=500, max_pages=10)
    total_orders = len(items)
    total_qty = sum(int(it.get("qty") or 0) for it in items)
    # Top 10 recientes
    head = items[:10]
    lines = [
        "## Resumen de ventas",
        f"- Total de órdenes: {total_orders}",
        f"- Suma de cantidades (qty): {total_qty}",
        "",
        "### Últimas 10 órdenes",
        "| order_id | sku | qty | depósito | fecha |",
        "|---:|---|---:|---|---|",
    ]
    for it in head:
        lines.append(f"| {it.get('order_id')} | {it.get('sku')} | {it.get('qty')} | {it.get('deposito_asignado') or ''} | {it.get('date_created')} |")
    if total_orders > 10:
        lines.append(f"\n... y {total_orders-10} más en el rango.")
    return "\n".join(lines)

def _fmt_count_qty(items: List[Dict[str, Any]]) -> Tuple[int, int]:
    total_orders = len(items)
    total_qty = sum(int(it.get("qty") or 0) for it in items)
    return total_orders, total_qty

def _count_ready_to_dispatch(rng: Dict[str, Any]) -> str:
    fields = ["order_id", "qty", "date_created", "ready_to_print", "printed"]
    params = {**rng, "ready_to_print": 1, "sort_by": "date_created", "sort_dir": "DESC"}
    items = _fetch_all(params, fields, page_size=500, max_pages=10)
    n, q = _fmt_count_qty(items)
    return f"Para despachar hoy: {n} órdenes, {q} ítems (ready_to_print=1)."

def _list_cancelled(rng: Dict[str, Any]) -> str:
    fields = ["order_id", "sku", "qty", "date_created", "_estado", "shipping_estado", "shipping_subestado"]
    # Dos consultas: por _estado y por shipping_estado, luego unificar por order_id
    items1 = _fetch_all({**rng, "_estado": "cancelled", "sort_by": "date_created", "sort_dir": "DESC"}, fields)
    items2 = _fetch_all({**rng, "shipping_estado": "cancelled", "sort_by": "date_created", "sort_dir": "DESC"}, fields)
    seen = set()
    merged: List[Dict[str, Any]] = []
    for it in items1 + items2:
        oid = it.get("order_id")
        if oid in seen:
            continue
        seen.add(oid)
        merged.append(it)
    if not merged:
        return "No hay ventas canceladas en el rango."
    n, q = _fmt_count_qty(merged)
    head = merged[:10]
    lines = [f"Canceladas: {n} órdenes, {q} ítems", "", "| order_id | sku | qty | estado | subestado | fecha |", "|---:|---|---:|---|---|---|"]
    for it in head:
        lines.append(f"| {it.get('order_id')} | {it.get('sku') or ''} | {it.get('qty')} | {it.get('shipping_estado') or it.get('_estado') or ''} | {it.get('shipping_subestado') or ''} | {it.get('date_created')} |")
    if n > 10:
        lines.append(f"\n... y {n-10} más.")
    return "\n".join(lines)

def _count_returns(rng: Dict[str, Any]) -> str:
    fields = ["order_id", "sku", "qty", "date_created", "shipping_estado", "shipping_subestado"]
    # Heurística de devoluciones
    candidates = [
        _fetch_all({**rng, "shipping_estado": "returned", "sort_by": "date_created", "sort_dir": "DESC"}, fields),
        _fetch_all({**rng, "shipping_estado": "to_be_returned", "sort_by": "date_created", "sort_dir": "DESC"}, fields),
        _fetch_all({**rng, "shipping_subestado": "to_be_returned", "sort_by": "date_created", "sort_dir": "DESC"}, fields),
    ]
    merged: List[Dict[str, Any]] = []
    seen = set()
    for batch in candidates:
        for it in batch:
            oid = it.get("order_id")
            if oid in seen:
                continue
            seen.add(oid)
            merged.append(it)
    if not merged:
        return "No hay devoluciones en el rango."
    n, q = _fmt_count_qty(merged)
    return f"Devoluciones para revisar: {n} órdenes, {q} ítems."

def _order_status(order_id: int) -> str:
    fields = ["order_id", "sku", "qty", "_estado", "shipping_estado", "shipping_subestado", "printed", "ready_to_print", "deposito_asignado", "date_created"]
    items, total = get_orders_service(fields, {"order_id": order_id, "limit": 1, "page": 1})
    if not items:
        return f"No encuentro la orden {order_id}."
    it = items[0]
    return (
        "## Estado de la orden\n"
        f"- order_id: {it.get('order_id')}\n"
        f"- estado: {it.get('_estado') or ''}\n"
        f"- shipping_estado: {it.get('shipping_estado') or ''}\n"
        f"- subestado: {it.get('shipping_subestado') or ''}\n"
        f"- printed: {it.get('printed')} | ready_to_print: {it.get('ready_to_print')}\n"
        f"- depósito: {it.get('deposito_asignado') or ''}\n"
        f"- fecha: {it.get('date_created') or ''}"
    )

def _order_rejection_reason(order_id: int) -> str:
    fields = ["order_id", "_estado", "shipping_estado", "shipping_subestado", "q_comentario"] if 'q_comentario' in globals() else ["order_id", "_estado", "shipping_estado", "shipping_subestado"]
    items, _ = get_orders_service(fields, {"order_id": order_id, "limit": 1, "page": 1})
    if not items:
        return f"No encuentro la orden {order_id}."
    it = items[0]
    motivo = it.get("shipping_subestado") or it.get("shipping_estado") or it.get("_estado")
    if motivo:
        return f"Motivo/referencia de rechazo para {order_id}: {motivo}"
    return f"No encuentro motivo de rechazo para {order_id}."

def _delays_summary() -> str:
    # Órdenes con ready_to_print=1 y printed=0 anteriores a hoy
    today = datetime.now().date().isoformat()
    rng = {"hasta": f"{today}T00:00:00"}
    fields = ["order_id", "qty", "date_created"]
    params = {**rng, "ready_to_print": 1, "printed": 0, "sort_by": "date_created", "sort_dir": "ASC"}
    items = _fetch_all(params, fields, page_size=500, max_pages=20)
    if not items:
        return "No hay demoras pendientes."
    n, q = _fmt_count_qty(items)
    oldest = items[0].get("date_created")
    return f"Demoras: {n} órdenes RTP no impresas (qty {q}). Más antigua: {oldest}."

def _shipped_today_by_item(kind: str, value: str) -> str:
    rng = _parse_natural_range("hoy") or {}
    fields = ["order_id", "sku", "qty", "date_created", "printed"]
    params = {**rng, "printed": 1, "sort_by": "date_created", "sort_dir": "DESC"}
    if kind == "barcode":
        params["barcode"] = value
    else:
        params["sku"] = value
    items = _fetch_all(params, fields, page_size=500, max_pages=10)
    n, q = _fmt_count_qty(items)
    return f"Hoy se despacharon {q} ítems en {n} órdenes para {kind}={value}."

def _count_shipped_by_item_on_date(kind: str, value: str, rng: Dict[str, Any]) -> str:
    fields = ["order_id", "sku", "qty", "date_created", "printed"]
    params = {**rng, "printed": 1, "sort_by": "date_created", "sort_dir": "DESC"}
    if kind == "barcode":
        params["barcode"] = value
    else:
        params["sku"] = value
    items = _fetch_all(params, fields, page_size=500, max_pages=10)
    n, q = _fmt_count_qty(items)
    return f"En el rango pedido se despacharon {q} ítems en {n} órdenes para {kind}={value}."

def try_answer_locally(text: str) -> Optional[str]:
    if not text:
        return None
    t = text.strip()
    # Detectar order_id
    m_id = re.findall(r"\b\d{6,}\b", t)
    # Detectar SKU
    m_sku = re.findall(r"[A-Z0-9]{2,}(?:-[A-Z0-9]+){0,3}", t, flags=re.IGNORECASE)
    # Detectar depósito
    m_depo = re.findall(r"\b(DEP|MDQ|MUNDOAL|MONBAHIA|MTGBBPS|MTGCBA|MTGCOM|MTGJBJ|MTGROCA|MUNDOROC|NQNSHOP|NQNALB|MUNDOCAB)\b", t, flags=re.IGNORECASE)

    lower = t.lower()

    # 0) Título de una orden específica
    if ("titulo" in lower or "título" in lower) and m_id:
        oid = _safe_int(m_id[0])
        if oid:
            tt = _order_title(oid)
            return tt or f"No encontré título para la orden {oid}."

    # 1) Cuántos vendidos de <SKU>
    if ("cuantos" in lower or "cuánto" in lower or "cantidad" in lower or "vendieron" in lower or "vendidos" in lower) and m_sku:
        sku = m_sku[0]
        return _sum_qty_by_sku(sku)

    # 2) Stock en depósito para SKU
    if ("stock" in lower or "tiene en stock" in lower) and m_sku and m_depo:
        return _stock_by_sku_and_depo(m_sku[0], m_depo[0])

    # 3) Es multiventa o individual
    if ("multiventa" in lower or "individual" in lower) and m_id:
        oid = _safe_int(m_id[0])
        if oid:
            return _order_multiventa_or_individual(oid)

    # 4) Se entregó este pedido?
    if ("se entrego" in lower or "se entregó" in lower or "entregado" in lower or "delivered" in lower) and m_id:
        oid = _safe_int(m_id[0])
        if oid:
            return _order_delivered(oid)

    # 4.5) ¿Está impresa la orden X?
    if ("impresa" in lower or "impreso" in lower or "printed" in lower) and m_id:
        oid = _safe_int(m_id[0])
        if oid:
            return _printed_status(oid)

    # 5) Listados por estado/printed/deposito/fechas
    if ("dame todos los pedidos" in lower or "listar" in lower or "mostrame" in lower or "dame todos los vendidos" in lower or "ventas" in lower):
        filters: Dict[str, Any] = {}
        # printed
        if "printed" in lower:
            filters["printed"] = 1
        if "sin imprimir" in lower:
            filters["printed"] = 0
        if "ready to print" in lower or "ready_to_print" in lower or "rtp" in lower:
            filters["ready_to_print"] = 1
        # shipping_estado
        m_se = re.findall(r"shipping_estado\s*=?\s*([a-z_]+)", lower)
        if m_se:
            filters["shipping_estado"] = m_se[0]
        # _estado (pagado)
        if "pagado" in lower or "paid" in lower:
            filters["_estado"] = "paid"
        # depósito asignado / keywords
        if "bahia" in lower or "bahía" in lower:
            # mapear 'bahia' a múltiples keywords
            filters["deposito_keywords"] = "dep,monbahia,mombahia,mtgbbps,mundoal"
        elif m_depo:
            filters["deposito_asignado"] = m_depo[0]
        # Rango de fechas naturales
        rng = _parse_natural_range(t)
        if not rng and "ultima fecha" in lower or "última fecha" in lower:
            md = _max_date_created()
            if md:
                rng = {"desde": f"{md}T00:00:00", "hasta": f"{md}T23:59:59"}
        if rng:
            filters.update(rng)
        if filters:
            return _list_orders_by(filters)

    # 6) "últimas ventas" con rango natural
    if ("ultimas ventas" in lower or "últimas ventas" in lower) or ("ultimo dia" in lower or "último día" in lower or "del ultimo dia de hoy" in lower):
        rng = _parse_natural_range(t)
        if not rng:
            # Por defecto, hoy
            rng = _parse_natural_range("hoy") or {}
        return _aggregate_sales(rng or {})

    # 7) ¿Cuántas ventas tengo que despachar hoy? (asumimos ready_to_print=1 hoy)
    if ("despachar" in lower or "despacho" in lower) and ("hoy" in lower or "para hoy" in lower or "del dia" in lower):
        rng = _parse_natural_range("hoy") or {}
        return _count_ready_to_dispatch(rng)

    # 8) ¿Qué ventas se cancelaron hoy? (por _estado=cancelled o shipping_estado=cancelled)
    if ("cancelaron" in lower or "canceladas" in lower or "cancelado" in lower) and ("hoy" in lower or "del dia" in lower):
        rng = _parse_natural_range("hoy") or {}
        return _list_cancelled(rng)

    # 9) ¿Cuántas devoluciones hay para revisar hoy?
    if ("devolucion" in lower or "devolución" in lower or "devoluciones" in lower) and ("hoy" in lower or "del dia" in lower):
        rng = _parse_natural_range("hoy") or {}
        return _count_returns(rng)

    # 9.5) ¿Cuántos paquetes/órdenes se imprimieron hoy?
    if ("impres" in lower or "printed" in lower) and ("hoy" in lower):
        return _count_printed_today()

    # 10) Estado por número de orden
    if ("estado" in lower or "en que estado" in lower or "estatus" in lower) and m_id:
        oid = _safe_int(m_id[0])
        if oid:
            return _order_status(oid)

    # 11) ¿Por qué me rechazó esta venta?
    if ("por que me rechazo" in lower or "por qué me rechazo" in lower or "rechazo esta venta" in lower) and m_id:
        oid = _safe_int(m_id[0])
        if oid:
            return _order_rejection_reason(oid)

    # 12) ¿Qué demoras tengo? (no impresas/pendientes anteriores a hoy)
    if "demoras" in lower or "demora" in lower:
        return _delays_summary()

    # 12.5) ¿Qué tengo que preparar hoy desde <DEPO>?
    if ("preparar" in lower or "preparación" in lower or "preparar hoy" in lower) and m_depo:
        return _to_prepare_today_by_depo(m_depo[0].upper())

    # 13) Ese artículo se despachó hoy? (detecta barcode o SKU)
    if ("se despacho" in lower or "se despachó" in lower or "despacho" in lower) and ("hoy" in lower):
        code = None
        # barcode: dígitos 8-14
        m_bar = re.findall(r"\b\d{8,14}\b", t)
        if m_bar:
            code = ("barcode", m_bar[0])
        elif m_sku:
            code = ("sku", m_sku[0])
        if code:
            return _shipped_today_by_item(code[0], code[1])

    # 14) ¿Cuántos se despacharon de ese el día X?
    if ("cuantos" in lower or "cuánto" in lower) and ("despacharon" in lower or "despachó" in lower or "despacho" in lower) and ("dia" in lower or re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", lower)):
        # detectar fecha explícita en formato dd/mm/aaaa
        m_date = re.findall(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", t)
        rng = _parse_natural_range(m_date[0]) if m_date else (_parse_natural_range(t) or {})
        if not rng:
            return "No pude interpretar la fecha. Probá con 'dd/mm/aaaa'."
        code = None
        m_bar = re.findall(r"\b\d{8,14}\b", t)
        if m_bar:
            code = ("barcode", m_bar[0])
        elif m_sku:
            code = ("sku", m_sku[0])
        if code:
            return _count_shipped_by_item_on_date(code[0], code[1], rng)

    return None

# ------------------------------
# Chat helpers: key, intents, context, local answers
# ------------------------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def _read_openrouter_key() -> Optional[str]:
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    # fallback a archivo local
    try:
        here = os.path.dirname(__file__)
        p = os.path.join(here, "openrouter_key.txt")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                k = fh.read().strip()
                return k or None
    except Exception:
        pass
    return None

_SKU_RE = re.compile(r"\b[\w-]{4,}[-_][\w-]{2,}\b", re.IGNORECASE)
_ORDERID_RE = re.compile(r"\b\d{12,19}\b")

def _extract_intents(t: str) -> Dict[str, Any]:
    lower = (t or "").lower()
    intents: Dict[str, Any] = {}
    # order_id
    m_oid = _ORDERID_RE.findall(t)
    if m_oid:
        intents["order_id"] = int(m_oid[0])
    # sku
    m_sku = _SKU_RE.findall(t)
    if m_sku:
        intents["sku"] = m_sku[0]
    # quoted title phrase
    m_q = re.findall(r'"([^"]{3,})"', t)
    if m_q:
        intents["title_phrase"] = m_q[0]
    # natural date range via existing helper if available
    try:
        rng = _parse_natural_range(t)  # type: ignore[name-defined]
        if isinstance(rng, dict) and (rng.get("from") or rng.get("to")):
            intents["from"] = rng.get("from")
            intents["to"] = rng.get("to")
    except Exception:
        pass
    # deposito
    m_depo = re.findall(r"\b(depo|mundocab|mundoroc|monbahia|mombahia|mtgbbps|mundoal)\b", lower)
    # Bahía: si aparece en el texto, mapear a keywords múltiples
    if ("bahia" in lower or "bahía" in lower) and "deposito_keywords" not in intents:
        intents["deposito_keywords"] = "dep,monbahia,mombahia,mtgbbps,mundoal"
    if m_depo:
        intents["deposito_keywords"] = m_depo[0]
    return intents

def _build_db_context(user_text: str) -> str:
    intents = _extract_intents(user_text)
    # armar params para servicio de órdenes
    params: Dict[str, Any] = {
        "page": 1,
        "limit": 20,
        "include_printed": 1,
        "sort_by": "date_created",
        "sort_dir": "DESC",
    }
    params.update({k: v for k, v in intents.items() if k in {"order_id", "sku", "from", "to", "deposito_keywords"}})
    if intents.get("title_phrase"):
        params["title_phrase"] = intents["title_phrase"]

    try:
        items, total = get_orders_service(["*"], params)  # type: ignore[name-defined]
    except Exception as e:
        return f"CONTEXT_ERROR: {e}"

    def mini_item(it: Dict[str, Any]) -> str:
        nombre = it.get("nombre") or it.get("ARTICULO") or it.get("seller_sku") or it.get("sku")
        sku = it.get("sku") or it.get("seller_sku")
        dep = it.get("deposito_asignado") or it.get("DEPOSITO")
        ship = it.get("shipping_status") or it.get("shipping_substatus") or it.get("ship")
        qty = it.get("qty") or it.get("quantity") or 1
        printed = int(it.get("printed") or 0)
        return f"- order_id={it.get('order_id')} pack_id={it.get('pack_id')} sku={sku} qty={qty} dep={dep} printed={printed} ship={ship} title={nombre}"

    # Armar como tabla Markdown compacta
    hdr = "order_id | pack_id | sku | qty | deposito | printed | estado | title"
    sep = "-|-|-|-|-|-|-|-"
    rows = []
    for it in items:
        rows.append(
            f"{it.get('order_id')} | {it.get('pack_id')} | {it.get('sku') or it.get('seller_sku')} | "
            f"{it.get('qty') or it.get('quantity') or 1} | {it.get('deposito_asignado') or it.get('DEPOSITO')} | "
            f"{int(it.get('printed') or 0)} | {(it.get('shipping_status') or it.get('shipping_substatus') or '')} | "
            f"{(it.get('nombre') or it.get('ARTICULO') or '')}"
        )
    lines = [
        "CONTEXT: ORDERS",
        f"total={total}",
        hdr,
        sep,
        *rows,
        "ENDPOINTS: /orders (order_id, sku, barcode, title_phrase, from, to, deposito_keywords), /orders/resolve-by-barcode, /orders/{order_id}/printed-moved",
    ]
    return "\n".join(lines)

def try_answer_locally(t: str) -> Optional[str]:
    if not t:
        return None
    lower = t.lower()
    # marcar impresa la orden X -> devolver instrucción API segura
    m_oid = _ORDERID_RE.findall(t)
    if ("marcar" in lower or "impresa" in lower or "impreso" in lower) and m_oid:
        oid = m_oid[0]
        return (
            f"Para marcar impresa la orden {oid}, hacé un POST a /orders/{oid}/printed-moved "
            f"con JSON: {{\"printed\": 1}}. Si necesitás registrar movimiento de depósito, agregá campos: "
            f"mov_depo_hecho, mov_depo_numero, mov_depo_obs, asignacion_detalle."
        )
    # últimas ventas
    if "ultimas" in lower and ("ventas" in lower or "ordenes" in lower or "órdenes" in lower):
        try:
            items, total = get_orders_service(["*"], {"page": 1, "limit": 10, "sort_by": "date_created", "sort_dir": "DESC"})  # type: ignore[name-defined]
            if not items:
                return "No hay ventas recientes."
            rows = []
            for it in items:
                rows.append(f"{it.get('order_id')} | {it.get('sku') or it.get('seller_sku')} | {it.get('qty') or 1} | {it.get('deposito_asignado') or ''} | {it.get('date_created') or ''}")
            return "Últimas ventas (máx 10):\n" + "\n".join(rows)
        except Exception:
            return None
    # conteo por SKU
    m_sku = _SKU_RE.findall(t)
    if ("cuantos" in lower or "cuánto" in lower or "vendieron" in lower or "ventas" in lower) and m_sku:
        sku = m_sku[0]
        try:
            items, _ = get_orders_service(["*"], {"page": 1, "limit": 200, "sku": sku, "sort_by": "date_created", "sort_dir": "DESC"})  # type: ignore[name-defined]
            total_qty = sum(int(x.get("qty") or 1) for x in items)
            return f"Vendidos de {sku}: {total_qty} (sobre {len(items)} órdenes coincidentes)."
        except Exception:
            return None
    return None

@app.post("/api/chat")
def api_chat(payload: Dict[str, Any]):
    key = _get_openrouter_key()
    if not key:
        raise HTTPException(status_code=500, detail="Falta OPENROUTER_API_KEY en el servidor")

    model = payload.get("model") or "deepseek/deepseek-chat"
    messages = payload.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages requerido")

    # Intento de respuesta local (estructurada) antes de llamar al LLM
    last_user = None
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = m
            break
    if last_user:
        local_ans = try_answer_locally(str(last_user.get("content") or ""))
        if local_ans:
            # Devolver en formato OpenAI-compatible
            return {"choices": [{"message": {"role": "assistant", "content": local_ans}}]}

    # Agregar contexto de DB al último mensaje de usuario
    if last_user:
        ctx = _build_db_context(str(last_user.get("content") or ""))
        messages = [
            {
                "role": "system",
                "content": (
                    "Respondé en español, con respuestas cortas, claras y accionables. "
                    "Usá títulos y bullets. Si listás varias órdenes, usá una tabla Markdown de 5-6 columnas máximo: "
                    "order_id | nombre | qty | deposito | estado | fecha. "
                    "No repitas texto innecesario. Si falta información, pedí el dato mínimo (sku, order_id o rango de fechas)."
                ),
            },
            {"role": "system", "content": ctx},
            *messages,
        ]

    public_url = os.getenv("SERVER_PUBLIC_URL", "http://190.211.201.217:5001")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # OpenRouter recomienda enviar Referer/X-Title; incluimos también Origin para compatibilidad
        "HTTP-Referer": public_url,
        "Referer": public_url,
        "Origin": public_url,
        "X-Title": "CHATBASE",
        "User-Agent": "meli-stock-pipeline/1.0 (+http://190.211.201.217:5001)",
    }
    body = {"model": model, "messages": messages}

    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=60)
        content_type = r.headers.get("Content-Type", "")
        if r.status_code >= 400:
            # Loggear detalles para diagnóstico 401/403
            try:
                print("[OpenRouter error] status=", r.status_code)
                print("[OpenRouter error] request headers=", headers)
                print("[OpenRouter error] response headers=", dict(r.headers))
                print("[OpenRouter error] body=", r.text[:2000])
            except Exception:
                pass
            # Devolver error de OpenRouter al cliente
            return JSONResponse(status_code=r.status_code, content=r.json() if "application/json" in content_type else {"error": r.text})
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Error al contactar OpenRouter: {e}")


@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now().isoformat()}


@app.get("/orders", response_model=OrdersResponse)
def get_orders(
    fields: Optional[str] = Query(None, description="Campos separados por coma a devolver. Si no se envía, se devuelven campos por defecto."),
    # Filtros exactos comunes
    order_id: Optional[int] = None,
    pack_id: Optional[str] = None,
    sku: Optional[str] = None,
    seller_sku: Optional[str] = None,
    barcode: Optional[str] = None,
    ARTICULO: Optional[str] = None,
    COLOR: Optional[str] = None,
    TALLE: Optional[str] = None,
    display_color: Optional[str] = None,
    deposito_asignado: Optional[str] = None,
    _estado: Optional[str] = None,
    meli_ad: Optional[str] = None,
    venta_tipo: Optional[str] = None,
    shipping_estado: Optional[str] = None,
    shipping_subestado: Optional[str] = None,
    agotamiento_flag: Optional[int] = Query(None, ge=0, le=1),
    ready_to_print: Optional[int] = Query(None, ge=0, le=1),
    printed: Optional[int] = Query(None, ge=0, le=1),
    qty: Optional[int] = None,
    # Rangos de fecha
    desde: Optional[str] = Query(None, description="date_created >= (ISO8601)"),
    hasta: Optional[str] = Query(None, description="date_created <= (ISO8601)"),
    cerrado_desde: Optional[str] = Query(None, description="date_closed >= (ISO8601)"),
    cerrado_hasta: Optional[str] = Query(None, description="date_closed <= (ISO8601)"),
    # Búsquedas parciales
    q_sku: Optional[str] = Query(None, description="LIKE en sku"),
    q_barcode: Optional[str] = Query(None, description="LIKE en barcode"),
    q_comentario: Optional[str] = Query(None, description="LIKE en COMENTARIO"),
    q_title: Optional[str] = Query(None, description="LIKE en nombre/título si existe"),
    # Extras contrato
    deposito_keywords: Optional[str] = Query(None, description="CSV de términos para contains en deposito_asignado"),
    deposito_asignado_in: Optional[str] = Query(None, description="CSV de depósitos para filtro IN exacto en deposito_asignado"),
    include_printed: Optional[int] = Query(None, ge=0, le=1, description="0 excluye impresas, 1 incluye"),
    # Orden
    sort_by: Optional[str] = Query(None, description="Columna para ordenar (default id)"),
    sort_dir: Optional[str] = Query("DESC", regex="^(?i)(ASC|DESC)$"),
    # Paginación
    page: int = Query(1, ge=1),
    limit: int = Query(200, ge=1, le=1000),
    debug_nombre: int = Query(0, ge=0, le=1),
    title_sources: Optional[str] = Query(None, description="CSV de columnas para armar el título en orden de preferencia"),
    # Compatibilidad con clientes existentes
    from_: Optional[str] = Query(None, alias="from", description="Alias de 'desde' en ISO8601"),
    to_: Optional[str] = Query(None, alias="to", description="Alias de 'hasta' en ISO8601"),
    page_size: Optional[int] = Query(None, alias="page_size", ge=1, le=1000, description="Alias de 'limit"),
    acc: str = Query("acc1", regex="^acc1|acc2$", description="Cuenta/base de datos a usar: acc1 o acc2"),
    _=Depends(require_token),
):
    try:
        # Resolver compatibilidad
        if from_ and not desde:
            desde = from_
        if to_ and not hasta:
            hasta = to_
        eff_limit = page_size if page_size is not None else limit

        selected_fields: Optional[List[str]] = None
        if fields:
            selected_fields = [f.strip() for f in fields.split(",") if f.strip()]
        else:
            # Usar default del servicio
            selected_fields = get_default_fields_for_orders()
        # Asegurar columnas mínimas para resolución de título
        must_have = {"nombre", "ARTICULO", "sku", "seller_sku"}
        for col in must_have:
            if col not in selected_fields:
                selected_fields.append(col)

        items, total = get_orders_service(
            selected_fields=selected_fields,
            params={
                "order_id": order_id,
                "pack_id": pack_id,
                "sku": sku,
                "seller_sku": seller_sku,
                "barcode": barcode,
                "ARTICULO": ARTICULO,
                "COLOR": COLOR,
                "TALLE": TALLE,
                "display_color": display_color,
                "deposito_asignado": deposito_asignado,
                "_estado": _estado,
                "meli_ad": meli_ad,
                "venta_tipo": venta_tipo,
                "shipping_estado": shipping_estado,
                "shipping_subestado": shipping_subestado,
                "agotamiento_flag": agotamiento_flag,
                "ready_to_print": ready_to_print,
                "printed": printed,
                "qty": qty,
                "desde": desde,
                "hasta": hasta,
                "cerrado_desde": cerrado_desde,
                "cerrado_hasta": cerrado_hasta,
                "q_sku": q_sku,
                "q_barcode": q_barcode,
                "q_comentario": q_comentario,
                "q_title": q_title,
                "deposito_keywords": deposito_keywords,
                "deposito_asignado_in": deposito_asignado_in,
                "include_printed": include_printed,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
                "page": page,
                "limit": eff_limit,
            },
            acc=acc,
        )
        # Precomputar si un pack es consolidado (más de una orden en el mismo pack dentro del set consultado)
        pack_counts: Dict[str, int] = {}
        for it in items:
            pid = it.get("pack_id")
            if pid is not None and pid != "":
                k = str(pid)
                pack_counts[k] = pack_counts.get(k, 0) + 1

        # Adaptar items para el cliente GUI: agregar campos esperados por la GUI
        adapted = []
        for it in items:
            # Resolver título completo según fuentes preferidas
            nombre_full = _resolve_full_title(it, title_sources)
            cand_onombre = it.get("onombre"); cand_nombre = it.get("nombre"); cand_articulo = it.get("ARTICULO"); cand_sku = it.get("sku"); cand_seller = it.get("seller_sku")
            nombre_src = (
                "onombre" if (cand_onombre and str(cand_onombre).strip()) else
                ("nombre" if (cand_nombre and str(cand_nombre).strip()) else
                 ("pack_orders_json" if nombre_full not in (cand_onombre, cand_nombre, cand_articulo, cand_sku, cand_seller) else
                  ("ARTICULO" if cand_articulo else ("sku" if cand_sku else "seller_sku"))))
            )
            title = nombre_full
            quantity = it.get("qty") or it.get("quantity") or 1
            seller_sku_val = it.get("seller_sku") or it.get("sku")
            sku_val = it.get("sku") or seller_sku_val
            variation_list = []
            if it.get("COLOR"):
                variation_list.append({"id": "COLOR", "value_name": it.get("COLOR")})
            if it.get("TALLE"):
                variation_list.append({"id": "TALLE", "value_name": it.get("TALLE")})

            item_payload = {
                "title": title,
                "nombre": nombre_full,
                "quantity": quantity,
                "barcode": it.get("barcode"),
                "seller_sku": seller_sku_val,
                "sku": sku_val,
                "item": {
                    "id": it.get("item_id"),
                    "variation_id": it.get("variation_id"),
                    "seller_sku": seller_sku_val,
                    "seller_custom_field": seller_sku_val,
                    "variation_attributes": variation_list if variation_list else None,
                },
                "variation_attributes": variation_list if variation_list else None,
                "attributes": {"COLOR": it.get("COLOR"), "TALLE": it.get("TALLE")},
            }
            if debug_nombre:
                item_payload["__nombre_src"] = nombre_src
                item_payload["__nombre_candidates"] = {
                    "onombre": cand_onombre,
                    "nombre": cand_nombre,
                    "ARTICULO": cand_articulo,
                    "sku": cand_sku,
                    "seller_sku": cand_seller,
                }
            # limpiar None en variation_attributes si vacío
            if not item_payload["variation_attributes"]:
                item_payload.pop("variation_attributes", None)

            # Campos adicionales requeridos por la GUI
            buyer_obj = None
            # Construir objeto buyer con lo disponible
            nick = it.get("buyer_nickname") or it.get("buyer")
            bid = it.get("buyer_id")
            if nick is not None or bid is not None:
                buyer_obj = {k: v for k, v in {"nickname": nick, "id": bid}.items() if v is not None}

            # Priorizar columnas estándar si existen; caer a alias
            shipping_status = it.get("shipping_status") or it.get("shipping_estado")
            shipping_substatus = it.get("shipping_substatus") or it.get("shipping_subestado")

            # Nota: elegir la "mejor" nota: COMENTARIO si existe, sino deposito_asignado como pista
            notes = it.get("COMENTARIO") or it.get("deposito_asignado")

            # is_consolidated_pack: true si hay más de una orden con el mismo pack_id en el set
            pid = it.get("pack_id")
            is_pack = False
            if pid is not None and pid != "":
                is_pack = (pack_counts.get(str(pid), 0) > 1)

            # extra con campos útiles para INFO
            extra = {
                "COMENTARIO": it.get("COMENTARIO"),
                "mov_depo_hecho": it.get("mov_depo_hecho"),
                "mov_depo_numero": it.get("mov_depo_numero"),
                "mov_depo_obs": it.get("mov_depo_obs"),
                "asignacion_detalle": it.get("asignacion_detalle"),
            }
            # quitar claves None para aligerar
            extra = {k: v for k, v in extra.items() if v is not None}

            # Ensamblar objeto final compatible (sin copiar toda la fila para evitar Decimals no serializables)
            out: Dict[str, Any] = {
                "id": it.get("order_id"),
                "order_id": it.get("order_id"),
                "date_created": it.get("date_created"),
                "date_closed": it.get("date_closed"),
                "pack_id": it.get("pack_id"),
                "shipping_id": it.get("shipping_id"),
                "shipping_status": shipping_status,
                "shipping_substatus": shipping_substatus,
                "deposito_asignado": it.get("deposito_asignado"),
                "nombre": title,
                "qty": quantity,
                "notes": notes,
                "is_consolidated_pack": True if is_pack else False,
                "printed": it.get("printed"),
                "ready_to_print": it.get("ready_to_print"),
            }
            if buyer_obj is not None:
                out["buyer"] = buyer_obj
            elif it.get("buyer") is not None:
                # fallback: valor plano si existe en la base
                out["buyer"] = it.get("buyer")
            # amounts
            subtotal = it.get("unit_price")
            total_amt = it.get("total_amount") or it.get("unit_price")
            # asegurar serialización numérica
            if isinstance(subtotal, Decimal):
                subtotal = float(subtotal)
            if isinstance(total_amt, Decimal):
                total_amt = float(total_amt)
            currency = it.get("currency_id")
            amounts = {k: v for k, v in {
                "subtotal": subtotal,
                "shipping": 0,
                "discounts": 0,
                "total": total_amt,
                "currency": currency,
            }.items() if v is not None}
            if amounts:
                out["amounts"] = amounts
            out["items"] = [item_payload]
            out["order_items"] = out["items"]
            if extra:
                out["extra"] = extra
            adapted.append(out)
        # total puede venir None si el COUNT falla; devolver 0 para cumplir esquema
        safe_total = int(total) if total is not None else 0
        return {"orders": adapted, "page": int(page), "page_size": int(eff_limit), "total": safe_total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------
# Utilidades de mapeo de órdenes
# ------------------------------
def _resolve_full_title(row: Dict[str, Any], title_sources_csv: Optional[str] = None) -> str:
    """Elegir el mejor título disponible del registro, configurable por fuentes.
    - Orden de preferencia:
      1) Query param 'title_sources' (CSV)
      2) Env BACKEND_TITLE_SOURCES (CSV)
      3) Default: ARTICULO, sku, seller_sku
    - Solo si explícitamente se incluye, se considerarán 'nombre', 'onombre' o 'pack_orders_json'.
    """
    import os
    # construir lista de fuentes
    sources: Optional[str] = title_sources_csv or os.getenv("BACKEND_TITLE_SOURCES")
    if sources:
        order = [s.strip() for s in sources.split(',') if s.strip()]
    else:
        # Default: usar 'nombre' de la base primero (título completo), luego fallbacks
        order = ["nombre", "ARTICULO", "sku", "seller_sku"]

    # soporte especial para extraer desde pack_orders_json si está en el orden
    def _extract_from_pack_orders_json(po_val: Any) -> Optional[str]:
        if not po_val:
            return None
        try:
            import json as _json
            data = _json.loads(po_val) if isinstance(po_val, (str, bytes)) else po_val
            def find_title(obj):
                if isinstance(obj, dict):
                    for k in ("nombre", "title", "item_title", "full_title"):
                        v = obj.get(k)
                        if isinstance(v, str) and len(v.strip()) >= 3:
                            return v.strip()
                    for v in obj.values():
                        r = find_title(v)
                        if r:
                            return r
                elif isinstance(obj, list):
                    for el in obj:
                        r = find_title(el)
                        if r:
                            return r
                return None
            return find_title(data)
        except Exception:
            return None

    for key in order:
        k = key.strip()
        if k.lower() == "pack_orders_json":
            val = _extract_from_pack_orders_json(row.get("pack_orders_json"))
            if val:
                return val
        else:
            v = row.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return ""

# ------------------------------
# Contrato cliente adicional
# ------------------------------
@app.get("/orders/resolve-by-barcode")
def resolve_by_barcode(barcode: str = Query(...), deposito: Optional[str] = None, debug_nombre: int = Query(0, ge=0, le=1), acc: str = Query("acc1", regex="^acc1|acc2$"), _=Depends(require_token)):
    try:
        params: Dict[str, Any] = {"page": 1, "limit": 1, "sort_by": "id", "sort_dir": "DESC"}
        if barcode:
            params["barcode"] = barcode
        if deposito:
            params["deposito_asignado"] = deposito
        items, _ = get_orders_service(["*"], params, acc=acc)
        if not items:
            raise HTTPException(status_code=404, detail="No match")
        it = items[0]
        # Resolver título completo
        nombre_full = _resolve_full_title(it)
        cand_onombre = it.get("onombre"); cand_nombre = it.get("nombre"); cand_articulo = it.get("ARTICULO"); cand_sku = it.get("sku"); cand_seller = it.get("seller_sku")
        nombre_src = (
            "onombre" if (cand_onombre and str(cand_onombre).strip()) else
            ("nombre" if (cand_nombre and str(cand_nombre).strip()) else
             ("pack_orders_json" if nombre_full not in (cand_onombre, cand_nombre, cand_articulo, cand_sku, cand_seller) else
              ("ARTICULO" if cand_articulo else ("sku" if cand_sku else "seller_sku"))))
        )
        variation_list = []
        if it.get("TALLE"):
            variation_list.append({"id": "TALLE", "value_name": it.get("TALLE")})
        if it.get("COLOR"):
            variation_list.append({"id": "COLOR", "value_name": it.get("COLOR")})
        item_obj = {
            "title": nombre_full,
            "nombre": nombre_full,
            "quantity": it.get("qty") or 1,
            "barcode": it.get("barcode"),
            "seller_sku": it.get("seller_sku") or it.get("sku"),
            "sku": it.get("sku") or it.get("seller_sku"),
            "item": {
                "id": it.get("item_id"),
                "variation_id": it.get("variation_id"),
                "variation_attributes": variation_list if variation_list else None,
            },
            "variation_attributes": variation_list if variation_list else None,
        }
        if debug_nombre:
            item_obj["__nombre_src"] = nombre_src
            item_obj["__nombre_candidates"] = {
                "onombre": cand_onombre,
                "nombre": cand_nombre,
                "ARTICULO": cand_articulo,
                "sku": cand_sku,
                "seller_sku": cand_seller,
            }
        # limpiar None
        if not item_obj["item"]["variation_attributes"]:
            item_obj["item"].pop("variation_attributes", None)
        if not item_obj["variation_attributes"]:
            item_obj.pop("variation_attributes", None)
        return {
            "order_id": it.get("order_id"),
            "pack_id": it.get("pack_id"),
            "shipping_id": it.get("shipping_id"),
            "printed": it.get("printed") or 0,
            "notes": it.get("COMENTARIO"),
            "items": [item_obj],
            "extra": {
                "COMENTARIO": it.get("COMENTARIO"),
                "mov_depo_hecho": it.get("mov_depo_hecho"),
                "mov_depo_numero": it.get("mov_depo_numero"),
                "mov_depo_obs": it.get("mov_depo_obs"),
                # Exponer también movimiento LOCAL para verificación directa desde el cliente/GUI
                "MOV_LOCAL_HECHO": it.get("MOV_LOCAL_HECHO"),
                "MOV_LOCAL_NUMERO": it.get("MOV_LOCAL_NUMERO"),
                "MOV_LOCAL_OBS": it.get("MOV_LOCAL_OBS"),
                "MOV_LOCAL_TS": it.get("MOV_LOCAL_TS"),
                "asignacion_detalle": it.get("asignacion_detalle"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/{order_id}/movement")
def post_movement(order_id: int, body: Dict[str, Any], acc: str = Query("acc1", regex="^acc1|acc2$"), debug: int = Query(0, ge=0, le=1), _=Depends(require_token)):
    try:
        # Solo campos permitidos
        payload = {
            k: body.get(k)
            for k in [
                "mov_depo_hecho",
                "mov_depo_numero",
                "tracking_number",
                "mov_depo_obs",
                # Movimiento LOCAL (nuevo)
                "MOV_LOCAL_HECHO",
                "MOV_LOCAL_NUMERO",
                "MOV_LOCAL_OBS",
                # Otros
                "asignacion_detalle",
            ]
            if body.get(k) is not None
        }
        try:
            # Log diagnóstico: mostrar acc, order_id y payload recibido
            print(
                f"🔎 POST /orders/{order_id}/movement acc={acc} payload_keys={list(payload.keys())} payload_sample="
                f"{ {k: (str(v)[:80] if isinstance(v, str) else v) for k, v in payload.items()} }"
            )
        except Exception:
            pass
        if not payload:
            raise HTTPException(status_code=400, detail="No fields to update")
        from .schemas import UpdateOrderRequest
        req = UpdateOrderRequest(**payload)
        # Resolver ID interno (clave primaria) desde order_id/pack_id textual
        internal_id: int
        db_name = None
        server_name = None
        try:
            with _orders_conn(acc) as cn:
                cur = cn.cursor()
                # Diagnóstico: imprimir base y servidor actuales
                try:
                    cur.execute("SELECT DB_NAME(), @@SERVERNAME")
                    dbrow = cur.fetchone()
                    db_name, server_name = (dbrow[0], dbrow[1]) if dbrow else (None, None)
                    print(f"🔎 post_movement using DB={db_name} SERVER={server_name} (acc={acc})")
                except Exception:
                    pass
                cur.execute(f"SELECT TOP 1 id FROM {_ORDERS_TABLE} WHERE [order_id] = ? OR [pack_id] = ?", str(order_id), str(order_id))
                row = cur.fetchone()
                internal_id = int(row[0]) if row and row[0] is not None else int(order_id)
        except Exception:
            internal_id = int(order_id)
        try:
            print(f"🔎 post_movement resolved internal_id={internal_id} for order_id={order_id} (acc={acc})")
        except Exception:
            pass
        # Diagnóstico: verificar columnas esperadas
        col_check = {}
        try:
            from .services import list_orders_columns
            cols = set([c.lower() for c in (list_orders_columns(acc) or [])])
            col_check = {
                "MOV_LOCAL_HECHO": ("mov_local_hecho" in cols),
                "MOV_LOCAL_NUMERO": ("mov_local_numero" in cols),
                "MOV_LOCAL_OBS": ("mov_local_obs" in cols),
                "MOV_LOCAL_TS": ("mov_local_ts" in cols),
            }
            print("🔎 post_movement column check:", col_check)
        except Exception:
            pass
        affected = update_order_service(internal_id, req, acc=acc)
        try:
            print(f"✅ post_movement UPDATE affected={affected} (acc={acc}) id={internal_id}")
        except Exception:
            pass
        fallback_used = False
        if affected == 0:
            # Intentar fallback por order_id/pack_id textual
            try:
                affected = update_order_by_order_or_pack(str(order_id), req, acc=acc)
                fallback_used = affected > 0
                print(f"🔁 post_movement fallback by order/pack affected={affected} (acc={acc}) order_or_pack={order_id}")
            except Exception as _fb_e:
                print(f"✗ post_movement fallback error: {_fb_e}")
        if affected == 0:
            raise HTTPException(status_code=404, detail="Order not found or no changes")
        if int(debug or 0) == 1:
            return {
                "ok": True,
                "affected": affected,
                "acc": acc,
                "db": db_name,
                "server": server_name,
                "order_id": str(order_id),
                "internal_id": internal_id,
                "payload_keys": list(payload.keys()),
                "columns": col_check,
                "fallback_used": bool(fallback_used),
            }
        return {"ok": True, "affected": affected, "fallback_used": bool(fallback_used)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/{order_id}/printed-moved")
def post_printed_moved(order_id: int, body: Dict[str, Any], acc: str = Query("acc1", regex="^acc1|acc2$"), _=Depends(require_token)):
    try:
        payload = {
            k: body.get(k)
            for k in [
                "printed",
                "mov_depo_hecho",
                "mov_depo_numero",
                "tracking_number",
                "mov_depo_obs",
                # Movimiento LOCAL (nuevo)
                "MOV_LOCAL_HECHO",
                "MOV_LOCAL_NUMERO",
                "MOV_LOCAL_OBS",
                # Otros
                "asignacion_detalle",
            ]
            if body.get(k) is not None
        }
        if not payload:
            raise HTTPException(status_code=400, detail="No fields to update")
        from .schemas import UpdateOrderRequest
        req = UpdateOrderRequest(**payload)
        # Resolver ID interno (clave primaria) desde order_id/pack_id textual
        internal_id: int
        try:
            with _orders_conn(acc) as cn:
                cur = cn.cursor()
                cur.execute(f"SELECT TOP 1 id FROM {_ORDERS_TABLE} WHERE [order_id] = ? OR [pack_id] = ?", str(order_id), str(order_id))
                row = cur.fetchone()
                internal_id = int(row[0]) if row and row[0] is not None else int(order_id)
        except Exception:
            internal_id = int(order_id)
        # Actualizar todas las filas por order_id/pack_id en la cuenta indicada
        affected = update_order_by_order_or_pack(str(order_id), req, acc=acc)
        if affected == 0:
            raise HTTPException(status_code=404, detail="Order not found or no changes")
        # Respuesta estilo ejemplo máximo
        out = {"ok": True, "order_id": str(order_id), **payload}
        try:
            out["updated_at"] = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        except Exception:
            out["updated_at"] = datetime.utcnow().isoformat() + "Z"
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/orders/columns")
def list_columns(acc: str = Query("acc1", regex="^acc1|acc2$"), _=Depends(require_token)):
    try:
        from .services import list_orders_columns
        return {"columns": list_orders_columns(acc)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/{order_id}", response_model=UpdateOrderResponse)
def update_order(order_id: int, body: UpdateOrderRequest, acc: str = Query("acc1", regex="^acc1|acc2$"), _=Depends(require_token)):
    try:
        # Resolver ID interno (clave primaria) a partir del order_id/pack_id que envía la UI
        internal_id: int
        str_oid = str(order_id)
        try:
            with _orders_conn(acc) as cn:
                cur = cn.cursor()
                cur.execute(f"SELECT TOP 1 id FROM {_ORDERS_TABLE} WHERE [order_id] = ? OR [pack_id] = ?", str_oid, str_oid)
                row = cur.fetchone()
                if row and row[0] is not None:
                    internal_id = int(row[0])
                else:
                    # Fallback: usar el número recibido como id interno (para casos en que la UI ya envía id)
                    internal_id = int(order_id)
        except Exception:
            internal_id = int(order_id)

        affected = update_order_service(order_id=internal_id, update=body, acc=acc)
        if affected == 0:
            raise HTTPException(status_code=404, detail="Order not found or no changes")
        return {"ok": True, "affected": affected}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orders/{order_id}/update-deposito-with-note")
def update_deposito_with_note(order_id: str, body: Dict[str, Any], acc: str = Query("acc1", regex="^acc1|acc2$"), force_q: int = Query(0, description="1=forzar registrando solicitud en comentario"), _=Depends(require_token)):
    """Actualiza depósito asignado y republica nota en MercadoLibre."""
    try:
        new_deposito = body.get('deposito_asignado')
        force = False
        try:
            force = bool(int(body.get('force', force_q)))
        except Exception:
            force = str(body.get('force', force_q)).lower() in ("1","true","yes") or int(force_q or 0) == 1
        if not new_deposito:
            raise HTTPException(status_code=400, detail="deposito_asignado requerido")
        
        # Primero obtener datos actuales de la orden
        with _orders_conn(acc) as conn:
            cursor = conn.cursor()
            # Importante: en la base, order_id es NVARCHAR; si pasamos int, SQL intenta convertir toda la columna a bigint y falla.
            # Por eso enviamos el parámetro como texto para evitar conversiones implícitas (error 8114).
            cursor.execute(
                """
                SELECT id, seller_id, qty, agotamiento_flag, mov_depo_obs, mov_depo_numero,
                       ISNULL(printed, 0) AS printed_flag,
                       ISNULL(ready_to_print, 0) AS rtp_flag,
                       shipping_subestado,
                       numero_movimiento
                FROM orders_meli WHERE [order_id] = ?
                """,
                str(order_id)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Orden no encontrada")
            
            internal_id, seller_id, qty, agotamiento_flag, mov_depo_obs, mov_depo_numero, printed_flag, rtp_flag, shipping_subestado, numero_movimiento = row

            # Guard server-side: no permitir cambio de depósito si ya está impresa o con movimiento
            try:
                printed_int = int(printed_flag or 0)
            except Exception:
                printed_int = 0
            sub = (shipping_subestado or "").strip().lower()
            movimiento_hecho = False
            try:
                # Si existe la col mov_depo_hecho, leerla; si no, inferir por numero_movimiento/mov_depo_numero
                cursor2 = conn.cursor()
                cursor2.execute("SELECT TOP 1 ISNULL(mov_depo_hecho, 0) FROM orders_meli WHERE [id] = ?", internal_id)
                r2 = cursor2.fetchone()
                if r2 is not None:
                    movimiento_hecho = int(r2[0] or 0) == 1
            except Exception:
                movimiento_hecho = False
            numero_movimiento_txt = (str(numero_movimiento).strip() if numero_movimiento is not None else "")
            mov_depo_numero_txt = (str(mov_depo_numero).strip() if mov_depo_numero is not None else "")

            bloqueo_por_estado = (printed_int == 1) or (sub == 'printed')
            bloqueo_por_mov = movimiento_hecho or bool(numero_movimiento_txt) or bool(mov_depo_numero_txt)
            if bloqueo_por_estado or bloqueo_por_mov:
                # Si no vino 'force', aplicar override de todas formas (política server-side solicitada)
                if not force:
                    force = True
                # Modo forzado: intentar bypass del trigger usando SESSION_CONTEXT y actualizar deposito_asignado en una misma conexión
                comentario_extra = f"FORCED DEPOT CHANGE {datetime.utcnow().isoformat()}Z -> {new_deposito}"
                with _orders_conn(acc) as conn2:
                    cur2 = conn2.cursor()
                    # 1) Setear bandera de sesión para que el trigger permita el cambio (ver script SQL con trigger ajustado)
                    try:
                        cur2.execute("EXEC sp_set_session_context N'ALLOW_DEPO_CHANGE', 1;")
                    except Exception:
                        pass
                    # 2) Actualizar COMENTARIO para trazabilidad
                    prev = None
                    try:
                        cur2.execute("SELECT TOP 1 COMENTARIO FROM orders_meli WHERE [id] = ?", internal_id)
                        r = cur2.fetchone(); prev = r[0] if r else None
                    except Exception:
                        prev = None
                    new_comentario = (str(prev) + " | " + comentario_extra).strip() if prev else comentario_extra
                    try:
                        cur2.execute("UPDATE orders_meli SET COMENTARIO = ? WHERE [id] = ?", new_comentario, internal_id)
                    except Exception:
                        pass
                    # 3) Intentar cambio de depósito forzado
                    cur2.execute("UPDATE orders_meli SET deposito_asignado = ? WHERE [id] = ?", str(new_deposito), internal_id)
                    conn2.commit()
                # Publicar nota opcionalmente
                note_result = {"ok": False, "error": "publicación de nota deshabilitada"}
                if PUBLISH_NOTE_ON_DEPO_CHANGE and publish_note_upsert:
                    try:
                        note_result = publish_note_upsert(
                            order_id=str(order_id),
                            seller_id=seller_id,
                            deposito_asignado=new_deposito,
                            qty=qty or 1,
                            agotado=bool(agotamiento_flag),
                            observacion_mov=f"(FORZADO) {comentario_extra}",
                            numero_mov=mov_depo_numero,
                            dry_run=False
                        )
                    except Exception as _e:
                        note_result = {"ok": False, "error": str(_e)[:200]}
                return JSONResponse(
                    status_code=200,
                    content={
                        "ok": True,
                        "forced": True,
                        "message": "Depósito cambiado con override de administrador",
                        "note_published": note_result.get('ok', False),
                    }
                )
        
        # Actualizar depósito en BD
        update_req = UpdateOrderRequest(deposito_asignado=new_deposito)
        # Importante: update_order_service actualiza por clave primaria [id]; usar el id interno
        try:
            affected = update_order_service(order_id=int(internal_id), update=update_req, acc=acc)
        except Exception as e:
            # Si el trigger de SQL bloquea el cambio, intentar override automático usando SESSION_CONTEXT
            raw = str(e)
            low = raw.lower()
            blocked = (
                ("deposito_asignado" in low and "cannot be changed" in low) or
                ("[deposito_asignado]" in low and "cannot be changed" in low) or
                ("write-once" in low and "deposito" in low) or
                ("50000" in low and "deposito" in low and "changed" in low)
            )
            if blocked:
                comentario_extra = f"FORCED DEPOT CHANGE {datetime.utcnow().isoformat()}Z -> {new_deposito}"
                with _orders_conn(acc) as conn2:
                    cur2 = conn2.cursor()
                    try:
                        cur2.execute("EXEC sp_set_session_context N'ALLOW_DEPO_CHANGE', 1;")
                    except Exception:
                        pass
                    # Trazabilidad en COMENTARIO
                    prev = None
                    try:
                        cur2.execute("SELECT TOP 1 COMENTARIO FROM orders_meli WHERE [id] = ?", internal_id)
                        r = cur2.fetchone(); prev = r[0] if r else None
                    except Exception:
                        prev = None
                    new_comentario = (str(prev) + " | " + comentario_extra).strip() if prev else comentario_extra
                    try:
                        cur2.execute("UPDATE orders_meli SET COMENTARIO = ? WHERE [id] = ?", new_comentario, internal_id)
                    except Exception:
                        pass
                    # Cambio forzado de depósito
                    cur2.execute("UPDATE orders_meli SET deposito_asignado = ? WHERE [id] = ?", str(new_deposito), internal_id)
                    conn2.commit()
                return JSONResponse(status_code=200, content={
                    "ok": True,
                    "forced": True,
                    "message": "Depósito cambiado con override de administrador"
                })
            raise
        
        # Republicar nota en MercadoLibre (deshabilitado por defecto). Controlado por env PUBLISH_NOTE_ON_DEPO_CHANGE.
        note_result = {"ok": False, "error": "publicación de nota deshabilitada"}
        if PUBLISH_NOTE_ON_DEPO_CHANGE:
            print(f"🔄 Intentando republicar nota para orden {order_id}")
            print(f"📦 publish_note_upsert disponible: {publish_note_upsert is not None}")
            if publish_note_upsert:
                try:
                    print(f"📝 Datos para nota: deposito={new_deposito}, seller_id={seller_id}, qty={qty}")
                    note_result = publish_note_upsert(
                        order_id=str(order_id),
                        seller_id=seller_id,
                        deposito_asignado=new_deposito,
                        qty=qty or 1,
                        agotado=bool(agotamiento_flag),
                        observacion_mov=mov_depo_obs or f"Depósito cambiado a {new_deposito}",
                        numero_mov=mov_depo_numero,
                        dry_run=False
                    )
                    print(f"📋 Resultado publicación nota: {note_result}")
                    # Si la nota se publicó exitosamente, actualizar el campo notes en BD
                    if note_result.get('ok') and note_result.get('note'):
                        with _orders_conn() as conn:
                            cursor = conn.cursor()
                            update_sql = "UPDATE orders_meli SET note = ? WHERE order_id = ?"
                            cursor.execute(update_sql, (note_result.get('note', ''), order_id))
                            conn.commit()
                            print(f"✅ Campo notes actualizado en BD para orden {order_id}")
                except Exception as e:
                    print(f"❌ Error publicando nota para orden {order_id}: {e}")
                    import traceback
                    traceback.print_exc()
                    note_result = {"ok": False, "error": str(e)}
            else:
                print("❌ Módulo note_publisher_10 no está disponible")
        
        return {
            "ok": True, 
            "affected": affected,
            "note_published": note_result.get('ok', False),
            "note_error": note_result.get('error', '') if not note_result.get('ok') else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Mapear error de trigger/DB a 409 para el cliente si corresponde (manejar variantes)
        raw = str(e)
        low = raw.lower()
        if (
            ("deposito_asignado" in low and "cannot be changed" in low) or
            ("[deposito_asignado]" in low and "cannot be changed" in low) or
            ("write-once" in low and "deposito" in low) or
            ("50000" in low and "deposito" in low and "changed" in low)
        ):
            raise HTTPException(status_code=409, detail="No se puede cambiar deposito_asignado después de movimiento/impresión")
        print(f"Error updating deposito with note for order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===================== Stats: Movements =====================
@app.get("/stats/movements")
def stats_movements(
    request: Request,
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    depot: Optional[str] = Query(None, description="Filtro por deposito_asignado (exacto)"),
    include_packs: int = Query(0, ge=0, le=1, description="1=devolver lista de packs ejemplo"),
    _=Depends(require_token),
):
    """Cuenta paquetes únicos con movimiento (mov_depo_hecho=1) en el rango [from, to).
    Usa DISTINCT por pack_id si existe, si no, por order_id.
    """
    def _parse_iso(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    dt_from = _parse_iso(from_)
    dt_to = _parse_iso(to)
    if dt_from is None or dt_to is None:
        raise HTTPException(status_code=400, detail="Parámetros 'from' y 'to' deben ser ISO8601")

    key = "pack_id" if _orders_col_exists("pack_id") else "order_id"
    where = ["[mov_depo_hecho] = 1"]
    args: List[Any] = []

    if _orders_col_exists("mov_depo_ts"):
        where.append("[mov_depo_ts] >= ? AND [mov_depo_ts] < ?")
        args.extend([dt_from, dt_to])
    else:
        col = "date_closed" if _orders_col_exists("date_closed") else "date_created"
        where.append(f"[{col}] >= ? AND [{col}] < ?")
        args.extend([dt_from, dt_to])

    if depot and _orders_col_exists("deposito_asignado"):
        where.append("[deposito_asignado] = ?")
        args.append(depot)

    where_sql = " WHERE " + " AND ".join(where)
    sql = f"SELECT COUNT(DISTINCT [{key}]) FROM {_ORDERS_TABLE}{where_sql}"

    result = {"from": dt_from.isoformat(), "to": dt_to.isoformat(), "count": 0}
    items_preview: List[Dict[str, Any]] = []
    with _orders_conn() as cn:
        cur = cn.cursor()
        cur.execute(sql, *args)
        result["count"] = int(cur.fetchone()[0] or 0)
        if include_packs == 1:
            cols = [c for c in (key, "mov_depo_ts", "mov_depo_numero") if _orders_col_exists(c) or c == key]
            sel = ", ".join(f"[{c}]" for c in cols)
            sql2 = f"SELECT TOP 50 {sel} FROM {_ORDERS_TABLE}{where_sql} ORDER BY [mov_depo_ts] DESC"
            try:
                cur.execute(sql2, *args)
                rows = cur.fetchall() or []
                names = [d[0] for d in cur.description]
                for r in rows:
                    items_preview.append({names[i]: r[i] for i in range(len(names))})
            except Exception:
                pass
    if include_packs == 1:
        result["packs"] = items_preview
    return result


@app.get("/stats/movements/today")
def stats_movements_today(_=Depends(require_token)):
    """Cuenta paquetes movidos hoy según timezone configurada (SERVER_TZ)."""
    tz = SERVER_TZ or "Argentina Standard Time"
    key = "pack_id" if _orders_col_exists("pack_id") else "order_id"
    sql = (
        f"SELECT COUNT(DISTINCT [{key}]) "
        f"FROM {_ORDERS_TABLE} "
        f"WHERE [mov_depo_hecho] = 1 AND [mov_depo_ts] IS NOT NULL "
        f"AND CONVERT(date, [mov_depo_ts] AT TIME ZONE ?) = CONVERT(date, SYSUTCDATETIME() AT TIME ZONE ?)"
    )

    with _orders_conn() as cn:
        cur = cn.cursor()
        try:
            cur.execute(sql, tz, tz)
            count = int(cur.fetchone()[0] or 0)
        except Exception as e:
            try:
                sql2 = f"SELECT COUNT(DISTINCT [{key}]) FROM {_ORDERS_TABLE} WHERE [mov_depo_hecho]=1"
                cur.execute(sql2)
                count = int(cur.fetchone()[0] or 0)
            except Exception:
                raise HTTPException(status_code=500, detail=str(e))

    with _orders_conn() as cn:
        cur = cn.cursor()
        try:
            cur.execute("SELECT CONVERT(date, SYSUTCDATETIME() AT TIME ZONE ?)", tz)
            date_str = str(cur.fetchone()[0])
        except Exception:
            date_str = datetime.utcnow().date().isoformat()

    return {"date": date_str, "count": count}

@app.get("/favicon.ico")
def favicon():
    # Evitar 404 en navegadores: 204 sin cuerpo
    return Response(status_code=204)


# ------------------------------
# Chat tips (ayuda rápida)
# ------------------------------
CHAT_TIPS_MD = (
    """
## Ejemplos útiles (copiar y pegar)

- Órdenes sin imprimir hoy en Bahía: `pedidos de hoy para bahía sin imprimir`
- Listas para imprimir en DEPO: `¿qué órdenes están listas para imprimir en DEPO?`
- Ventas de un SKU hoy: `ventas del SKU NDPMB0E770AR048 de hoy`
- Total vendidos por SKU en la última semana: `¿cuántos se vendieron de NDPMB0E770AR048 en la última semana?`
- ¿Se despachó este SKU hoy?: `se despachó hoy el SKU 201-HF500?`
- Buscar por título: `mostrame ventas de "campera softshell"`
- Estado de una orden puntual: `estado de la orden 20000127656386930`
- Marcar impresa: `marcar impresa la orden 20000127656386930`
"""
)


@app.get("/api/chat/tips")
def chat_tips(_=Depends(require_token)):
    tips = [
        # Operativa diaria y depósitos
        "pedidos de hoy para bahía sin imprimir",
        "¿qué órdenes están listas para imprimir en DEPO?",
        "¿qué preparar hoy desde MUNDOROC?",
        # Ventas y conteos por SKU
        "ventas del SKU NDPMB0E770AR048 de hoy",
        "¿cuántos se vendieron de 201-HF500 en la última semana?",
        # Envíos y estado
        "se despachó hoy el SKU 201-HF500?",
        "estado de la orden 20000127656386930",
        # Acciones
        "marcar impresa la orden 20000127656386930",
        # Búsquedas por título
        "mostrame ventas de \"campera softshell\"",
    ]
    return {"title": "Cómo hablarle a la IA", "tips": tips, "markdown": CHAT_TIPS_MD}


@app.get("/chat/help")
def chat_help_page():
    html = f"""
<!doctype html>
<html lang=\"es\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Ayuda - Chat IA</title>
    <style>
      body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 20px; line-height: 1.5; }}
      code {{ background:#f4f4f4; padding:2px 4px; border-radius:4px; }}
      .card {{ max-width: 800px; margin: auto; border:1px solid #ddd; border-radius:8px; padding:16px; }}
    </style>
  </head>
  <body>
    <div class=\"card\">
      <h1>Cómo hablarle a la IA</h1>
      <p>Ejemplos útiles que podés pegar en el chat:</p>
      <ul>
        <li>título de la orden 123456</li>
        <li>la orden 123456 está impresa?</li>
        <li>¿cuántos paquetes se imprimieron hoy?</li>
        <li>¿qué tengo que preparar hoy desde DEPO?</li>
        <li>¿cuántos se vendieron de NDPMB0E770AR048?</li>
        <li>mostrame ventas de <code>\"zapatilla runner azul\"</code></li>
      </ul>
      <p><a href=\"/ui/chat\">Volver al chat</a></p>
    </div>
  </body>
</html>
"""
    return HTMLResponse(content=html, status_code=200)
