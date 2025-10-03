import argparse
import json
import os
import sys
from typing import Optional

import requests
import pyodbc

# Reusar conexión de la base del proyecto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Preferimos usar el database_utils "central" del pipeline 5
try:
    from PIPELINE_5_CONSOLIDADO.database_utils import get_connection
except Exception:
    # Fallback a una conexión directa con el mismo default del proyecto
    def get_connection() -> pyodbc.Connection:
        conn_str = (
            os.getenv(
                "CONNECTION_STRING_MELI_STOCK",
                "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;",
            )
        )
        return pyodbc.connect(conn_str)


def load_access_token(token_file: str) -> Optional[str]:
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("access_token")
    except Exception as e:
        print(f"❌ No se pudo leer el token desde {token_file}: {e}")
        return None


def fetch_shipment(shipment_id: str, access_token: str) -> Optional[dict]:
    url = f"https://api.mercadolibre.com/shipments/{shipment_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ ML devolvió {resp.status_code}: {resp.text[:300]}")
            return None
    except requests.RequestException as e:
        print(f"❌ Error de red al consultar envío {shipment_id}: {e}")
        return None


def extract_estimated_final(shipping_json: dict) -> Optional[str]:
    try:
        return shipping_json["shipping_option"]["estimated_delivery_final"]["date"]
    except Exception:
        return None


def ensure_column(conn: pyodbc.Connection) -> None:
    cur = conn.cursor()
    # Crear columna si no existe. Usamos NVARCHAR(50) para guardar ISO8601 con TZ.
    cur.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'estimated_delivery_final'
        )
        BEGIN
            ALTER TABLE orders_meli ADD estimated_delivery_final NVARCHAR(50) NULL;
        END
        """
    )
    conn.commit()


def get_shipping_id_by_order(conn: pyodbc.Connection, order_id: str) -> Optional[str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT TOP 1 shipping_id
        FROM orders_meli
        WHERE order_id = ?
        ORDER BY fecha_actualizacion DESC
        """,
        (str(order_id),),
    )
    row = cur.fetchone()
    return str(row[0]) if row and row[0] is not None else None


def update_estimated_delivery(conn: pyodbc.Connection, order_id: Optional[str], shipping_id: str, value: Optional[str]) -> None:
    cur = conn.cursor()
    # Actualizamos por order_id si lo tenemos; si no, por shipping_id
    if order_id:
        cur.execute(
            """
            UPDATE orders_meli
            SET estimated_delivery_final = ?
            WHERE order_id = ?
            """,
            (value, str(order_id)),
        )
    else:
        cur.execute(
            """
            UPDATE orders_meli
            SET estimated_delivery_final = ?
            WHERE shipping_id = ?
            """,
            (value, str(shipping_id)),
        )
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Actualiza orders_meli.estimated_delivery_final consultando ML")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--order-id", help="order_id a actualizar (se resolverá shipping_id desde la base)")
    g.add_argument("--shipping-id", help="shipping_id a consultar directamente en ML")
    parser.add_argument(
        "--token-file",
        default=os.path.join(PROJECT_ROOT, "config", "token_02.json"),
        help="Ruta al token JSON (default: config/token_02.json - token 2)",
    )

    args = parser.parse_args()

    token = load_access_token(args.token_file)
    if not token:
        return 1

    order_id: Optional[str] = args.order_id
    shipping_id: Optional[str] = args.shipping_id

    try:
        with get_connection() as conn:
            ensure_column(conn)

            # Resolver shipping_id si vino order_id
            if order_id and not shipping_id:
                shipping_id = get_shipping_id_by_order(conn, order_id)
                if not shipping_id:
                    print(f"⚠️ No se encontró shipping_id para order_id={order_id} en la base")
                    return 2

            # Consultar ML
            shipping_json = fetch_shipment(str(shipping_id), token)
            if shipping_json is None:
                return 3

            est = extract_estimated_final(shipping_json)
            if not est:
                print("⚠️ ML no devolvió shipping_option.estimated_delivery_final.date; se guardará NULL")

            # Guardar en SQL
            update_estimated_delivery(conn, order_id, str(shipping_id), est)

            target = f"order_id={order_id}" if order_id else f"shipping_id={shipping_id}"
            print(f"✅ Actualizado estimated_delivery_final={est!r} en orders_meli ({target})")
            return 0
    except pyodbc.Error as e:
        print(f"❌ Error de base de datos: {e}")
        return 4
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return 5


if __name__ == "__main__":
    sys.exit(main())
