"""
CLI para enviar movimientos de stock a Dragonfish (Movimientodestock)
====================================================================

Permite hacer movimientos NEGATIVO (Tipo=2) o REVERSA/entrada (Tipo=1)
indicando host, IdCliente, Authorization (token), BaseDeDatos, SKU, etc.

Ejemplos:
  python scripts/dragon_move_cli.py \
    --url http://ranchoaspen:8888/api.Dragonfish/Movimientodestock/ \
    --idcliente MATIAPP \
    --token "XXX" \
    --sku NMIDKTHZLE-NN0-T41 --detalle "Bota Trekking Lander Hombre Impermeable Montagne" \
    --color NN0 --talle T41 --qty 1 --tipo 2 --basedatos MELI \
    --obs "MANUAL_NEG | order_id=2000012961353562"

  # Si devuelve 401/400 con token crudo, reintenta automáticamente con Bearer

Salida: imprime status y el JSON/texto de respuesta. Considera 200/201/409 como éxito
(y extrae Numero de movimiento cuando es posible).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, Optional

import requests


def wcf_now_ms() -> int:
    return int(time.time() * 1000)


def wcf_date_literal(ms: Optional[int] = None, tz_offset: str = "-0300") -> str:
    ms = ms if ms is not None else wcf_now_ms()
    return f"/Date({ms}{tz_offset})/"


def build_body(
    *, sku: str, detalle: str, color: str, talle: str, qty: int,
    tipo: int, obs: str, base: str,
) -> Dict[str, Any]:
    fw = wcf_date_literal()
    return {
        "Codigo": sku,
        "OrigenDestino": "MELI",
        "Tipo": int(tipo),
        "Motivo": "API",
        "vendedor": "API",
        "Remito": "-",
        "CompAfec": [],
        "Numero": 0,
        "Fecha": fw,
        "Observacion": obs,
        "MovimientoDetalle": [
            {
                "Codigo": sku,
                "Articulo": sku,
                "ArticuloDetalle": detalle or "",
                "Color": color or "",
                "ColorDetalle": "",
                "Talle": talle or "",
                "Cantidad": int(qty),
                "NroItem": 1,
            }
        ],
        "InformacionAdicional": {
            "FechaAltaFW": fw,
            "HoraAltaFW": time.strftime("%H:%M:%S"),
            "EstadoTransferencia": "PENDIENTE",
            "BaseDeDatosAltaFW": base,
            "BaseDeDatosModificacionFW": base,
            "SerieAltaFW": "901224",
            "SerieModificacionFW": "901224",
            "UsuarioAltaFW": "API",
            "UsuarioModificacionFW": "API",
        },
    }


def do_post(url: str, headers: Dict[str, str], body: Dict[str, Any]) -> tuple[int, Any]:
    r = requests.post(url, headers=headers, data=json.dumps(body), timeout=60)
    status = r.status_code
    try:
        data = r.json() if r.content else None
    except Exception:
        data = r.text
    return status, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True, help='Endpoint Movimientodestock, ej http://ranchoaspen:8888/api.Dragonfish/Movimientodestock/')
    ap.add_argument('--idcliente', required=True)
    ap.add_argument('--token', required=True, help='Authorization token (crudo); si falla, se probará con Bearer')
    ap.add_argument('--basedatos', default='MELI')
    ap.add_argument('--sku', required=True)
    ap.add_argument('--detalle', default='')
    ap.add_argument('--color', default='')
    ap.add_argument('--talle', default='')
    ap.add_argument('--qty', type=int, default=1)
    ap.add_argument('--tipo', type=int, default=2, choices=[1,2], help='2=resta (negativo), 1=entrada (reversa)')
    ap.add_argument('--obs', default='MANUAL_NEG')
    args = ap.parse_args()

    body = build_body(
        sku=args.sku,
        detalle=args.detalle,
        color=args.color,
        talle=args.talle,
        qty=args.qty,
        tipo=args.tipo,
        obs=args.obs,
        base=args.basedatos,
    )

    headers = {
        'IdCliente': args.idcliente,
        'Authorization': args.token,
        'BaseDeDatos': args.basedatos,
        'Content-Type': 'application/json',
    }

    status, data = do_post(args.url, headers, body)
    if status in (200, 201, 409):
        print('OK raw:', status, data if isinstance(data, (str, int, float)) else json.dumps(data, ensure_ascii=False))
        return 0
    # Retry con Bearer
    headers['Authorization'] = args.token if args.token.lower().startswith('bearer ') else f'Bearer {args.token}'
    status2, data2 = do_post(args.url, headers, body)
    if status2 in (200, 201, 409):
        print('OK bearer:', status2, data2 if isinstance(data2, (str, int, float)) else json.dumps(data2, ensure_ascii=False))
        return 0
    # Error
    print('ERROR', status, data if isinstance(data, (str, int, float)) else json.dumps(data, ensure_ascii=False))
    print('ERROR bearer', status2, data2 if isinstance(data2, (str, int, float)) else json.dumps(data2, ensure_ascii=False))
    return 2


if __name__ == '__main__':
    sys.exit(main())
