"""
Ejecuta UN movimiento WOO→WOO para órdenes ya asignadas, reutilizando la misma
conexión a meli_stock que usa este pipeline (database_utils.CONNECTION_STRING).

Uso:
  python movement_once.py --order-id 2000012620778324
  python movement_once.py                 # toma la primera asignada sin movimiento

Reglas:
  - Movimiento único, sin reintentos automáticos, espera la respuesta (timeout=None).
  - Actualiza movimiento_realizado, numero_movimiento y observacion_movimiento.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Dict, Any

import pyodbc

# Reusar la conexión probada por el pipeline 6
from database_utils import get_connection

# Importar el módulo de movimiento real desde modules/09_dragon_movement.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
MODULES_DIR = os.path.join(PROJECT_ROOT, 'modules')
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import importlib.util

def _load_dragon_movement():
    path = os.path.join(MODULES_DIR, '09_dragon_movement.py')
    spec = importlib.util.spec_from_file_location('modules.09_dragon_movement', path)
    if not spec or not spec.loader:
        raise ImportError('No se pudo cargar 09_dragon_movement.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod

dragon_movement = _load_dragon_movement()


def pick_order(conn: pyodbc.Connection, order_id: Optional[str]) -> Optional[Dict[str, Any]]:
    sql = (
        "SELECT TOP 1 order_id, pack_id, sku, barcode, qty "
        "FROM orders_meli "
        "WHERE asignado_flag = 1 "
        "AND (movimiento_realizado = 0 OR movimiento_realizado IS NULL) "
        "AND (numero_movimiento IS NULL) "
    )
    params: tuple = ()
    if order_id:
        sql += " AND order_id = ?"
        params = (order_id,)
    sql += " ORDER BY fecha_actualizacion DESC"

    cur = conn.cursor()
    cur.execute(sql, params) if params else cur.execute(sql)
    row = cur.fetchone()
    if not row:
        return None
    return {
        'order_id': row[0],
        'pack_id': row[1],
        'sku': row[2],
        'barcode': row[3],
        'qty': int(row[4] or 1),
    }


def update_success(conn: pyodbc.Connection, order_id: str, numero: Optional[int], obs: str) -> None:
    sql = (
        "UPDATE orders_meli SET movimiento_realizado = 1, numero_movimiento = ?, "
        "observacion_movimiento = ?, fecha_actualizacion = SYSUTCDATETIME() WHERE order_id = ?"
    )
    cur = conn.cursor()
    cur.execute(sql, (numero, obs, order_id))
    conn.commit()


def update_failure(conn: pyodbc.Connection, order_id: str, obs: str) -> None:
    sql = (
        "UPDATE orders_meli SET observacion_movimiento = ?, fecha_actualizacion = SYSUTCDATETIME() "
        "WHERE order_id = ?"
    )
    cur = conn.cursor()
    cur.execute(sql, (obs, order_id))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--order-id', default=None)
    args = parser.parse_args()

    print('🚀 Movimiento WOO→WOO único (sin reintentos)')
    try:
        with get_connection() as conn:
            sel = pick_order(conn, args.order_id)
            if not sel:
                print('ℹ️ No hay orden asignada pendiente de movimiento (o no coincide el order-id).')
                return 0

            order_id = sel['order_id']
            pack_id = sel['pack_id']
            sku = sel['sku']
            barcode = sel['barcode']
            qty = sel['qty']
            obs = f"MATIAPP MELI A MELI | order_id={order_id} | pack_id={pack_id or ''}"

            print(f"📦 Orden: {order_id} | SKU: {sku} | Barcode: {barcode} | Qty: {qty}")
            print('🔁 Enviando POST a Dragonfish (espera única)...')

            result = dragon_movement.move_stock_woo_to_woo(
                sku=sku,
                qty=qty,
                observacion=obs,
                barcode=barcode,
            )

            ok = bool(result.get('ok'))
            numero = result.get('numero')
            status = result.get('status')
            data = result.get('data')
            error = result.get('error')

            if ok:
                obs_ok = f"{obs} | numero_movimiento={numero} | status={status}"
                update_success(conn, order_id, numero, obs_ok)
                print(f"✅ Movimiento OK | Numero={numero} | Status={status}")
            else:
                obs_err = f"{obs} | ERROR status={status} | detalle={str(data)[:300] if data else error}"
                update_failure(conn, order_id, obs_err)
                print(f"❌ Movimiento FALLÓ | Status={status} | Error={error}")

            return 0 if ok else 1

    except pyodbc.Error as e:
        print(f"❌ Error de base de datos: {e}")
        return 2
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
