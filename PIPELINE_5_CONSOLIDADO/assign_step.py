"""
Paso de asignación de depósito y manejo de stock.

- Consulta stock por depósito via Dragon API (modules/07_dragon_api.py)
- Calcula stock reservado en BD (órdenes ya asignadas y no impresas)
- Elige depósito ganador con `assigner.choose_winner`
- Actualiza columnas en `orders_meli`:
  deposito_asignado, stock_real, stock_reservado, resultante,
  agotamiento_flag, asignado_flag, fecha_asignacion, observacion_movimiento
"""
from typing import Dict, Tuple
from datetime import datetime
import os
import sys
import pyodbc
from importlib.machinery import SourceFileLoader
import logging

import os, sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
MODULES_DIR = os.path.join(PROJECT_ROOT, 'modules')
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)
from importlib.machinery import SourceFileLoader
DRAGON_API_PATH = os.path.join(MODULES_DIR, '07_dragon_api.py')
from assigner import choose_winner
from database_utils import log_movement

# Cargar 07_dragon_api.py (nombre inválido para import directo) desde modules/
BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))
MODULES_DIR = os.path.join(PROJECT_ROOT, 'modules')
DRAGON_API_PATH = os.path.join(MODULES_DIR, '07_dragon_api.py')
# Asegurar que el paquete 'modules' sea importable
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
dragon_api = SourceFileLoader('dragon_api07', DRAGON_API_PATH).load_module()
get_stock_per_deposit = dragon_api.get_stock_per_deposit

# Timeout configurable para Dragon API
DRAGON_TIMEOUT_SECS = int(os.getenv('DRAGON_TIMEOUT_SECS', '180'))

# Logger del módulo
logger = logging.getLogger(__name__)

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=.\\SQLEXPRESS;"
    "DATABASE=meli_stock;"
    "Trusted_Connection=yes;"
)


def _dragon_query_key(sku: str) -> str:
    """Normaliza la clave de consulta a Dragonfish.

    Regla puntual: para TDRK20-** se consulta por "TDRK20" (búsqueda por artículo),
    ya que la API lista variantes como TDRK20-15, TDRK20-1K bajo el prefijo.
    """
    s = str(sku or '').upper()
    # Regla TDRK20 (prefijo)
    if s.startswith('TDRK20'):
        return 'TDRK20'
    # Normalización general: colapsar guiones redundantes y quitar sufijos vacíos
    # Ej.: "201-HF500--" -> ["201","HF500"] -> "201-HF500"
    try:
        parts = [p for p in s.split('-') if p != '']
        norm = '-'.join(parts) if parts else s
        return norm
    except Exception:
        return s


def _get_reserved_by_depot(cursor: pyodbc.Cursor, sku: str) -> Dict[str, int]:
    """Suma qty reservada por depósito para un SKU en órdenes asignadas no impresas."""
    cursor.execute(
        """
        SELECT UPPER(ISNULL(deposito_asignado,'')) AS depot, SUM(TRY_CAST(qty AS INT)) AS reservado
        FROM orders_meli
        WHERE sku = ?
          AND asignado_flag = 1
          AND ISNULL(UPPER(shipping_subestado),'') <> 'PRINTED'
          AND ISNULL(deposito_asignado,'') <> ''
        GROUP BY UPPER(ISNULL(deposito_asignado,''))
        """,
        (sku,)
    )
    res: Dict[str, int] = {}
    for depot, reservado in cursor.fetchall():
        res[str(depot).upper()] = int(reservado or 0)
    return res


def _merge_stock_with_reserved(stock: Dict[str, Dict[str, int]], reserved: Dict[str, int]) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for depot, data in stock.items():
        tot = int((data or {}).get("total", 0))
        res = int(reserved.get(depot.upper(), 0))
        out[depot.upper()] = {"total": tot, "reserved": res}
    # Incluir depósitos con reserva pero sin respuesta de stock (por seguridad)
    for depot, res in reserved.items():
        if depot.upper() not in out:
            out[depot.upper()] = {"total": 0, "reserved": int(res or 0)}
    return out


