"""
Visor de movimientos (consola) para Dragonfish:
- BaseDeDatos (header) = MELI
- OrigenDestino (body en resultados) = MUNDOCAB
- Filtro por rango de fechas (local) y muestra en consola.

Uso:
  py scripts/movements_viewer_meli_to_mundocab.py  "2025-09-25" "2025-09-25"
Si no pasás fechas, toma la fecha de hoy.

Requisitos: variables DRAGONFISH_TOKEN y DRAGONFISH_IDCLIENTE=MATIAPP en .env o entorno.
"""
from __future__ import annotations

import os
import sys
import json
import re
import requests
from datetime import datetime, date, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv('DRAGONFISH_BASE_URL', 'http://190.211.201.217:8888/api.Dragonfish')
TOKEN = os.getenv('DRAGONFISH_TOKEN', '')
IDCLIENTE = os.getenv('DRAGONFISH_IDCLIENTE', 'MATIAPP')

if not TOKEN:
    print("[ERROR] DRAGONFISH_TOKEN no está configurado (.env o entorno)")
    sys.exit(1)

HEADERS = {
    "accept": "application/json",
    "Authorization": TOKEN,
    "IdCliente": IDCLIENTE,
    "BaseDeDatos": "MELI",
}


def parse_dragon_date(raw: str) -> datetime | None:
    if not raw:
        return None
    m = re.search(r"/Date\((\d+)", raw)
    if not m:
        return None
    ts = int(m.group(1)) / 1000.0
    return datetime.fromtimestamp(ts)


def in_range(dt: datetime | None, dfrom: date, dto: date) -> bool:
    if not dt:
        return False
    return dfrom <= dt.date() <= dto


def main():
    # Fechas
    if len(sys.argv) >= 3:
        dfrom = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        dto = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    else:
        today = date.today()
        dfrom = dto = today

    params = {
        # Si la API soporta más filtros, se pueden agregar aquí (p.ej. Numero, Observaciones, etc.)
        "limit": 300,
    }

    url = f"{BASE_URL}/Movimientodestock/"
    print("\n=== CONSULTA DRAGONFISH (MELI -> MUNDOCAB) ===")
    print("URL:", url)
    print("Headers:", json.dumps(HEADERS, ensure_ascii=False))
    print(f"Rango fechas: {dfrom} a {dto}")

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}: {resp.text[:400]}")
            sys.exit(2)
        data = resp.json()
        resultados = data.get("Resultados", [])

        # Filtrado local por OrigenDestino y fecha
        filtrados = []
        for mov in resultados:
            if (mov.get("OrigenDestino") or "").upper() != "MUNDOCAB":
                continue
            f = parse_dragon_date(mov.get("Fecha"))
            if not in_range(f, dfrom, dto):
                continue
            filtrados.append((f, mov))

        # Ordenar por fecha
        filtrados.sort(key=lambda x: x[0] or datetime.min)

        print(f"Encontrados: {len(filtrados)} movimientos")
        for f, mov in filtrados[:100]:
            numero = mov.get("Numero")
            tipo = mov.get("Tipo")
            obs = (mov.get("Observaciones") or "")[:120]
            cant_items = len(mov.get("MovimientoDetalle", []))
            print(f"- {f.strftime('%Y-%m-%d %H:%M')} | Nro:{numero} | Tipo:{tipo} | It:{cant_items} | Obs:{obs}")

    except Exception as e:
        print("[ERROR]", e)
        sys.exit(3)


if __name__ == "__main__":
    main()
