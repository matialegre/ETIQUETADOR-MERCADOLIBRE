import os
import sys
import argparse
from typing import List, Dict, Any

# Rutas de módulos del pipeline 5
sys.path.append(r"c:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline\PIPELINE_5_CONSOLIDADO")
from meli_client_01 import MeliClient
from order_processor import extract_order_data
from database_utils import insert_or_update_order


def process_orders_from_token(token_path: str, limit: int) -> None:
    print(f"\n=== Procesando últimas {limit} ventas con token: {token_path} ===")
    client = MeliClient(config_path=token_path)
    orders: List[Dict[str, Any]] = client.get_recent_orders(limit=limit)
    if not orders:
        print("No se obtuvieron órdenes.")
        return

    for idx, raw in enumerate(orders, 1):
        try:
            data = extract_order_data(raw, meli_client=client)
            if not data:
                print(f"[{idx}/{len(orders)}] Skip: no data procesada")
                continue
            action = insert_or_update_order(data)
            print(f"[{idx}/{len(orders)}] {action.upper()} | order_id={data['order_id']} | MELI={data.get('meli_user_id')} | total={data.get('total_amount')}")
        except Exception as e:
            print(f"[{idx}/{len(orders)}] Error procesando orden: {e}")


def main():
    parser = argparse.ArgumentParser(description="Procesa las últimas N ventas de cada cuenta MELI y las guarda en DB (columna MELI incluida)")
    parser.add_argument("--token1", default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token.json", help="Ruta al token de la cuenta 1")
    parser.add_argument("--token2", default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token_02.json", help="Ruta al token de la cuenta 2")
    parser.add_argument("--limit", type=int, default=2, help="Cantidad de ventas recientes por cuenta")
    args = parser.parse_args()

    # Cuenta 1
    process_orders_from_token(args.token1, args.limit)

    # Cuenta 2 si existe
    if os.path.exists(args.token2):
        process_orders_from_token(args.token2, args.limit)
    else:
        print(f"\n(Info) Segundo token no encontrado en {args.token2}.")


if __name__ == "__main__":
    main()
