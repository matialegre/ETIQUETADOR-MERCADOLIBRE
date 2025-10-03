"""
MÓDULO DRAGONFISH API - CONSULTA DE STOCK (REAL)
===============================================

Consulta stock en tiempo real desde la API Dragonfish.
- Método soportado: GET ConsultaStockYPreciosEntreLocales por ART (SKU)
- Filtro exacto por COLOR y TALLE según el SKU formateado ART-COLOR-TALLE

Sin simulaciones ni datos mock. Usa la configuración real en `modules/config.py`.

Autor: Cascade AI
Fecha: 2025-08-08
"""

from __future__ import annotations

import requests
from typing import Dict, Tuple, Optional, Any, List
import re

# Cargar configuración real
import sys
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')
from config import DRAGON_API_BASE, DRAGON_API_KEY, DRAGON_ID_CLIENTE, DRAGON_BASEDEDATOS, API_TIMEOUT

# Timeout extendido (la API puede demorar ~1 minuto)
REQUEST_TIMEOUT = max(API_TIMEOUT, 65)

# Depósitos válidos esperados (oficiales)
VALID_DEPOTS = {
    'DEP', 'MDQ', 'MONBAHIA', 'MTGBBPS', 'MTGCBA', 'MTGCOM', 'MTGJBJ', 'MTGROCA',
    'MUNDOAL', 'MUNDOCAB', 'MUNDOROC', 'NQNALB', 'NQNSHOP'
}


def _parse_sku(sku: str) -> Optional[Tuple[str, str, str]]:
    """
    Parsea SKU estilo ART-COLOR-TALLE y retorna (ART, COLOR, TALLE).
    Devuelve None si no se puede parsear.
    """
    if not sku:
        return None
    parts = sku.strip().split('-')
    if len(parts) < 3:
        return None
    art = parts[0].strip()
    color = parts[1].strip()
    talle = parts[2].strip()
    return (art, color, talle)


def _match_color_talle(item: dict, color: str, talle: str) -> bool:
    """Intenta matchear color/talle con variantes de nombres y normalización robusta."""
    def norm(s: Any) -> str:
        s = str(s or '').strip().upper()
        s = re.sub(r"[^A-Z0-9]", "", s)
        return s

    def eq_talle(a: str, b: str) -> bool:
        # Igualar '3', '03', '003', etc.
        a_n = a.lstrip('0') or '0'
        b_n = b.lstrip('0') or '0'
        return a == b or a_n == b_n

    color_target = norm(color)
    talle_target = norm(talle)

    candidates_color = [
        item.get('color'), item.get('COLOR'), item.get('Color'),
        item.get('color_codigo'), item.get('COLOR_CODIGO'), item.get('ColorCodigo'),
        item.get('codigo_color'), item.get('CODCOLOR'), item.get('CodColor'),
        item.get('ColorAbrev'), item.get('COLOR_ABREV'), item.get('ColorCod')
    ]
    candidates_talle = [
        item.get('talle'), item.get('TALLE'), item.get('Talle'),
        item.get('talle_codigo'), item.get('TALLE_CODIGO'), item.get('TalleCodigo'),
        item.get('codigo_talle'), item.get('CODTALLE'), item.get('CodTalle'),
        item.get('TalleAbrev'), item.get('TALLE_ABREV')
    ]
    col_ok = any(norm(c) == color_target for c in candidates_color)
    tal_ok = any(eq_talle(norm(t), talle_target) for t in candidates_talle)
    return col_ok and tal_ok


