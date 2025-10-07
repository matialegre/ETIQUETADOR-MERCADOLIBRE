"""
Script de DEBUG para enviar un movimiento de stock a Dragonfish y ver el request completo.
- Fuerza modo CABA (CABA_VERSION=true)
- Usa DRAGONFISH_BASE_URL= http://190.211.201.217:8888/api.Dragonfish
- Usa DRAGONFISH_IDCLIENTE= MATIAPP
- Usa DRAGONFISH_TOKEN desde .env si no está en variables de entorno.

Imprime:
- URL
- Headers (incluye BaseDeDatos=WOO para CABA)
- Body (incluye OrigenDestino=MUNDOCAB)

ADVERTENCIA: Este script hace una llamada real a la API. Úsalo con un SKU de prueba.
"""
from __future__ import annotations

import os
from dotenv import load_dotenv

# Cargar .env del proyecto (si existe)
try:
    load_dotenv()
except Exception:
    pass

# Forzar configuración CABA y credenciales/URL nuevas
os.environ['CABA_VERSION'] = 'true'
os.environ.setdefault('DRAGONFISH_BASE_URL', 'http://190.211.201.217:8888/api.Dragonfish')
os.environ.setdefault('DRAGONFISH_IDCLIENTE', 'MATIAPP')

# Token: si no está en entorno, avisar
TOKEN = os.environ.get('DRAGONFISH_TOKEN')
if not TOKEN:
    print("[WARN] DRAGONFISH_TOKEN no está en variables de entorno ni .env. El request fallará por falta de autorización.")

# Import después de setear entorno, para que tome los valores
from api.dragonfish_api import send_stock_movement  # noqa: E402


def main():
    # Datos de PRUEBA: ajustá a gusto
    pedido_id = "DEBUG-ORDER-TEST"
    sku = "PRUEBAAPI"
    cantidad = 1
    datos_articulo = {
        "CODIGO_BARRA": sku,
        "ARTDES": "Artículo Prueba Debug",
        "CODIGO_COLOR": "UNICO",
        "CODIGO_TALLE": "UNICO",
    }

    print("\n=== DEBUG DRAGONFISH MOVIMIENTO (CABA) ===")
    print("CABA_VERSION=", os.environ.get('CABA_VERSION'))
    print("DRAGONFISH_BASE_URL=", os.environ.get('DRAGONFISH_BASE_URL'))
    print("DRAGONFISH_IDCLIENTE=", os.environ.get('DRAGONFISH_IDCLIENTE'))

    ok, msg = send_stock_movement(pedido_id, sku, cantidad, datos_articulo)
    print("Resultado:", ok, msg)
    print("=== FIN DEBUG ===\n")


if __name__ == "__main__":
    main()
