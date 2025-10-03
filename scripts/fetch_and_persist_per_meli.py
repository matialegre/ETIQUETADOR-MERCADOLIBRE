import os
import sys
import argparse
from typing import Optional, Dict, Any

# Ensure module path to pipeline 5 libs
sys.path.append(r"c:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline\PIPELINE_5_CONSOLIDADO")
from meli_client_01 import MeliClient
from order_processor import extract_order_data
from database_utils import insert_or_update_order, get_latest_order_for_meli


def fetch_and_save_one(token_path: str) -> Optional[Dict[str, Any]]:
    print(f"\n=== Probando y persistiendo con token: {token_path} ===")
    client = MeliClient(config_path=token_path)
    orders = client.get_recent_orders(limit=1)
    if not orders:
        print("No hay órdenes recientes.")
        return None

    raw = orders[0]
    data = extract_order_data(raw, meli_client=client)
    if not data:
        print("No se pudo procesar la orden.")
        return None

    action = insert_or_update_order(data)
    print(f"Persistencia: {action} | order_id={data['order_id']} | MELI={data.get('meli_user_id')}")

    # Verificar última por MELI (por si hay más recientes ya en DB)
    try:
        latest = get_latest_order_for_meli(int(client.user_id)) if getattr(client, 'user_id', None) else None
        if latest:
            print(f"Última en DB para MELI={client.user_id}: order_id={latest.get('order_id')} fecha_actualizacion={latest.get('fecha_actualizacion')} date_created={latest.get('date_created')}")
        else:
            print(f"No hay registros en DB para MELI={client.user_id} aún.")
    except Exception as e:
        print(f"(Info) No se pudo verificar última orden por MELI: {e}")

    return data


def main():
    parser = argparse.ArgumentParser(description="Trae 1 orden reciente por cada cuenta de MercadoLibre y la guarda en DB (columna MELI incluida)")
    parser.add_argument("--token1", default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token.json", help="Ruta al token de la cuenta 1")
    parser.add_argument("--token2", default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token_02.json", help="Ruta al token de la cuenta 2")
    args = parser.parse_args()

    # Cuenta 1 (obligatoria)
    fetch_and_save_one(args.token1)

    # Cuenta 2 (si existe el archivo)
    if os.path.exists(args.token2):
        fetch_and_save_one(args.token2)
    else:
        print(f"\n(Info) Segundo token no encontrado en {args.token2}. Guárdalo para probar la otra cuenta.")


if __name__ == "__main__":
    main()
