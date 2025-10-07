"""Wrapper sencillo para la API Dragonfish"""
from __future__ import annotations

import requests
import json
import time
import uuid
from datetime import datetime, timezone, timedelta

from utils import config
from utils.logger import get_logger
from .base import APIError

log = get_logger(__name__)

BASE_URL = getattr(config, "DRAGONFISH_BASE_URL", "http://190.211.201.217:8888/api.Dragonfish")


def _headers(deposito_origen: str = "DEPOSITO") -> dict:
    """Headers dinámicos según el depósito origen.
    
    Para CABA (MUNDOCAB): BaseDeDatos = "MELI" (destino)
    Para DEPOSITO: BaseDeDatos = "DEPOSITO" (origen)
    """
    # Formato invertido para CABA y ROCA
    if deposito_origen in ("MUNDOCAB", "MUNDOROC"):
        base_datos = "WOO"  # Para CABA/ROCA: BaseDeDatos es el DESTINO
    else:
        base_datos = "DEPOSITO"  # Para DEPOSITO: BaseDeDatos es el ORIGEN
        
    return {
        "accept": "application/json",
        "Authorization": config.DRAGONFISH_TOKEN,
        "IdCliente": getattr(config, "DRAGONFISH_IDCLIENTE", "MATIAPP"),
        "Content-Type": "application/json",
        "BaseDeDatos": base_datos,
    }


def _fecha_dragonfish() -> str:
    zona = timezone(timedelta(hours=-3))
    ms = int(datetime.now(zona).timestamp() * 1000)
    return f"/Date({ms}-0300)/"


def _hora_dragonfish() -> str:
    return datetime.now().strftime("%H:%M:%S")