def _get_existing_columns(cur: pyodbc.Cursor) -> set:
    """Devuelve el set de columnas existentes en orders_meli (cache simple por conexión)."""
    try:
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'orders_meli'")
        return {str(r[0]).lower() for r in cur.fetchall()}
    except Exception:
        return set()


def _tot_from_stock(stock: Dict[str, Dict[str, int]], depot_code: str) -> int:
    try:
        d = stock.get(depot_code) or {}
        return int(d.get('total') or 0)
    except Exception:
        return 0


def _update_per_depot_stock_columns(cur: pyodbc.Cursor, db_id: int, stock: Dict[str, Dict[str, int]]):
    """Actualiza columnas stock_* por depósito si existen en la tabla.

    Mapea claves conocidas de depósitos a columnas: stock_dep, stock_mundoal, stock_monbahia,
    stock_mtgbbps, stock_mundocab, stock_nqnshop, stock_mtgcom, stock_mtgroca, stock_mundoroc.
    """
    existing = _get_existing_columns(cur)
    col_map = {
        'stock_dep': _tot_from_stock(stock, 'DEP'),
        'stock_mdq': _tot_from_stock(stock, 'MDQ'),
        'stock_mundoal': _tot_from_stock(stock, 'MUNDOAL'),
        'stock_monbahia': _tot_from_stock(stock, 'MONBAHIA'),
        'stock_mtgbbps': _tot_from_stock(stock, 'MTGBBPS'),
        'stock_mtgcba': _tot_from_stock(stock, 'MTGCBA'),
        'stock_mundocab': _tot_from_stock(stock, 'MUNDOCAB'),
        'stock_nqnshop': _tot_from_stock(stock, 'NQNSHOP'),
        'stock_mtgjbj': _tot_from_stock(stock, 'MTGJBJ'),
        'stock_nqnalb': _tot_from_stock(stock, 'NQNALB'),
        'stock_mtgcom': _tot_from_stock(stock, 'MTGCOM'),
        'stock_mtgroca': _tot_from_stock(stock, 'MTGROCA'),
        'stock_mundoroc': _tot_from_stock(stock, 'MUNDOROC'),
        # Control: stock del depósito MELI (no afecta asignación)
        'depo_meli': _tot_from_stock(stock, 'MELI'),
        # Control: stock del depósito WOO (no afecta asignación)
        'depo_woo': _tot_from_stock(stock, 'WOO'),
    }
    # Construir SET solo con columnas que existan
    sets = []
    params = []
    for col, val in col_map.items():
        if col.lower() in existing:
            sets.append(f"{col} = ?")
            params.append(int(val))
    if not sets:
        return
    sql = f"""
        UPDATE orders_meli
        SET {', '.join(sets)}
        WHERE id = ?
    """
    params.append(int(db_id))
    cur.execute(sql, tuple(params))


def _post_assignment_flags_update(cur: pyodbc.Cursor, db_id: int, resultante: int):
    """Actualiza flags adicionales si las columnas existen:
    - agotamiento_flag = 1 si resultante <= 0, si existe la columna.
    - fecha_orden = GETDATE() solo si existe la columna y está NULL (fallback cuando falta origen ML).
    """
    existing = _get_existing_columns(cur)
    sets = []
    params = []
    if 'agotamiento_flag' in existing:
        sets.append("agotamiento_flag = ?")
        params.append(1 if int(resultante) <= 0 else 0)
    if 'fecha_orden' in existing:
        # Solo setear si está NULL, para no pisar fecha real
        sets.append("fecha_orden = ISNULL(fecha_orden, GETDATE())")
    if not sets:
        return
    sql = f"""
        UPDATE orders_meli
        SET {', '.join(sets)}
        WHERE id = ?
    """
    params.append(int(db_id))
    cur.execute(sql, tuple(params))


