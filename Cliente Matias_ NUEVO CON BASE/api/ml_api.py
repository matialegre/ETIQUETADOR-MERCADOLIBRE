"""Wrappers de MercadoLibre API"""
from __future__ import annotations

import requests
from datetime import datetime
from typing import List, Dict

from utils import config
from utils.logger import get_logger
from .base import APIError

log = get_logger(__name__)

BASE_URL = "https://api.mercadolibre.com"

def refresh_access_token() -> tuple[str, str]:
    """Obtiene un access_token válido de ML1.

    Preferencia: usar el helper centralizado basado en token.json para asegurar
    el uso de la misma app (daemon) y refrescar solo cuando sea necesario.
    Fallback: flujo clásico con variables de entorno en `utils.config`.
    """
    # 1) Intentar helper centralizado (token.json)
    try:
        from utils.meli_token_helper import refresh_if_needed  # type: ignore
        cfg = refresh_if_needed()
        access_token = cfg.get("access_token", "")
        seller_id = str(cfg.get("user_id", "") or "")
        if not access_token:
            raise RuntimeError("access_token vacío desde helper")
        # Si no vino user_id en el archivo, intentar consultarlo
        if not seller_id:
            who = requests.get(f"{BASE_URL}/users/me", headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            if who.status_code == 200:
                seller_id = str(who.json().get("id", ""))
        return access_token, seller_id
    except Exception as helper_err:
        log.warning("Token helper no disponible o falló (%s). Usando fallback por config.", helper_err)

    # 2) Fallback: flujo OAuth clásico usando variables de entorno (.env)
    url = f"{BASE_URL}/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": config.ML_CLIENT_ID,
        "client_secret": config.ML_CLIENT_SECRET,
        "refresh_token": config.ML_REFRESH_TOKEN,
    }
    resp = requests.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if resp.status_code != 200:
        raise APIError.from_response(resp)
    js = resp.json()
    access_token = js["access_token"]
    seller_id = str(js.get("user_id", ""))
    return access_token, seller_id

def list_orders(seller_id: str, access_token: str, date_from: datetime, date_to: datetime) -> List[Dict]:
    offset, limit = 50, 50
    orders: list[dict] = []
    while True:
        from_str = f"{date_from.strftime('%Y-%m-%d')}T00:00:00.000-00:00"
        to_str = f"{date_to.strftime('%Y-%m-%d')}T23:59:59.000-00:00"
        url = (
            f"{BASE_URL}/orders/search?seller={seller_id}&offset={offset - limit}&limit={limit}"
            f"&order.date_created.from={from_str}&order.date_created.to={to_str}"
        )
        resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code != 200:
            raise APIError.from_response(resp)
        res = resp.json().get("results", [])
        if not res:
            break
        orders.extend(res)
        if len(res) < limit:
            break
        offset += limit
    return orders

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_order_note(order_id: int | str, access_token: str) -> str:
    """Devuelve la primera nota (si existe) del pedido."""
    url = f"{BASE_URL}/orders/{order_id}/notes"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        return ""
    arr = resp.json()
    if arr and arr[0].get("results"):
        return arr[0]["results"][0].get("note", "")
    return ""

def get_shipment_substatus(shipping_id: int | None, access_token: str) -> str | None:
    if not shipping_id:
        return None
    url = f"{BASE_URL}/shipments/{shipping_id}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    if resp.status_code != 200:
        return None
    return resp.json().get("substatus")

def get_pack_orders(pack_id: int | str, access_token: str) -> List[int] | None:
    """Obtiene todas las order_id que pertenecen a un pack_id.
    
    Retorna una lista de order_ids o None si hay error.
    """
    if not pack_id:
        return None
    
    url = f"{BASE_URL}/packs/{pack_id}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    
    if resp.status_code != 200:
        log.warning("Error obteniendo pack %s: %s", pack_id, resp.status_code)
        return None
    
    pack_data = resp.json()
    orders = pack_data.get("orders", [])
    
    # Extraer solo los IDs de las órdenes
    order_ids = [order["id"] for order in orders if "id" in order]
    
    log.debug("Pack %s contiene %d órdenes: %s", pack_id, len(order_ids), order_ids)
    return order_ids