def send_stock_movement(pedido_id: int | str, codigo_barra: str, cantidad: int, datos_articulo: dict) -> tuple[bool, str]:
    """Envía movimiento de stock con formato dinámico según el depósito.
    
    Para CABA (MUNDOCAB): Formato invertido (Tipo=1, OrigenDestino=MUNDOCAB, BaseDeDatos=MELI)
    Para DEPOSITO: Formato normal (Tipo=2, OrigenDestino=MELI, BaseDeDatos=DEPOSITO)
    """
    # Detectar si estamos en CABA o ROCA
    import os
    es_caba = os.environ.get('CABA_VERSION') == 'true'
    es_roca = os.environ.get('ROCA_VERSION') == 'true'
    if es_caba:
        deposito_origen = "MUNDOCAB"
    elif es_roca:
        deposito_origen = "MUNDOROC"
    else:
        deposito_origen = "DEPOSITO"
    
    url = f"{BASE_URL}/Movimientodestock/"
    # Datos para enriquecer la descripción (Observacion)
    hora_txt = _hora_dragonfish()
    articulo_obs = datos_articulo.get("CODIGO_BARRA", codigo_barra)
    movimiento_id = f"MV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    
    # Formato invertido para CABA/ROCA
    if es_caba or es_roca:
        body = {
            "OrigenDestino": deposito_origen,  # Origen en payload (MUNDOCAB/MUNDOROC)
            "Tipo": 1,  # Entrada (no salida)
            "Motivo": "API",
            "vendedor": "API",
            "Remito": "-",
            "CompAfec": [],
            "Fecha": _fecha_dragonfish(),
            # Observación enriquecida: ORIGEN->DESTINO | hora | prenda | cant | pedido | movID
            "Observacion": (
                f"{deposito_origen} -> WOO | {hora_txt} | Art:{articulo_obs} | Cant:{cantidad} | "
                f"Pedido:{pedido_id} | ID:{movimiento_id}"
            ),
            "MovimientoDetalle": [
                {
                    "Articulo": datos_articulo.get("CODIGO_BARRA", codigo_barra),
                    "ArticuloDetalle": datos_articulo.get("ARTDES", ""),
                    "Color": datos_articulo.get("CODIGO_COLOR"),
                    "Talle": datos_articulo.get("CODIGO_TALLE"),
                    "Cantidad": cantidad,
                    "NroItem": 1,
                }
            ],
            "InformacionAdicional": {
                "FechaTransferencia": None,
                "EstadoTransferencia": "",  # Vacío para CABA
                "FechaAltaFW": None,  # Null para CABA
                "HoraAltaFW": "",  # Vacío para CABA
                "FechaModificacionFW": None,  # Null para CABA
                "HoraModificacionFW": "",  # Vacío para CABA
                "FechaImpo": None,
                "HoraImpo": "",
                "FechaExpo": None,
                "HoraExpo": "",
                "UsuarioAltaFW": "",  # Vacío para CABA
                "UsuarioModificacionFW": "",  # Vacío para CABA
                "SerieAltaFW": "",  # Vacío para CABA
                "SerieModificacionFW": "",  # Vacío para CABA
                "BaseDeDatosAltaFW": "",  # Vacío para CABA
                "BaseDeDatosModificacionFW": "",  # Vacío para CABA
                "VersionAltaFW": "",
                "VersionModificacionFW": "",
                "ZADSFW": ""
            }
        }
    else:
        # Formato DEPOSITO: normal
        body = {
            "OrigenDestino": "MELI",  # Destino en payload
            "Tipo": 2,  # Salida
            "Motivo": "API",
            "vendedor": "API",
            "Remito": "-",
            "CompAfec": [],
            "Fecha": _fecha_dragonfish(),
            # Observación enriquecida: ORIGEN->DESTINO | hora | prenda | cant | pedido | movID
            "Observacion": (
                f"DEPOSITO -> MELI | {hora_txt} | Art:{articulo_obs} | Cant:{cantidad} | "
                f"Pedido:{pedido_id} | ID:{movimiento_id}"
            ),
            "MovimientoDetalle": [
                {
                    "Articulo": datos_articulo.get("CODIGO_BARRA", codigo_barra),
                    "ArticuloDetalle": datos_articulo.get("ARTDES", ""),
                    "Color": datos_articulo.get("CODIGO_COLOR"),
                    "Talle": datos_articulo.get("CODIGO_TALLE"),
                    "Cantidad": cantidad,
                    "NroItem": 1,
                }
            ],
            "InformacionAdicional": {
                "FechaAltaFW": _fecha_dragonfish(),
                "HoraAltaFW": _hora_dragonfish(),
                "EstadoTransferencia": "PENDIENTE",
                "BaseDeDatosAltaFW": "MELI",
                "BaseDeDatosModificacionFW": "MELI",
                "SerieAltaFW": "901224",
                "SerieModificacionFW": "901224",
                "UsuarioAltaFW": "API",
                "UsuarioModificacionFW": "API",
            }
        }

    # LOGS DETALLADOS para debugging
    articulo_enviado = body['MovimientoDetalle'][0]['Articulo']
    cantidad_enviada = body['MovimientoDetalle'][0]['Cantidad']

    # Construir headers con el deposito_origen para ver BaseDeDatos real
    headers = _headers(deposito_origen)
    base_datos_hdr = headers.get("BaseDeDatos")

    # Logs explícitos y prints para consola
    log.info("📦 DRAGONFISH MOVIMIENTO")
    log.info("   🌐 URL: %s", url)
    log.info("   🗃️ BaseDeDatos(header): %s", base_datos_hdr)
    log.info("   🧭 OrigenDestino(body): %s", body.get("OrigenDestino"))
    log.info("   🔄 Tipo(body): %s (%s)", body.get("Tipo"), 'Entrada' if body.get('Tipo') == 1 else 'Salida')
    log.info("   🏷️ Artículo: %s", articulo_enviado)
    log.info("   🔢 Cantidad: %s", cantidad_enviada)
    log.info("   📝 Observación: %s", body.get("Observacion"))

    # PRINTS para consola del EXE (--console)
    try:
        print("\n==== DRAGONFISH REQUEST ====")
        print(f"URL: {url}")
        print(f"Headers: {json.dumps(headers, ensure_ascii=False)}")
        print(f"Body: {json.dumps(body, ensure_ascii=False)}")
        print("===========================\n")
    except Exception:
        # No romper por issues de encoding en consola
        pass

    # SOLUCIÓN ESTRUCTURAL: SOLO 1 INTENTO para evitar descuentos múltiples
    # El problema era que cada timeout reiniciaba la operación pero el servidor YA procesó el movimiento
    log.info("Dragonfish movimiento - INTENTO ÚNICO (sin reintentos)")
    
    try:
        # TIMEOUT AUMENTADO para evitar timeouts por red lenta
        resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=30)
        
        if 200 <= resp.status_code < 300:
            log.info("✅ MOVIMIENTO EXITOSO - Status: %s", resp.status_code)
            log.debug("Respuesta Dragonfish (texto): %s", (resp.text or "")[:1000])
            try:
                print("\n==== DRAGONFISH RESPONSE (OK) ====")
                print(f"Status: {resp.status_code}")
                print(f"Body: {resp.text}")
                print("=================================\n")
            except Exception:
                pass
            return True, "OK"
        else:
            log.warning("⚠️ Dragonfish movimiento FAIL – status %s – cuerpo: %s", resp.status_code, (resp.text or "")[:1000])
            try:
                print("\n==== DRAGONFISH RESPONSE (FAIL) ====")
                print(f"Status: {resp.status_code}")
                print(f"Body: {resp.text}")
                print("===================================\n")
            except Exception:
                pass
            return False, f"HTTP {resp.status_code}"
            
    except requests.Timeout as e:
        log.error("⏰ Dragonfish movimiento TIMEOUT (30s) (%s → MELI) - POSIBLE ÉXITO en servidor: %s", deposito_origen, e)
        # CRÍTICO: En timeout, asumir que SÍ se procesó para evitar descuentos múltiples
        try:
            print("\n==== DRAGONFISH TIMEOUT (ASUMIDO OK) ====")
            print(str(e))
            print("========================================\n")
        except Exception:
            pass
        return True, "TIMEOUT - Asumido como exitoso"
        
    except requests.RequestException as e:
        log.error("❌ Dragonfish movimiento ERROR de conexión: %s", e)
        try:
            print("\n==== DRAGONFISH ERROR ====")
            print(str(e))
            print("========================\n")
        except Exception:
            pass
        return False, f"ERROR: {str(e)[:100]}"