def assign_recent_pending(limit: int = 50) -> Dict[str, int]:
    """Asigna depósito a las últimas órdenes pendientes.

    Retorna contadores: {'assigned': X, 'exhausted': Y, 'errors': Z}
    """
    summary = {"assigned": 0, "exhausted": 0, "errors": 0}
    try:
        with pyodbc.connect(CONNECTION_STRING) as conn:
            cur = conn.cursor()
            # Buscar pendientes más recientes por fecha de actualización
            cur.execute(
                """
                SELECT TOP (?) id, order_id, sku, TRY_CAST(qty AS INT) AS qty
                FROM orders_meli
                WHERE (asignado_flag IS NULL OR asignado_flag = 0)
                  AND ISNULL(UPPER(estado),'') <> 'CANCELLED'
                  AND ISNULL(UPPER(shipping_subestado),'') <> 'PRINTED'
                ORDER BY fecha_actualizacion DESC, id DESC
                """,
                (limit,)
            )
            rows = cur.fetchall()
            for row in rows:
                db_id, order_id, sku, qty = row
                if not sku or not qty or qty <= 0:
                    continue
                try:
                    logger.info(f"➡️ Asignando (pendientes): id={db_id} order={order_id} sku={sku} qty={qty}")
                    # Stock Dragonfish por depósito
                    qkey = _dragon_query_key(sku)
                    stock_raw = get_stock_per_deposit(qkey, timeout=DRAGON_TIMEOUT_SECS)
                    logger.info(f"✅ Stock obtenido para {sku} (id={db_id}) [qkey={qkey}]")
                    # Reservas en BD por depósito (no impresas)
                    reserved = _get_reserved_by_depot(cur, sku)
                    stock = _merge_stock_with_reserved(stock_raw, reserved)

                    winner = choose_winner(stock, qty)
                    if not winner:
                        # Agotado
                        # Registrar movimiento: AGOTADO
                        try:
                            log_movement(order_id=str(order_id), sku=str(sku), qty=int(qty or 0),
                                         accion='AGOTADO', deposito=None, disponible=0, resultante=0,
                                         nota='Sin stock suficiente')
                        except Exception:
                            pass
                        cur.execute(
                            """
                            UPDATE orders_meli
                            SET agotamiento_flag = 1,
                                asignado_flag = 0,
                                stock_real = 0,
                                fecha_actualizacion = GETDATE(),
                                observacion_movimiento = CONCAT(ISNULL(observacion_movimiento,''),
                                    '; ', CONVERT(varchar(16), GETDATE(), 120), ' - Sin stock suficiente')
                            WHERE id = ?
                            """,
                            (db_id,)
                        )
                        # Persistir columnas por depósito para auditoría (incluye depo_woo/depo_meli)
                        try:
                            _update_per_depot_stock_columns(cur, db_id, stock)
                        except Exception:
                            pass
                        # Observación de no asignación
                        try:
                            _update_observacion_asignado(cur, db_id, "Sin stock en ningún depósito")
                        except Exception:
                            pass
                        # Commit por iteración (agotado)
                        try:
                            conn.commit()
                            logger.info(f"💾 Commit (pendientes agotado) id={db_id}")
                        except Exception as ce:
                            logger.warning(f"⚠️ Commit failed (pendientes agotado) id={db_id}: {ce}")
                        summary["exhausted"] += 1
                        continue

                    depot, total, reservado = winner
                    disponible = max(int(total or 0) - int(reservado or 0), 0)
                    new_reserved = int(reservado or 0) + int(qty or 0)
                    resultante = max(int(total or 0) - new_reserved, 0)

                    # Registrar movimiento: ASIGNACION
                    try:
                        log_movement(order_id=str(order_id), sku=str(sku), qty=int(qty or 0),
                                     accion='ASIGNACION', deposito=str(depot), disponible=int(disponible),
                                     resultante=int(resultante), nota=None)
                    except Exception:
                        pass

                    cur.execute(
                        """
                        UPDATE orders_meli
                        SET deposito_asignado = ?,
                            stock_real = ?,
                            stock_reservado = ?,
                            resultante = ?,
                            asignado_flag = 1,
                            fecha_asignacion = GETDATE(),
                            fecha_actualizacion = GETDATE(),
                            observacion_movimiento = CONCAT(ISNULL(observacion_movimiento,''),
                                '; ', CONVERT(varchar(16), GETDATE(), 120), ' - Asignado ', ?, ' (', ?, '→', ?, ')')
                        WHERE id = ?
                        """,
                        (
                            depot,
                            int(total or 0),
                            int(new_reserved),
                            int(resultante),
                            depot,
                            int(max(disponible - int(qty or 0), 0)),
                            int(resultante),
                            db_id,
                        ),
                    )
                    # Observación de asignación
                    try:
                        _update_observacion_asignado(cur, db_id, f"Asignado a {depot}")
                    except Exception:
                        pass
                    # Persistir columnas de stock por depósito (si existen)
                    try:
                        _update_per_depot_stock_columns(cur, db_id, stock)
                    except Exception:
                        pass
                    # Flags adicionales si existen (agotamiento_flag, fecha_orden)
                    try:
                        _post_assignment_flags_update(cur, db_id, resultante)
                    except Exception:
                        pass
                    # Commit por iteración (asignado)
                    try:
                        conn.commit()
                        logger.info(f"💾 Commit (pendientes asignado) id={db_id} depot={depot}")
                    except Exception as ce:
                        logger.warning(f"⚠️ Commit failed (pendientes asignado) id={db_id}: {ce}")
                    summary["assigned"] += 1
                except Exception as e:
                    # Registrar movimiento de error para tener traza
                    try:
                        log_movement(order_id=str(order_id), sku=str(sku or ''), qty=int(qty or 0),
                                     accion='ERROR', deposito=None, disponible=None, resultante=None,
                                     nota=f"{type(e).__name__}: {e}")
                    except Exception:
                        pass
                    print(f"❌ Error asignando orden {order_id} ({sku}): {e}")
                    summary["errors"] += 1
                    continue
            conn.commit()
    except Exception as e:
        print(f"❌ Error general en assign_recent_pending: {e}")
        summary["errors"] += 1
    return summary


