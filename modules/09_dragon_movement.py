"""
Módulo 09: Movimiento de stock MELI→MELI (Dragonfish)
=====================================================

Realiza el POST a Dragonfish /Movimientodestock/ para registrar un movimiento
MELI→MELI. Sin reintentos, timeout largo, esperando siempre respuesta.

Campos editables de cabecera: OrigenDestino y Tipo (2=resta, 1=suma).
"""
from __future__ import annotations

import requests
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import json

from modules.config import (
    DRAGON_MOV_URL,
    DRAGON_API_KEY,
    DRAGON_ID_CLIENTE,
    DRAGON_BASEDEDATOS,
    MOV_ORIGENDESTINO_DEFAULT,
    MOV_TIPO_DEFAULT,
    DRAGON_ALT_API_KEY,
    DRAGON_ALT_ID_CLIENTE,
)
import logging
import importlib.util
import os


def _get_article_info_from_db(barcode: str):
    """Carga dinámica de modules/02_dragon_db.py para obtener ARTDES por barcode.
    Evita importar con nombre inválido (módulo que comienza con dígitos).
    """
    try:
        base_dir = os.path.dirname(__file__)
        mod_path = os.path.join(base_dir, "02_dragon_db.py")
        spec = importlib.util.spec_from_file_location("dragon_db_helper", mod_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            func = getattr(mod, "get_article_info_by_barcode", None)
            if callable(func):
                return func(barcode)
    except Exception:
        pass
    return None


def _dragon_date() -> str:
    """Devuelve fecha formato Dragonfish /Date(ms-0300)/ en zona -03:00."""
    zona = timezone(timedelta(hours=-3))
    ms = int(datetime.now(zona).timestamp() * 1000)
    return f"/Date({ms}-0300)/"


def _dragon_time() -> str:
    zona = timezone(timedelta(hours=-3))
    return datetime.now(zona).strftime("%H:%M:%S")


def _parse_sku(sku: str) -> tuple[str, Optional[str], Optional[str]]:
    """Devuelve (articulo, color, talle) a partir de ART-COLOR-TALLE."""
    if not sku:
        return ("", None, None)
    parts = sku.split('-')
    if len(parts) >= 3:
        return (parts[0].strip(), parts[1].strip(), parts[2].strip())
    return (parts[0].strip(), None, None)


logger = logging.getLogger(__name__)


def _normalize_code(code: str) -> str:
    """Colapsa guiones redundantes y remueve sufijos vacíos.
    Ej.: "201-HF500--" -> "201-HF500".
    """
    try:
        parts = [p for p in str(code or '').strip().upper().split('-') if p != '']
        return '-'.join(parts) if parts else str(code or '').strip().upper()
    except Exception:
        return str(code or '').strip().upper()


def move_stock_woo_to_woo(
    *,
    sku: str,
    qty: int,
    observacion: str,
    origen_destino: Optional[str] = None,
    tipo: Optional[int] = None,
    base_datos_header: Optional[str] = None,
    barcode: Optional[str] = None,
    articulo_detalle: Optional[str] = None,
    color_codigo: Optional[str] = None,
    talle_codigo: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ejecuta movimiento MELI→MELI en Dragonfish.

    Args:
        sku: SKU estilo ART-COLOR-TALLE
        qty: cantidad a mover (positiva). Tipo=2 restará, Tipo=1 sumará.
        observacion: texto a enviar en el campo Observacion (idempotencia sugerida)
        origen_destino: valor para OrigenDestino (default config)
        tipo: 2=resta, 1=suma (default config)
        base_datos_header: header BaseDeDatos (default 'MELI' si no hay config)

    Returns:
        dict con { 'ok': bool, 'status': int, 'data': any, 'error': str|None }
    """
    if not DRAGON_MOV_URL:
        return {"ok": False, "status": 0, "data": None, "error": "DRAGON_MOV_URL no configurada"}

    articulo_raw, color_raw, talle_raw = _parse_sku(sku)
    if not articulo_raw:
        return {"ok": False, "status": 0, "data": None, "error": "SKU/artículo inválido"}

    od = (origen_destino or MOV_ORIGENDESTINO_DEFAULT or "MELI").strip()
    tp = int(tipo if tipo is not None else MOV_TIPO_DEFAULT)
    base_db = (base_datos_header or DRAGON_BASEDEDATOS or "MELI").strip()

    # Autorización: algunos servidores aceptan token crudo, otros requieren 'Bearer <token>'.
    # Además, soportar credenciales alternativas.
    cred_list = [
        {
            "IdCliente": (DRAGON_ID_CLIENTE or "").strip(),
            "Token": (DRAGON_API_KEY or "").strip(),
            "Label": "primary",
        }
    ]
    if (DRAGON_ALT_ID_CLIENTE or DRAGON_ALT_API_KEY):
        cred_list.append({
            "IdCliente": (DRAGON_ALT_ID_CLIENTE or DRAGON_ID_CLIENTE or "").strip(),
            "Token": (DRAGON_ALT_API_KEY or DRAGON_API_KEY or "").strip(),
            "Label": "alt",
        })

    fecha = _dragon_date()
    hora = _dragon_time()

    # Elegir código a enviar (priorizar barcode) y normalizar si viene del SKU
    code_input = barcode or sku
    code_norm = _normalize_code(code_input)

    # Decidir Color/Talle: priorizar lo que venga del SKU original
    # Si no hay, intentar derivarlo del code_norm (solo si tiene 3 partes)
    parts = (sku or '').split('-')
    if len(parts) >= 3:
        color_send = (color_raw or parts[1].strip() or "")
        talle_send = (talle_raw or parts[2].strip() or "")
    else:
        parts_norm = code_norm.split('-') if code_norm else []
        if len(parts_norm) >= 3:
            color_send = parts_norm[1].strip()
            talle_send = parts_norm[2].strip()
        else:
            color_send = ""
            talle_send = ""

    # Fallback: si no llega articulo_detalle, intentar obtener ARTDES por DB
    articulo_detalle_final = (articulo_detalle or "").strip()
    color_codigo_final = (color_codigo or "").strip() or None
    talle_codigo_final = (talle_codigo or "").strip() or None

    if (not articulo_detalle_final) and barcode:
        try:
            info = _get_article_info_from_db(barcode)
            if info:
                articulo_detalle_final = (info.get("ARTDES") or "").strip()
                # Si no llegan color/talle y DB los tiene, usarlos
                if not color_codigo_final:
                    color_codigo_final = (info.get("CODIGO_COLOR") or "").strip() or None
                if not talle_codigo_final:
                    talle_codigo_final = (info.get("CODIGO_TALLE") or "").strip() or None
        except Exception:
            # No romper por errores de DB: seguimos con valores actuales
            pass

    body = {
        # Cabecera
        "OrigenDestino": od,
        "Tipo": tp,
        "Motivo": "API",
        "vendedor": "API",
        "Remito": "-",
        "CompAfec": [],
        "Fecha": fecha,
        "Observacion": observacion,
        # Detalle
        "MovimientoDetalle": [
            {
                # Según payload de referencia del usuario: usar el código de barras como Articulo
                # y NO incluir el campo "Codigo" en absoluto. Mantener ArticuloDetalle, Color y Talle.
                "Articulo": code_norm,
                "ArticuloDetalle": articulo_detalle_final,
                "Color": (color_codigo_final or color_send),
                "Talle": (talle_codigo_final or talle_send),
                "Cantidad": qty,
                "NroItem": 1,
            }
        ],
        # Info adicional
        "InformacionAdicional": {
            "FechaAltaFW": fecha,
            "HoraAltaFW": hora,
            "EstadoTransferencia": "PENDIENTE",
            "BaseDeDatosAltaFW": base_db,
            "BaseDeDatosModificacionFW": base_db,
            "SerieAltaFW": "901224",
            "SerieModificacionFW": "901224",
            "UsuarioAltaFW": "API",
            "UsuarioModificacionFW": "API",
        },
    }

    # Debug/Info: mostrar payload antes del POST (sin credenciales)
    try:
        # INFO compacto y seguro
        safe_det = body.get("MovimientoDetalle", [{}])[0]
        safe_info = {
            "OrigenDestino": body.get("OrigenDestino"),
            "Tipo": body.get("Tipo"),
            "Observacion": body.get("Observacion"),
            "Articulo": safe_det.get("Articulo"),
            "ArticuloDetalle": safe_det.get("ArticuloDetalle"),
            "Color": safe_det.get("Color"),
            "Talle": safe_det.get("Talle"),
            "Cantidad": safe_det.get("Cantidad"),
            "BaseDeDatos": headers.get("BaseDeDatos"),
        }
        logger.info(f"Dragon MOVE → request: {json.dumps(safe_info, ensure_ascii=False)}")
        # DEBUG completo
        dbg_headers = {k: v for k, v in headers.items() if k.lower() != 'authorization'}
        logger.debug(f"Dragon MOVE headers: {dbg_headers}")
        logger.debug(f"Dragon MOVE body: {json.dumps(body, ensure_ascii=False)}")
    except Exception:
        # No romper por logging
        pass

    def _do_post(hdrs):
        r = requests.post(DRAGON_MOV_URL, headers=hdrs, data=json.dumps(body), timeout=None)
        st = r.status_code
        try:
            dt = r.json() if r.content else None
        except Exception:
            dt = r.text
        return st, dt

    try:
        status = 0
        data = None
        ok = False
        numero = None
        last_err = None
        for cred in cred_list:
            tok = cred["Token"]
            idc = cred["IdCliente"]
            # headers raw
            headers_raw = {
                "accept": "application/json",
                "IdCliente": idc,
                "Authorization": tok,
                "Content-Type": "application/json",
                "BaseDeDatos": base_db,
            }
            # headers bearer
            headers_bearer = {
                **headers_raw,
                "Authorization": tok if tok.lower().startswith("bearer ") else (f"Bearer {tok}" if tok else ""),
            }
            # 1) raw
            status, data = _do_post(headers_raw)
            if status in (200, 201, 409):
                ok = True
                break
            if status in (400, 401) and tok:
                # 2) bearer
                logger.info(f"Dragon MOVE retry con Authorization Bearer (cred={cred['Label']}, IdCliente={idc})")
                try:
                    status, data = _do_post(headers_bearer)
                except Exception as e:
                    last_err = e
                    status, data = 0, None
                if status in (200, 201, 409):
                    ok = True
                    break

        # Tratar 201 (creado), 200 (algunas variantes) y 409 (duplicado idempotente) como éxito
        ok = ok or (status in (200, 201, 409))

        # Intentar extraer el número de movimiento como en los scripts de referencia
        if isinstance(data, dict):
            for k in ("Numero", "NroMovimiento", "Id", "IdMovimiento", "NumeroMovimiento"):
                if k in data and data[k]:
                    try:
                        numero = int(str(data[k]).strip())
                    except Exception:
                        try:
                            numero = int(''.join(ch for ch in str(data[k]) if ch.isdigit()))
                        except Exception:
                            numero = None
                    break
        if numero is None and isinstance(data, (str, bytes)):
            import re
            m = re.search(r"\b(\d{5,})\b", data if isinstance(data, str) else data.decode(errors='ignore'))
            numero = int(m.group(1)) if m else None

        # Log en INFO un resumen y en DEBUG el cuerpo
        try:
            brief = data if isinstance(data, (str, int, float)) else (
                {k: data.get(k) for k in ("Numero", "Mensaje", "mensaje", "status", "ok") if isinstance(data, dict) and k in data}
                if isinstance(data, dict) else None
            )
            logger.info(f"Dragon MOVE ← response: status={status} data={brief if brief is not None else str(data)[:300]}")
            logger.debug(f"Dragon MOVE full response: {data}")
        except Exception:
            pass

        return {
            "ok": ok,
            "status": status,
            "data": data,
            "numero": numero,
            "od": od,
            "base_db": base_db,
            "error": None if ok else (str(data)[:500] if data is not None else "")
        }
    except requests.Timeout as e:
        return {"ok": False, "status": 0, "data": None, "error": f"timeout: {e}"}
    except requests.RequestException as e:
        return {"ok": False, "status": 0, "data": None, "error": f"request_error: {e}"}
    except Exception as e:
        return {"ok": False, "status": 0, "data": None, "error": f"unexpected: {e}"}
