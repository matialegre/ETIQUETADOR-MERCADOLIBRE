import argparse
import json
import os
import sys
from typing import Optional

import requests


def load_access_token(token_file: str) -> Optional[str]:
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("access_token")
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo de token: {token_file}")
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON de token: {e}")
    except Exception as e:
        print(f"❌ Error leyendo token: {e}")
    return None


def get_default_token_path() -> str:
    # scripts/ -> ../config/token_02.json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base_dir, "..", "config", "token_02.json"))


def fetch_shipment(shipment_id: str, access_token: str) -> requests.Response:
    url = f"https://api.mercadolibre.com/shipments/{shipment_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    return requests.get(url, headers=headers, timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser(description="Consulta estimated_delivery_final de un envío ML")
    parser.add_argument(
        "--shipment-id",
        default="45458303219",
        help="ID del envío a consultar (default: 45458303219)",
    )
    parser.add_argument(
        "--token-file",
        default=get_default_token_path(),
        help="Ruta al JSON con el access_token (default: ../config/token_02.json)",
    )
    args = parser.parse_args()

    token = load_access_token(args.token_file)
    if not token:
        print("❌ No se pudo obtener el access_token del token 2. Verificá el archivo.")
        return 1

    try:
        resp = fetch_shipment(args.shipment_id, token)
    except requests.RequestException as e:
        print(f"❌ Error de red al consultar el envío: {e}")
        return 2

    if resp.status_code == 200:
        data = resp.json()
        # Navegar al campo estimated_delivery_final
        try:
            estimated_date = data["shipping_option"]["estimated_delivery_final"]["date"]
            print(f"\n📦 La entrega final estimada para el envío {args.shipment_id} es: {estimated_date}")
        except (KeyError, TypeError):
            print("⚠️ No se encontró el campo 'estimated_delivery_final.date' en la respuesta.")
        # Mostrar el JSON completo, bonito
        print("\n📄 JSON completo recibido:")
        try:
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            # fallback por si hay caracteres no serializables
            print(str(data)[:2000])
        return 0
    else:
        print(f"❌ Error al obtener datos del envío. Código: {resp.status_code}")
        # Tratar de mostrar mensaje de error de ML si viene en JSON
        try:
            jerr = resp.json()
            print(json.dumps(jerr, indent=2, ensure_ascii=False))
        except Exception:
            print(resp.text[:1000])
        return 3


if __name__ == "__main__":
    sys.exit(main())