def assign_ready_to_print_missing_stock(limit: int = 50) -> Dict[str, int]:
    """Asigna depósito SOLO a órdenes READY_TO_PRINT que aún no tienen stock/depósito.

    Criterios:
      - shipping_subestado = 'READY_TO_PRINT'
      - No impresas (excluye 'PRINTED')
      - No canceladas
      - asignado_flag IS NULL/0
      - (stock_real IS NULL OR deposito_asignado IS NULL)

    Retorna contadores: {'assigned': X, 'exhausted': Y, 'errors': Z}
    """
    summary = {"assigned": 0, "exhausted": 0, "errors": 0}
    try:
        with pyodbc.connect(CONNECTION_STRING) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP (?) id, order_id, sku, TRY_CAST(qty AS INT) AS qty
                FROM orders_meli
                WHERE ISNULL(UPPER(shipping_subestado),'') = 'READY_TO_PRINT'
                  AND ISNULL(UPPER(estado),'') <> 'CANCELLED'
                  AND ISNULL(UPPER(shipping_subestado),'') <> 'PRINTED'
                  AND (asignado_flag IS NULL OR asignado_flag = 0)
                  AND (stock_real IS NULL OR deposito_asignado IS NULL)
                ORDER BY fecha_actualizacion DESC, id DESC
                """,
                (limit,)
            )
            rows = cur.fetchall()
            for row in rows:
                db_id, order_id, sku, qty = row
                if not sku or not qty or qty <= 0:
                    continue
                try:
                    logger.info(f"➡️ Asignando (RTP): id={db_id} order={order_id} sku={sku} qty={qty}")
                    # Stock Dragonfish por depósito
                    qkey = _dragon_query_key(sku)
                    stock_raw = get_stock_per_deposit(qkey, timeout=DRAGON_TIMEOUT_SECS)
                    logger.info(f"✅ Stock obtenido para {sku} (id={db_id}) [RTP qkey={qkey}]")
                    # Reservas en BD por depósito (no impresas)
                    reserved = _get_reserved_by_depot(cur, sku)
                    stock = _merge_stock_with_reserved(stock_raw, reserved)

                    winner = choose_winner(stock, qty)
                    if not winner:
                        try:
                            log_movement(order_id=str(order_id), sku=str(sku), qty=int(qty or 0),
                                         accion='AGOTADO', deposito=None, disponible=0, resultante=0,
                                         nota='Sin stock suficiente (READY_TO_PRINT)')
                        except Exception:
                            pass
                        cur.execute(
                            """
                            UPDATE orders_meli
                            SET agotamiento_flag = 1,
                                asignado_flag = 0,
                                stock_real = 0,
                                fecha_actualizacion = GETDATE(),
                                observacion_movimiento = CONCAT(ISNULL(observacion_movimiento,''),
                                    '; ', CONVERT(varchar(16), GETDATE(), 120), ' - Sin stock suficiente (RTP)')
                            WHERE id = ?
                            """,
                            (db_id,)
                        )
                        # Persistir columnas por depósito para auditoría (incluye depo_woo/depo_meli)
                        try:
                            _update_per_depot_stock_columns(cur, db_id, stock)
                        except Exception:
                            pass
                        # Observación de no asignación
                        try:
                            _update_observacion_asignado(cur, db_id, "Sin stock en ningún depósito")
                        except Exception:
                            pass
                        # Commit por iteración (RTP agotado)
                        try:
                            conn.commit()
                            logger.info(f"💾 Commit (RTP agotado) id={db_id}")
                        except Exception as ce:
                            logger.warning(f"⚠️ Commit failed (RTP agotado) id={db_id}: {ce}")
                        summary["exhausted"] += 1
                        continue

                    depot, total, reservado = winner
                    disponible = max(int(total or 0) - int(reservado or 0), 0)
                    # Calcular reservado nuevo y resultante de forma consistente
                    new_reserved = int(reservado or 0) + int(qty or 0)
                    resultante = max(int(total or 0) - new_reserved, 0)

                    try:
                        log_movement(order_id=str(order_id), sku=str(sku), qty=int(qty or 0),
                                     accion='ASIGNACION', deposito=str(depot), disponible=int(disponible),
                                     resultante=int(resultante), nota='READY_TO_PRINT')
                    except Exception:
                        pass

                    cur.execute(
                        """
                        UPDATE orders_meli
                        SET deposito_asignado = ?,
                            stock_real = ?,
                            stock_reservado = ?,
                            resultante = ?,
                            asignado_flag = 1,
                            fecha_asignacion = GETDATE(),
                            fecha_actualizacion = GETDATE(),
                            observacion_movimiento = CONCAT(ISNULL(observacion_movimiento,''),
                                '; ', CONVERT(varchar(16), GETDATE(), 120), ' - Asignado (RTP) ', ?, ' (', ?, '→', ?, ')')
                        WHERE id = ?
                        """,
                        (
                            depot,
                            int(total or 0),
                            int(new_reserved),
                            int(resultante),
                            depot,
                            int(max(disponible - int(qty or 0), 0)),
                            int(resultante),
                            db_id,
                        ),
                    )
                    # Observación de asignación
                    try:
                        _update_observacion_asignado(cur, db_id, f"Asignado a {depot}")
                    except Exception:
                        pass
                    # Persistir columnas de stock por depósito (si existen)
                    try:
                        _update_per_depot_stock_columns(cur, db_id, stock)
                    except Exception:
                        pass
                    # Flags adicionales si existen (agotamiento_flag, fecha_orden)
                    try:
                        _post_assignment_flags_update(cur, db_id, resultante)
                    except Exception:
                        pass
                    # Commit por iteración (RTP asignado)
                    try:
                        conn.commit()
                        logger.info(f"💾 Commit (RTP asignado) id={db_id} depot={depot}")
                    except Exception as ce:
                        logger.warning(f"⚠️ Commit failed (RTP asignado) id={db_id}: {ce}")
                    summary["assigned"] += 1
                except Exception as e:
                    try:
                        log_movement(order_id=str(order_id), sku=str(sku or ''), qty=int(qty or 0),
                                     accion='ERROR', deposito=None, disponible=None, resultante=None,
                                     nota=f"{type(e).__name__}: {e}")
                    except Exception:
                        pass
                    print(f"❌ Error asignando orden {order_id} ({sku}) [RTP]: {e}")
                    summary["errors"] += 1
                    continue
            conn.commit()
    except Exception as e:
        print(f"❌ Error general en assign_ready_to_print_missing_stock: {e}")
        summary["errors"] += 1
    return summary
