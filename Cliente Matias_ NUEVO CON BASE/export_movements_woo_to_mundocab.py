"""
Exporta a Excel los movimientos de Dragonfish:
- Header BaseDeDatos = WOO
- OrigenDestino (en resultados) = MUNDOCAB
- Filtro por rango de fechas

Uso ejemplos:
  py export_movements_woo_to_mundocab.py --from 2025-09-20 --to 2025-09-30
  py export_movements_woo_to_mundocab.py  # por defecto usa hoy

Requisitos: .env con DRAGONFISH_TOKEN y DRAGONFISH_IDCLIENTE=MATIAPP
Salida por defecto: Mov_WOO_to_MUNDOCAB_<from>_<to>.xlsx en el mismo directorio.
"""
from __future__ import annotations

import os
import sys
import re
import argparse
from datetime import datetime, date
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry  # type: ignore
except Exception:
    Retry = None  # fallback si no está disponible
try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None  # Fallback a CSV si no hay pandas

from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv('DRAGONFISH_BASE_URL', 'http://190.211.201.217:8888/api.Dragonfish')
TOKEN = os.getenv('DRAGONFISH_TOKEN', '')
IDCLIENTE = os.getenv('DRAGONFISH_IDCLIENTE', 'MATIAPP')

if not TOKEN:
    print("[ERROR] DRAGONFISH_TOKEN no está configurado (.env o entorno)")
    sys.exit(1)

def build_headers(base_db: str) -> Dict[str, str]:
    return {
        "accept": "application/json",
        "Authorization": TOKEN,
        "IdCliente": IDCLIENTE,
        "BaseDeDatos": base_db,
    }


def parse_dragon_date(raw: str | None) -> datetime | None:
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