def get_stock_by_sku(sku: str) -> Dict[str, Dict[str, int]]:
    """
    Consulta stock por SKU usando GET ConsultaStockYPreciosEntreLocales.
    - Hace query por ARTICULO (ART)
    - Filtra por COLOR y TALLE exactos

    Returns dict por depósito: {'DEPOT': {'total': int, 'reserved': int}}
    """
    parsed = _parse_sku(sku)
    if not parsed:
        print(f"❌ SKU inválido para consulta Dragonfish: {sku}")
        return {}
    art, color, talle = parsed

    try:
        # Variantes de headers/params para sortear 401 o diferencias de API
        # Headers según doc: IdCliente + Authorization (token plano). Probamos variantes.
        base_headers = {'IdCliente': DRAGON_ID_CLIENTE or ''}
        if DRAGON_BASEDEDATOS:
            base_headers['BaseDeDatos'] = DRAGON_BASEDEDATOS
        header_options: List[Dict[str, str]] = [
            {**base_headers, 'Authorization': DRAGON_API_KEY},
            {**base_headers, 'Authorization': f'Bearer {DRAGON_API_KEY}'},
            {**base_headers, 'x-api-key': DRAGON_API_KEY},
        ]
        # Param principal por doc: 'query'
        param_keys = ['query', 'art', 'articulo', 'ARTICULO']

        last_status = None
        last_text = ''
        data: Any = {}
        chosen_headers: Optional[Dict[str, str]] = None
        # 1) Primer intento: encontrar combinación headers/param que responda 200
        for hdr in header_options:
            for key in param_keys:
                params = {key: art, 'page': 1, 'limit': 100}
                try:
                    # Asegurar slash final para evitar 307 -> 200 innecesario
                    base_url = (DRAGON_API_BASE.rstrip('/') + '/')
                    resp = requests.get(
                        base_url,
                        headers=hdr,
                        params=params,
                        timeout=REQUEST_TIMEOUT,
                    )
                except requests.exceptions.Timeout:
                    print(f"❌ Timeout consultando Dragonfish para SKU {sku} (headers={list(hdr.keys())}, param={key})")
                    continue

                last_status = resp.status_code
                last_text = resp.text[:200] if resp.text else ''
                if resp.status_code == 200:
                    data = resp.json() if resp.content else {}
                    chosen_headers = hdr
                    break
            if data:
                break

        if not data:
            print(f"❌ Dragonfish {last_status}: {last_text}")
            return {}

        # Estructura flexible: preferir doc oficial "Resultados" y luego variantes
        stock_result: Dict[str, Dict[str, int]] = {}

        def _extract_from_payload(payload: Any) -> Optional[Dict[str, Dict[str, int]]]:
            """Devuelve dict de stock si encuentra el ART-COLOR-TALLE; si no, None."""
            # Intento 1 (doc): Resultados -> item por color/talle -> Stock[{BaseDeDatos, Stock}]
            stock_list_local: List[dict] = []
            if isinstance(payload, dict):
                if isinstance(payload.get('Resultados'), list):
                    for it in payload['Resultados']:
                        # Coincidir artículo exacto y color/talle
                        if str(it.get('Articulo', '')).strip().upper() != art.upper():
                            continue
                        if _match_color_talle(it, color, talle):
                            stk = it.get('Stock') or []
                            if isinstance(stk, list):
                                tmp: Dict[str, Dict[str, int]] = {}
                                for d in stk:
                                    depot = str(d.get('BaseDeDatos', '')).upper()
                                    if depot == 'DEPOSITO':
                                        depot = 'DEP'
                                    total = int(d.get('Stock', 0) or 0)
                                    reservado = 0
                                    if depot in VALID_DEPOTS:
                                        tmp[depot] = {'total': total, 'reserved': reservado}
                                return tmp
                # Caso 2: stock directo
                if isinstance(payload.get('stock'), list):
                    stock_list_local = payload['stock']
                # Caso 2b: items → buscar por color/talle
                elif isinstance(payload.get('items'), list):
                    for it in payload['items']:
                        if _match_color_talle(it, color, talle):
                            stk = it.get('stock') or it.get('Stock') or []
                            if isinstance(stk, list):
                                stock_list_local = stk
                                break
                # Caso 3: resultados en raíz como lista de items
                elif isinstance(payload.get('results'), list):
                    for it in payload['results']:
                        if _match_color_talle(it, color, talle):
                            stk = it.get('stock') or it.get('Stock') or []
                            if isinstance(stk, list):
                                stock_list_local = stk
                                break
            elif isinstance(payload, list):
                # Lista de items directamente
                for it in payload:
                    if _match_color_talle(it, color, talle):
                        stk = it.get('stock') or it.get('Stock') or []
                        if isinstance(stk, list):
                            stock_list_local = stk
                            break

            if stock_list_local:
                tmp: Dict[str, Dict[str, int]] = {}
                for d in stock_list_local:
                    depot = str(d.get('deposito', d.get('deposit', d.get('Deposito', d.get('BaseDeDatos', ''))))).upper()
                    if depot == 'DEPOSITO':
                        depot = 'DEP'
                    total = int(d.get('total', d.get('cantidad', d.get('Cantidad', d.get('Stock', 0)))) or 0)
                    reservado = int(d.get('reservado', d.get('reserved', d.get('Reservado', 0))) or 0)
                    if depot in VALID_DEPOTS:
                        tmp[depot] = {'total': total, 'reserved': reservado}
                return tmp
            return None

        # 2) Paginación: recorrer páginas siguiendo 'Siguiente' si no se encontró en la primera
        # Guardado para seguridad: máximo 50 páginas
        max_pages = 50
        pages_checked = 0
        current_payload = data
        while current_payload and pages_checked < max_pages:
            pages_checked += 1
            extracted = _extract_from_payload(current_payload)
            if extracted:
                return extracted
            # Seguir link 'Siguiente'
            next_url = None
            if isinstance(current_payload, dict):
                nxt = current_payload.get('Siguiente') or current_payload.get('siguiente') or current_payload.get('next')
                if isinstance(nxt, str) and nxt.strip():
                    next_url = nxt.strip()
            if not next_url:
                break
            try:
                resp = requests.get(next_url, headers=chosen_headers or {}, timeout=REQUEST_TIMEOUT)
            except requests.exceptions.Timeout:
                print(f"❌ Timeout paginando Dragonfish para SKU {sku} (page {pages_checked+1})")
                break
            if resp.status_code != 200:
                break
            current_payload = resp.json() if resp.content else None

        # Si no se encontró en ninguna página, devolver lo acumulado (vacío)
        return stock_result

    except requests.exceptions.Timeout:
        print(f"❌ Timeout consultando Dragonfish para SKU {sku}")
        return {}
    except requests.RequestException as e:
        print(f"❌ Error de red Dragonfish: {e}")
        return {}
    except Exception as e:
        print(f"❌ Error inesperado Dragonfish: {e}")
        return {}


def get_stock_for_barcode(barcode: str) -> Dict[str, Dict[str, int]]:
    """
    Mantenido por compatibilidad. La estrategia oficial es por SKU.
    """
    print("⚠️ Consulta por barcode no soportada por el endpoint actual; usar get_stock_by_sku(sku)")
    return {}


if __name__ == "__main__":
    # Pequeño test manual (requiere conectividad real)
    sku_test = 'NDPMB7E774-NN0-46'
    print(f"🔍 Probando Dragonfish real para SKU {sku_test}...")
    s = get_stock_by_sku(sku_test)
    print("Resultado:", s)
