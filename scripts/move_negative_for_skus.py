"""
Mover stock en negativo para una lista de SKUs específicos
=========================================================

- Busca órdenes en dbo.orders_meli para los SKUs indicados con movimiento_realizado=0
  y numero_movimiento vacío, y ejecuta un movimiento negativo por cada orden.
- Actualiza: movimiento_realizado, fecha_movimiento, numero_movimiento, observacion_movimiento,
  stock_reservado += qty y completa deposito_asignado si estaba vacío (si se pudo elegir ganador).

Uso ejemplos:
  python scripts/move_negative_for_skus.py --skus "NDPMB6E773-AGC-48,NMIDKTHZLE-NN0-T41"
  python scripts/move_negative_for_skus.py --file C:/ruta/lista_skus.txt
  python scripts/move_negative_for_skus.py --skus "A,B" --limit 200 --dry-run 1

Notas:
- Lee config/.env igual que el resto del proyecto.
- No modifica impresas/ready_to_print; sólo registra el movimiento.
- Si no puede elegir depósito, intenta mover igual (el módulo de movimiento decide por MOVIMIENTO_TARGET).
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Any
from datetime import datetime
import logging

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

# Hacer importables los módulos del proyecto
if PROJ_ROOT not in sys.path:
    sys.path.append(PROJ_ROOT)

# Imports dinámicos de módulos
import importlib
try:
    dapi = importlib.import_module('modules.07_dragon_api')
    assigner = importlib.import_module('modules.07_assigner')
    mover = importlib.import_module('modules.09_dragon_movement')
except Exception as e:
    print('Error importando módulos del proyecto:', e)
    sys.exit(2)

get_stock_per_deposit = getattr(dapi, 'get_stock_per_deposit', None)
choose_winner = getattr(assigner, 'choose_winner', None)
move_stock_woo_to_woo = getattr(mover, 'move_stock_woo_to_woo', None)

if not (callable(get_stock_per_deposit) and callable(choose_winner) and callable(move_stock_woo_to_woo)):
    print('Faltan funciones requeridas (get_stock_per_deposit/choose_winner/move_stock_woo_to_woo)')
    sys.exit(3)

# Conexión a SQL Server (orders app)
APP_CONN_STR = os.getenv('SQLSERVER_APP_CONN_STR') or os.getenv('ORDERS_CONN_STR')
if not APP_CONN_STR:
    driver = os.getenv('ODBC_DRIVER', 'ODBC Driver 17 for SQL Server')
    server = os.getenv('SQL_SERVER', '.\\SQLEXPRESS')
    db = os.getenv('SQL_DB', 'meli_stock')
    trusted = (os.getenv('SQL_TRUSTED', 'yes').lower() in ('1','true','yes'))
    user = os.getenv('SQL_USER')
    pwd = os.getenv('SQL_PASSWORD')
    APP_CONN_STR = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={db};Trusted_Connection=yes;" if trusted
        else f"DRIVER={{{driver}}};SERVER={server};DATABASE={db};UID={user};PWD={pwd};"
    )

logger = logging.getLogger('move_skus')
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')


def _parse_skus_param(s: str) -> List[str]:
    return [x.strip() for x in (s or '').split(',') if x and x.strip()]


def _load_skus_from_file(p: str) -> List[str]:
    items: List[str] = []
    with open(p, 'r', encoding='utf-8') as f:
        for line in f:
            t = line.strip()
            if not t or t.startswith('#'):
                continue
            items.append(t)
    return items


def _row_to_dict(cur, row) -> dict:
    cols = [c[0] for c in cur.description]
    return {cols[i]: row[i] for i in range(len(cols))}


def process_skus(skus: List[str], limit: int, dry_run: bool) -> int:
    count = 0
    if not skus:
        logger.warning('Lista de SKUs vacía')
        return 0
    with pyodbc.connect(APP_CONN_STR) as conn:
        for sku in skus:
            cur = conn.cursor()
            # Seleccionar órdenes pendientes de movimiento para este SKU
            sql = (
                "SELECT TOP ({limit}) id, order_id, sku, seller_sku, nombre, ARTICULO, qty, deposito_asignado "
                "FROM dbo.orders_meli "
                "WHERE (numero_movimiento IS NULL OR LTRIM(RTRIM(COALESCE(numero_movimiento,'')))='') "
                "  AND ISNULL(movimiento_realizado,0)=0 "
                "  AND (sku = ? OR seller_sku = ?) "
                "ORDER BY id ASC"
            ).format(limit=limit)
            cur.execute(sql, sku, sku)
            rows = cur.fetchall() or []
            if not rows:
                logger.info(f"SKU {sku}: sin órdenes pendientes")
                continue
            logger.info(f"SKU {sku}: {len(rows)} órdenes pendientes")
            for r in rows:
                obj = _row_to_dict(cur, r)
                order_id = int(obj['order_id'])
                qty = int(obj.get('qty') or 1)
                skustr = (obj.get('sku') or obj.get('seller_sku') or '').strip()
                depot = (obj.get('deposito_asignado') or '').strip() or None
                # Elegir depósito si no hay
                if not depot:
                    try:
                        stock = get_stock_per_deposit(skustr, timeout=60)
                        cw = choose_winner(stock, qty)
                        if cw:
                            depot = cw[0]
                    except Exception:
                        depot = None
                observacion = f"MANUAL_NEG | order_id={order_id}"
                if dry_run:
                    logger.info(f"DRY-RUN orden {order_id}: mover SKU={skustr} qty={qty} depot={depot or '-'}")
                    count += 1
                    continue
                try:
                    mv = move_stock_woo_to_woo(sku=skustr, qty=qty, observacion=observacion, tipo=2, barcode=None, articulo_detalle=str(obj.get('nombre') or obj.get('ARTICULO') or ''))
                except Exception as e:
                    mv = {"ok": False, "error": str(e)}
                numero = str(mv.get('numero')) if mv and (mv.get('numero') is not None) else ''
                ok = bool(mv.get('ok'))
                obs_fin = observacion + (f" | numero_movimiento={numero}" if numero else '') + (f" | error={mv.get('error')}" if not ok else '')
                # Persistir
                sets = []
                vals = []
                sets.append("[movimiento_realizado] = ?"); vals.append(1 if ok else 0)
                sets.append("[fecha_movimiento] = CASE WHEN ?=1 THEN SYSUTCDATETIME() ELSE [fecha_movimiento] END"); vals.append(1 if ok else 0)
                sets.append("[numero_movimiento] = ?"); vals.append(numero[:100])
                sets.append("[observacion_movimiento] = LEFT(?,500)"); vals.append(obs_fin)
                sets.append("[stock_reservado] = COALESCE([stock_reservado],0) + ?"); vals.append(int(qty))
                if depot:
                    sets.append("[deposito_asignado] = COALESCE([deposito_asignado], ?)"); vals.append(depot)
                upd = f"UPDATE dbo.orders_meli SET {', '.join(sets)} WHERE [order_id] = ?"
                vals.append(order_id)
                cur2 = conn.cursor(); cur2.execute(upd, *vals); conn.commit()
                count += 1
                logger.info(f"Orden {order_id}: movimiento {'OK' if ok else 'ERROR'} num={numero or '-'} depot={depot or '-'}")
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skus', type=str, default='')
    ap.add_argument('--file', type=str, default='')
    ap.add_argument('--limit', type=int, default=200)
    ap.add_argument('--dry-run', type=int, default=0)
    args = ap.parse_args()

    skus: List[str] = []
    if args.skus:
        skus.extend(_parse_skus_param(args.skus))
    if args.file:
        skus.extend(_load_skus_from_file(args.file))
    # Normalizar únicos
    skus = sorted(list({s for s in skus if s}))
    if not skus:
        print('Debe informar --skus CSV o --file')
        sys.exit(1)
    n = process_skus(skus, limit=args.limit, dry_run=bool(args.dry_run))
    print(f"Órdenes procesadas: {n}")

if __name__ == '__main__':
    main()
