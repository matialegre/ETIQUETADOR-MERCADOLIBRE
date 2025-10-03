import os
import sys
import argparse
from typing import Optional

# Ensure module path
sys.path.append(r"c:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline\PIPELINE_5_CONSOLIDADO")
from meli_client_01 import MeliClient


def show_one_order(token_path: str) -> Optional[str]:
    print(f"\n=== Probando token: {token_path} ===")
    client = MeliClient(config_path=token_path)
    orders = client.get_recent_orders(limit=1)
    if not orders:
        print("No hay órdenes recientes.")
        return None
    o = orders[0]
    oid = o.get('id')
    tot = o.get('total_amount')
    status = o.get('status')
    sub = o.get('substatus')
    pack = o.get('pack_id')
    ship = None
    try:
        ship = (o.get('shipping') or {}).get('id') if isinstance(o.get('shipping'), dict) else None
    except Exception:
        pass
    print(f"OK → user_id={client.user_id} | order_id={oid} | total={tot} | status={status}/{sub} | pack={pack} | shipping={ship}")
    return str(oid) if oid else None


def main():
    parser = argparse.ArgumentParser(description="Trae 1 orden reciente por cada cuenta de MercadoLibre")
    parser.add_argument("--token1", default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token.json", help="Ruta al token de la cuenta 1")
    parser.add_argument("--token2", default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token_02.json", help="Ruta al token de la cuenta 2")
    args = parser.parse_args()

    # Cuenta 1 (obligatoria)
    show_one_order(args.token1)

    # Cuenta 2 (si existe el archivo)
    if os.path.exists(args.token2):
        show_one_order(args.token2)
    else:
        print(f"\n(Info) Segundo token no encontrado en {args.token2}. Guárdalo para probar la otra cuenta.")


if __name__ == "__main__":
    main()
