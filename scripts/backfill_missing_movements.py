"""
Backfill de movimientos faltantes en orders_meli
================================================

- Busca órdenes sin movimiento (numero_movimiento vacío y movimiento_realizado/mov_depo_hecho en 0/NULL)
- Para cada orden:
  * Consulta stock por depósito usando modules/07_dragon_api.get_stock_per_deposit (con fallback por depósito)
  * Elige depósito con modules/07_assigner.choose_winner (si no hay, usa deposito_asignado si existe)
  * Ejecuta movimiento negativo con modules/09_dragon_movement.move_stock_woo_to_woo
  * Actualiza columnas: movimiento_realizado, fecha_movimiento, numero_movimiento, observacion_movimiento,
    stock_reservado += qty, deposito_asignado (si estaba vacío)

Uso:
  python scripts/backfill_missing_movements.py --limit 200 --desde "2025-09-06" --solo-ready-to-print 1

Depende de variables en config/.env (SQLSERVER_APP_CONN_STR, DRAGON_*) que ya usa el proyecto.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
import logging
from typing import Any, Optional

import pyodbc

# Cargar .env del proyecto
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*args: Any, **kwargs: Any) -> None:
        return None

PROJ_ROOT = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(PROJ_ROOT, 'config', '.env')
if os.path.isfile(ENV_PATH):
    load_dotenv(ENV_PATH, override=True)
else:
    load_dotenv()

# Import dinámico de módulos del paquete modules/
import importlib.util as _ilu
MODULES_DIR = os.path.join(PROJ_ROOT, 'modules')

# get_stock_per_deposit
_spec_dapi = _ilu.spec_from_file_location('modules.07_dragon_api', os.path.join(MODULES_DIR, '07_dragon_api.py'))
_mod_dapi = _ilu.module_from_spec(_spec_dapi) if _spec_dapi and _spec_dapi.loader else None
if _spec_dapi and _spec_dapi.loader and _mod_dapi:
    _spec_dapi.loader.exec_module(_mod_dapi)  # type: ignore[attr-defined]
get_stock_per_deposit = getattr(_mod_dapi, 'get_stock_per_deposit', None)

# choose_winner
_spec_asg = _ilu.spec_from_file_location('modules.07_assigner', os.path.join(MODULES_DIR, '07_assigner.py'))
_mod_asg = _ilu.module_from_spec(_spec_asg) if _spec_asg and _spec_asg.loader else None
if _spec_asg and _spec_asg.loader and _mod_asg:
    _spec_asg.loader.exec_module(_mod_asg)  # type: ignore[attr-defined]
choose_winner = getattr(_mod_asg, 'choose_winner', None)

# move_stock_woo_to_woo
_spec_mov = _ilu.spec_from_file_location('modules.09_dragon_movement', os.path.join(MODULES_DIR, '09_dragon_movement.py'))
_mod_mov = _ilu.module_from_spec(_spec_mov) if _spec_mov and _spec_mov.loader else None
if _spec_mov and _spec_mov.loader and _mod_mov:
    _spec_mov.loader.exec_module(_mod_mov)  # type: ignore[attr-defined]
move_stock_woo_to_woo = getattr(_mod_mov, 'move_stock_woo_to_woo', None)

# Conexión a SQL Server (app)
APP_CONN_STR = os.getenv('SQLSERVER_APP_CONN_STR') or os.getenv('ORDERS_CONN_STR')
if not APP_CONN_STR:
    # Fallback por piezas
    driver = os.getenv('ODBC_DRIVER', 'ODBC Driver 17 for SQL Server')
    server = os.getenv('SQL_SERVER', '.\\SQLEXPRESS')
    db = os.getenv('SQL_DB', 'meli_stock')
    trusted = (os.getenv('SQL_TRUSTED', 'yes').lower() in ('1','true','yes'))
    user = os.getenv('SQL_USER')
    pwd = os.getenv('SQL_PASSWORD')
    if trusted:
        APP_CONN_STR = f"DRIVER={{{{}}}};SERVER={server};DATABASE={db};Trusted_Connection=yes;".format(driver)
    else:
        APP_CONN_STR = f"DRIVER={{{{}}}};SERVER={server};DATABASE={db};UID={user};PWD={pwd};".format(driver)

logger = logging.getLogger('backfill_mov')
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')


def _row_to_dict(cur, row) -> dict:
    cols = [c[0] for c in cur.description]
    return {cols[i]: row[i] for i in range(len(cols))}


def backfill(limit: int, desde: Optional[str], solo_ready_to_print: bool) -> int:
    if not callable(get_stock_per_deposit) or not callable(choose_winner) or not callable(move_stock_woo_to_woo):
        logger.error('Faltan módulos: get_stock_per_deposit / choose_winner / move_stock_woo_to_woo')
        return 0
    count = 0
    with pyodbc.connect(APP_CONN_STR) as conn:
        cur = conn.cursor()
        # Filtro de órdenes sin movimiento
        where = [
            "(numero_movimiento IS NULL OR LTRIM(RTRIM(COALESCE(numero_movimiento,'')))='')",
            "(ISNULL(movimiento_realizado,0)=0)",
            "(ISNULL(mov_depo_hecho,0)=0)",
        ]
        args = []
        if solo_ready_to_print:
            where.append("(ISNULL(ready_to_print,0)=1 OR shipping_subestado='ready_to_print')")
        if desde:
            try:
                dt = datetime.fromisoformat(desde)
                where.append("[date_created] >= ?")
                args.append(dt)
            except Exception:
                pass
        sql = (
            "SELECT TOP ({limit}) id, order_id, sku, seller_sku, nombre, ARTICULO, qty, deposito_asignado "
            "FROM dbo.orders_meli WHERE {where} ORDER BY id ASC"
        ).format(limit=limit, where=" AND ".join(where))
        cur.execute(sql, *args)
        rows = cur.fetchall() or []
        logger.info(f"Órdenes candidatas: {len(rows)}")
        for r in rows:
            obj = _row_to_dict(cur, r)
            order_id = int(obj['order_id'])
            sku = (obj.get('sku') or obj.get('seller_sku') or '').strip()
            qty = int(obj.get('qty') or 1)
            depot_assigned = (obj.get('deposito_asignado') or '').strip() or None
            if not sku:
                logger.warning(f"Orden {order_id}: sin SKU, se omite")
                continue
            # Stock & ganador
            try:
                stock = get_stock_per_deposit(sku, timeout=60)
            except Exception as e:
                logger.warning(f"Orden {order_id}: error consultando stock: {e}")
                stock = {}
            depot = None
            try:
                cw = choose_winner(stock, qty)
                if cw:
                    depot = cw[0]
            except Exception:
                depot = None
            if not depot:
                depot = depot_assigned  # último fallback
            # Ejecutar movimiento
            observacion = f"BACKFILL_MOV | order_id={order_id}"
            try:
                mv = move_stock_woo_to_woo(sku=sku, qty=qty, observacion=observacion, tipo=2, barcode=None, articulo_detalle=str(obj.get('nombre') or obj.get('ARTICULO') or ''))
            except Exception as e:
                mv = {"ok": False, "error": str(e)}
            numero = str(mv.get('numero')) if mv and (mv.get('numero') is not None) else ''
            ok = bool(mv.get('ok'))
            obs_fin = observacion + (f" | numero_movimiento={numero}" if numero else '') + (f" | error={mv.get('error')}" if not ok else '')
            # Persistir
            sets = []
            vals = []
            sets.append("[movimiento_realizado] = ?")
            vals.append(1 if ok else 0)
            sets.append("[fecha_movimiento] = CASE WHEN ?=1 THEN SYSUTCDATETIME() ELSE [fecha_movimiento] END")
            vals.append(1 if ok else 0)
            sets.append("[numero_movimiento] = ?")
            vals.append(numero[:100])
            sets.append("[observacion_movimiento] = LEFT(?,500)")
            vals.append(obs_fin)
            sets.append("[stock_reservado] = COALESCE([stock_reservado],0) + ?")
            vals.append(int(qty))
            if depot:
                sets.append("[deposito_asignado] = COALESCE([deposito_asignado], ?)")
                vals.append(depot)
            upd = f"UPDATE dbo.orders_meli SET {', '.join(sets)} WHERE [order_id] = ?"
            vals.append(order_id)
            cur2 = conn.cursor()
            cur2.execute(upd, *vals)
            conn.commit()
            count += 1
            logger.info(f"Orden {order_id}: movimiento {'OK' if ok else 'ERROR'} num={numero or '-'} depot={depot or '-'}")
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=200)
    ap.add_argument('--desde', type=str, default=None, help='ISO date/time ej 2025-09-06 o 2025-09-06T00:00:00')
    ap.add_argument('--solo-ready-to-print', type=int, default=0)
    args = ap.parse_args()
    n = backfill(limit=args.limit, desde=args.desde, solo_ready_to_print=bool(args.solo_ready_to_print))
    print(f"Movimientos procesados: {n}")

if __name__ == '__main__':
    main()
