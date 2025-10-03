#!/usr/bin/env python3
r"""
Refresca el token de MercadoLibre usando el refresh_token y actualiza el JSON.

Uso:
  - Por defecto intenta refrescar c:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline\config\token_02.json
  - También podés pasar --token <ruta_al_json>

Ejemplos:
  python scripts/refresh_meli_token.py
  python scripts/refresh_meli_token.py --token "C:/ruta/a/token.json"
"""
import argparse
import json
import os
import sys
import time
from typing import Any, Dict

import requests

DEFAULT_TOKEN_PATH = os.path.join(
    os.path.expanduser("C:/Users/Mundo Outdoor/CascadeProjects/meli_stock_pipeline/config"),
    "token_02.json",
)


def load_token(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


essential_fields = ("client_id", "client_secret", "refresh_token")


def save_token(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def refresh_token(token_path: str) -> None:
    cfg = load_token(token_path)

    missing = [k for k in essential_fields if not cfg.get(k)]
    if missing:
        sys.exit(
            f"Faltan campos en el JSON: {', '.join(missing)}. Necesarios: {', '.join(essential_fields)}"
        )

    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    refresh_tok = cfg["refresh_token"]

    url = "https://api.mercadolibre.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_tok,
    }

    try:
        resp = requests.post(url, data=data, timeout=25)
    except Exception as e:
        sys.exit(f"Error de red al refrescar token: {e}")

    if resp.status_code != 200:
        # Mostrar body legible
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        sys.exit(f"Fallo al refrescar token ({resp.status_code}). Respuesta: {body}")

    token_resp = resp.json()

    new_access = token_resp.get("access_token")
    new_refresh = token_resp.get("refresh_token") or refresh_tok
    expires_in = token_resp.get("expires_in", cfg.get("expires_in", 0))
    created_at = int(time.time())

    if not new_access:
        sys.exit(f"Respuesta sin access_token: {token_resp}")

    # Actualizar y guardar
    cfg["access_token"] = new_access
    cfg["refresh_token"] = new_refresh
    cfg["expires_in"] = expires_in
    cfg["created_at"] = created_at

    save_token(token_path, cfg)

    print("✅ Token refrescado y guardado")
    print(f"📄 Archivo: {token_path}")
    if cfg.get("user_id"):
        print(f"👤 user_id: {cfg['user_id']}")
    print(f"⏳ expires_in: {expires_in} seg")
    print(f"🕒 created_at: {created_at}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresca token de MercadoLibre y actualiza el JSON")
    parser.add_argument(
        "--token",
        dest="token_path",
        default=DEFAULT_TOKEN_PATH,
        help=f"Ruta al token.json (default: {DEFAULT_TOKEN_PATH})",
    )
    args = parser.parse_args()

    token_path = args.token_path
    if not os.path.exists(token_path):
        sys.exit(f"No existe el archivo de token: {token_path}")

    refresh_token(token_path)


if __name__ == "__main__":
    main()