def get_order_details(order_id: int | str, access_token: str) -> Dict | None:
    """Obtiene los detalles completos de una orden específica.
    
    Retorna el JSON de la orden o None si hay error.
    """
    if not order_id:
        return None
        
    url = f"{BASE_URL}/orders/{order_id}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"})
    
    if resp.status_code != 200:
        log.warning("Error obteniendo orden %s: %s", order_id, resp.status_code)
        return None
        
    return resp.json()

def get_latest_note(order_id: int | str, access_token: str) -> str:
    """Obtiene la nota más reciente de una orden basándose en timestamp.
    
    Utiliza el endpoint /orders/{order_id}/notes para obtener todas las notas
    y retorna el contenido de la nota más reciente según fecha/hora.
    
    Args:
        order_id: ID de la orden
        access_token: Token de acceso de ML
        
    Returns:
        str: Contenido de la nota más reciente, o string vacío si no hay notas
    """
    if not order_id:
        return ""
        
    url = f"{BASE_URL}/orders/{order_id}/notes"
    
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        
        if resp.status_code == 404:
            # Orden sin notas
            log.debug("Orden %s no tiene notas", order_id)
            return ""
            
        if resp.status_code != 200:
            log.warning("Error obteniendo notas de orden %s: %s", order_id, resp.status_code)
            return ""
            
        notes_data = resp.json()
        
        # El endpoint puede devolver diferentes formatos según la versión de la API
        notes_list = []
        
        # DEBUG: Mostrar estructura de respuesta
        log.debug(f"📋 Estructura de respuesta para orden {order_id}: {type(notes_data)} - {notes_data}")
        
        if isinstance(notes_data, list):
            # Formato: lista con objetos que contienen "results"
            # Ejemplo: [{"results": [{"note": "..."}], "order_id": "..."}]
            for item in notes_data:
                if isinstance(item, dict) and "results" in item:
                    results = item["results"]
                    if isinstance(results, list):
                        notes_list.extend(results)
                    elif isinstance(results, dict):
                        notes_list.append(results)
                elif isinstance(item, dict) and "note" in item:
                    # Nota directa en el item
                    notes_list.append(item)
        elif isinstance(notes_data, dict):
            if "results" in notes_data:
                # Formato: {"results": [notas...]}
                results = notes_data["results"]
                if isinstance(results, list):
                    notes_list = results
                elif isinstance(results, dict) and "note" in results:
                    # Una sola nota en formato {"results": {"note": "...", "date_created": "..."}}
                    notes_list = [results]
            elif "note" in notes_data:
                # Una sola nota directa
                notes_list = [notes_data]
        
        if not notes_list:
            log.debug("Orden %s: no se encontraron notas en la respuesta", order_id)
            return ""
        
        # Buscar la nota más reciente por fecha
        latest_note = None
        latest_date = None
        
        for note in notes_list:
            if not isinstance(note, dict):
                continue
                
            note_text = note.get("note") or note.get("plain_text") or ""
            date_created = note.get("date_created") or note.get("created_date")
            
            if not note_text:
                continue
                
            # Si no hay fecha, usar la nota (fallback)
            if not date_created:
                if latest_note is None:
                    latest_note = note_text
                continue
                
            try:
                # Parsear fecha (formato ISO de ML: "2025-07-23T15:24:00.000-03:00")
                note_datetime = datetime.fromisoformat(date_created.replace('Z', '+00:00'))
                
                if latest_date is None or note_datetime > latest_date:
                    latest_date = note_datetime
                    latest_note = note_text
                    
            except (ValueError, TypeError) as e:
                log.debug("Error parseando fecha de nota %s: %s", date_created, e)
                # Si no se puede parsear la fecha, usar como fallback
                if latest_note is None:
                    latest_note = note_text
        
        result = latest_note or ""
        
        if result:
            log.debug("📝 Orden %s: nota más reciente obtenida (%s chars)", order_id, len(result))
        else:
            log.debug("📝 Orden %s: no se pudo obtener nota válida", order_id)
            
        return result
        
    except requests.RequestException as e:
        log.warning("Error de conexión obteniendo notas de orden %s: %s", order_id, e)
        return ""
    except Exception as e:
        log.error("Error inesperado obteniendo notas de orden %s: %s", order_id, e)
        return ""
