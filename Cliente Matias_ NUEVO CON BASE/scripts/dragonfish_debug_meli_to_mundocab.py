"""
Script de DEBUG para enviar un movimiento Dragonfish con:
- Header BaseDeDatos = MELI
- Body OrigenDestino = MUNDOCAB

Usa:
- DRAGONFISH_BASE_URL (default: http://190.211.201.217:8888/api.Dragonfish)
- DRAGONFISH_TOKEN (desde .env o entorno)
- DRAGONFISH_IDCLIENTE (default: MATIAPP)

Imprime URL, headers, body y respuesta.
ADVERTENCIA: Esto realiza una llamada real.
"""
from __future__ import annotations

import os
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

load_dotenv()

BASE_URL = os.getenv('DRAGONFISH_BASE_URL', 'http://190.211.201.217:8888/api.Dragonfish')
TOKEN = os.getenv('DRAGONFISH_TOKEN')
IDCLIENTE = os.getenv('DRAGONFISH_IDCLIENTE', 'MATIAPP')

if not TOKEN:
    print("[WARN] DRAGONFISH_TOKEN no configurado. Ponelo en .env o variables de entorno.")


def _fecha_dragonfish() -> str:
    tz = timezone(timedelta(hours=-3))
    ms = int(datetime.now(tz).timestamp() * 1000)
    return f"/Date({ms}-0300)/"


def main():
    url = f"{BASE_URL}/Movimientodestock/"

    # Datos de ejemplo (ajustables)
    pedido_id = "DEBUG-ML-TO-MUNDOCAB"
    sku = "PRUEBAAPI"
    cantidad = 1

    headers = {
        "accept": "application/json",
        "Authorization": TOKEN or "",
        "IdCliente": IDCLIENTE,
        "Content-Type": "application/json",
        # Pedido por el usuario: BaseDeDatos = MELI
        "BaseDeDatos": "MELI",
    }

    body = {
        # Pedido por el usuario: OrigenDestino = MUNDOCAB
        "OrigenDestino": "MUNDOCAB",
        # Tipo: se puede usar 1 (Entrada) si la intención es que entre a MUNDOCAB
        # Cambiá a 2 si necesitás salida.
        "Tipo": 1,
        "Motivo": "API-DEBUG",
        "vendedor": "API",
        "Remito": "-",
        "CompAfec": [],
        "Fecha": _fecha_dragonfish(),
        "Observacion": (
            f"MELI -> MUNDOCAB | {datetime.now().strftime('%H:%M:%S')} | "
            f"Art:{sku} | Cant:{cantidad} | Pedido:{pedido_id}"
        ),
        "MovimientoDetalle": [
            {
                "Articulo": sku,
                "ArticuloDetalle": "Artículo Prueba Debug",
                "Color": "UNICO",
                "Talle": "UNICO",
                "Cantidad": cantidad,
                "NroItem": 1,
            }
        ],
        "InformacionAdicional": {
            "FechaAltaFW": _fecha_dragonfish(),
            "HoraAltaFW": datetime.now().strftime('%H:%M:%S'),
        },
    }

    print("\n==== DRAGONFISH REQUEST (ML -> MUNDOCAB) ====")
    print("URL:", url)
    print("Headers:", json.dumps(headers, ensure_ascii=False))
    print("Body:", json.dumps(body, ensure_ascii=False))
    print("===========================================\n")

    try:
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=30)
        print("Status:", resp.status_code)
        print("Response:", (resp.text or "")[:1000])
    except requests.Timeout as e:
        print("[TIMEOUT]", e)
    except Exception as e:
        print("[ERROR]", e)


if __name__ == "__main__":
    main()