def build_session(timeout_s: float | None, base_db: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(build_headers(base_db))
    # Retries exponenciales para errores transitorios; total=None = infinito
    if Retry is not None:
        retry = Retry(
            total=None,  # reintentos infinitos
            connect=None,
            read=None,
            backoff_factor=2,  # 2,4,8,...
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount('http://', adapter)
        s.mount('https://', adapter)
    # Guardar timeout deseado en sesión (custom attr)
    s.request_timeout = timeout_s  # type: ignore[attr-defined]
    return s


def fetch_movements_for_day(session: requests.Session, day: date) -> List[Dict[str, Any]]:
    """Trae movimientos para un día específico usando parámetro Fecha.
    Nota: si el backend devuelve más de 'limit', se podría agregar paginación.
    """
    url = f"{BASE_URL}/Movimientodestock/"
    params = {
        "Fecha": day.strftime("%Y-%m-%d"),
        "limit": 1000,
    }
    timeout = getattr(session, 'request_timeout', None)
    resp = session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    data = resp.json() or {}
    return data.get("Resultados", []) or []


def build_rows(movs: List[Dict[str, Any]], dfrom: date, dto: date, dest_filter: str) -> List[Dict[str, Any]]:
    """Construye filas por detalle (una fila por SKU)."""
    out: List[Dict[str, Any]] = []
    for mv in movs:
        # Filtrar por OrigenDestino
        if (mv.get("OrigenDestino") or "").upper() != (dest_filter or "").upper():
            continue

        # Fecha y filtro por rango
        f = parse_dragon_date(mv.get("Fecha"))
        if not in_range(f, dfrom, dto):
            continue

        fecha = f.strftime("%Y-%m-%d %H:%M") if f else ""
        numero = mv.get("Numero") or mv.get("NroMovimiento") or mv.get("numero")
        observacion = (
            mv.get("Observaciones")
            or mv.get("Observacion")
            or (mv.get("InformacionAdicional") or {}).get("Observacion")
            or ""
        )

        detalles = mv.get("MovimientoDetalle") or []
        if not detalles:
            # Si no hay detalle, dejar fila en blanco de SKU
            out.append({
                "Fecha": fecha,
                "Numero": numero,
                "SKU": "",
                "ArticuloCodigo": "",
                "ColorCodigo": "",
                "TalleCodigo": "",
                "SKUCompuesto": "",
                "Observacion": str(observacion)[:500],
            })
            continue

        for det in detalles:
            # Extraer SKU/código desde distintas posibles claves
            sku = (
                det.get("Codigo")
                or det.get("SKU")
                or (det.get("ArticuloDetalle") if isinstance(det.get("ArticuloDetalle"), str) else None)
                or det.get("Articulo")
                or ""
            )
            # Códigos separados desde el detalle
            art_code = str(det.get("Articulo") or "")
            color_code = str(det.get("Color") or "")
            talle_raw = str(det.get("Talle") or "")
            talle_code = talle_raw[1:] if talle_raw.upper().startswith('T') else talle_raw
            # SKU compuesto si hay los tres
            sku_comp = f"{art_code}-{color_code}-{talle_code}" if art_code and color_code and talle_code else ""

            # Fallback desde Observacion (solo si falta algún código)
            if (not art_code or not color_code or not talle_code) and observacion:
                import re as _re
                m = _re.search(r"Art:([A-Z0-9]+)", str(observacion).upper())
                if m:
                    obs_token = m.group(1)
                    # Heurística: si termina con 2 dígitos o ST/CXS/CXL etc., separar
                    m2 = _re.match(r"([A-Z0-9]+?)([A-Z]{2,3})?(\d{2}|ST|XS|S|M|L|XL|XXL|XXXL|CXS|CS|CM|CL|CXL)?$", obs_token)
                    if m2:
                        art_guess = m2.group(1) or art_code
                        color_guess = m2.group(2) or color_code
                        talle_guess = (m2.group(3) or talle_code or "").lstrip('T')
                        art_code = art_code or art_guess
                        color_code = color_code or (color_guess or "")
                        talle_code = talle_code or (talle_guess or "")
                        if not sku_comp and art_code and color_code and talle_code:
                            sku_comp = f"{art_code}-{color_code}-{talle_code}"

            out.append({
                "Fecha": fecha,
                "Numero": numero,
                "SKU": str(sku),
                "ArticuloCodigo": art_code,
                "ColorCodigo": color_code,
                "TalleCodigo": talle_code,
                "SKUCompuesto": sku_comp,
                "Observacion": str(observacion)[:500],
            })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="from_date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--out", dest="out_file", type=str, default=None, help="Ruta de salida .xlsx o .csv")
    parser.add_argument("--timeout", dest="timeout", type=float, default=None, help="Timeout en segundos (por defecto: infinito)")
    parser.add_argument("--base", dest="base_db", type=str, default=os.getenv('DF_BASE_DB', 'WOO'), help="Header BaseDeDatos (default: WOO)")
    parser.add_argument("--dest", dest="dest", type=str, default=os.getenv('DF_DEST', 'MUNDOCAB'), help="Filtro OrigenDestino (default: MUNDOCAB)")
    args = parser.parse_args()

    # Rango por defecto: hoy
    today = date.today()
    dfrom = datetime.strptime(args.from_date, "%Y-%m-%d").date() if args.from_date else today
    dto = datetime.strptime(args.to_date, "%Y-%m-%d").date() if args.to_date else today

    print(f"Consultando movimientos base={args.base_db} -> dest={args.dest} entre {dfrom} y {dto}...")
    try:
        session = build_session(args.timeout, args.base_db)
        # Traer por día (mejor cobertura que un solo request)
        all_movs: List[Dict[str, Any]] = []
        cur = dfrom
        while cur <= dto:
            day_movs = fetch_movements_for_day(session, cur)
            all_movs.extend(day_movs)
            cur = date.fromordinal(cur.toordinal() + 1)
        rows = build_rows(all_movs, dfrom, dto, args.dest)
        print(f"Filtrados {len(rows)} registros")

        # Output
        if not args.out_file:
            out_name = f"Mov_{args.base_db}_to_{args.dest}_{dfrom}_{dto}"
            # Priorizar Excel si hay pandas
            args.out_file = out_name + (".xlsx" if pd is not None else ".csv")

        if pd is not None and args.out_file.lower().endswith(".xlsx"):
            df = pd.DataFrame(rows, columns=[
                "Fecha", "Numero", "SKU",
                "ArticuloCodigo", "ColorCodigo", "TalleCodigo", "SKUCompuesto",
                "Observacion"
            ])
            df.to_excel(args.out_file, index=False)
            print(f"✔ Archivo Excel generado: {args.out_file}")
        else:
            # CSV fallback
            import csv
            with open(args.out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "Fecha", "Numero", "SKU",
                    "ArticuloCodigo", "ColorCodigo", "TalleCodigo", "SKUCompuesto",
                    "Observacion"
                ])
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            print(f"✔ Archivo CSV generado: {args.out_file}")

    except requests.HTTPError as he:
        print("[HTTP ERROR]", he)
        print(getattr(he, 'response', None) and getattr(he.response, 'text', '')[:400])
        sys.exit(2)
    except Exception as e:
        print("[ERROR]", e)
        sys.exit(3)


if __name__ == "__main__":
    main()
