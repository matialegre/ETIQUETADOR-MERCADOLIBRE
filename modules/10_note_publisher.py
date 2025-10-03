"""
Modulo 10: Publicador de notas MercadoLibre (idempotente)
=========================================================

- Selecciona token por seller (multi-cuenta) leyendo config/token.json y config/token_02.json
- Upsert/replace del bloque [APPMATI: ...]
- Agrega/asegura una etiqueta de stock: [STOCK -qty MOV N]
- Reintento con refresh de token una vez si expira
"""
from __future__ import annotations

import os
import json
import re
import requests
from typing import Optional, Dict

# Rutas por defecto
PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TOKEN_PATHS = [
    os.path.join(PROJ_ROOT, 'config', 'token.json'),
    os.path.join(PROJ_ROOT, 'config', 'token_02.json'),
    # Path legacy GUI por compatibilidad
    r'C:\Users\Mundo Outdoor\Desktop\Develop_Mati\Escritor Meli\token.json',
]

API_BASE = "https://api.mercadolibre.com"


def _load_token(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_token(path: str, data: dict) -> None:
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _find_token_for_seller(seller_id: Optional[str|int]) -> Optional[str]:
    sid = str(seller_id or '').strip()
    candidates: list[tuple[str, dict]] = []
    for p in TOKEN_PATHS:
        if os.path.exists(p):
            data = _load_token(p)
            if data.get('access_token'):
                candidates.append((p, data))
    if not candidates:
        return None
    # Match por user_id si está disponible
    for p, d in candidates:
        if str(d.get('user_id', '')).strip() == sid and sid:
            return p
    # Fallback: si hay 2, usar heurística simple por seller conocido
    if sid in ('756086955', '209611492') and len(candidates) >= 2:
        # Mantener orden: token.json (p0) y token_02.json (p1)
        # Por convención, 756086955 suele ser la cuenta 2
        if sid == '756086955':
            for p, _ in candidates:
                if p.endswith('token_02.json'):
                    return p
        if sid == '209611492':
            for p, _ in candidates:
                if p.endswith('token.json'):
                    return p
    # Último recurso: el primero
    return candidates[0][0]


def _refresh_token_inplace(path: str) -> bool:
    data = _load_token(path)
    rt = data.get('refresh_token')
    cid = data.get('client_id') or os.getenv('ML_CLIENT_ID') or os.getenv('MELI_CLIENT_ID')
    cs = data.get('client_secret') or os.getenv('ML_CLIENT_SECRET') or os.getenv('MELI_CLIENT_SECRET')
    if not (rt and cid and cs):
        return False
    try:
        resp = requests.post(
            f"{API_BASE}/oauth/token",
            data={
                'grant_type': 'refresh_token',
                'client_id': cid,
                'client_secret': cs,
                'refresh_token': rt,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            return False
        td = resp.json()
        data['access_token'] = td.get('access_token', data.get('access_token', ''))
        if 'refresh_token' in td:
            data['refresh_token'] = td.get('refresh_token')
        _save_token(path, data)
        return True
    except Exception:
        return False


def _get_access_token_for_seller(seller_id: Optional[str|int]) -> tuple[Optional[str], Optional[str]]:
    path = _find_token_for_seller(seller_id)
    if not path:
        return None, None
    tok = _load_token(path).get('access_token')
    if not tok:
        return None, path
    return tok, path


def _fetch_current_notes_with_ids(order_id: str, token: str) -> tuple[str, Optional[str]]:
    """
    Retorna (texto_concatenado, note_id_con_appmati)
    Si encuentra una nota con [APPMATI:], retorna su ID para editarla.
    """
    url = f"{API_BASE}/orders/{order_id}/notes"
    try:
        r = requests.get(url, headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }, params={"role": "seller"}, timeout=20)
        if r.status_code != 200:
            return '', None
        data = r.json()
        
        # Normalizar a lista de notas
        notes_list: list[dict] = []
        if isinstance(data, list):
            for it in data:
                if isinstance(it, dict):
                    if 'results' in it and isinstance(it.get('results'), list):
                        notes_list.extend([x for x in it['results'] if isinstance(x, dict)])
                    else:
                        notes_list.append(it)
        elif isinstance(data, dict):
            if 'results' in data and isinstance(data['results'], list):
                notes_list.extend([x for x in data['results'] if isinstance(x, dict)])
            else:
                notes_list.append(data)
        
        texts: list[str] = []
        appmati_note_id = None
        
        for n in notes_list:
            t = (n.get('note') or n.get('text') or n.get('plain_text') or '').strip()
            if t:
                texts.append(t)
                # Buscar nota con [APPMATI:] para editarla
                if API_BLOCK_RE.search(t) and not appmati_note_id:
                    appmati_note_id = n.get('id')
        
        return ' | '.join(texts), appmati_note_id
    except Exception:
        return '', None


def _fetch_current_notes_text(order_id: str, token: str) -> str:
    """Función legacy que mantiene compatibilidad"""
    text, _ = _fetch_current_notes_with_ids(order_id, token)
    return text


API_BLOCK_RE = re.compile(r"\[APPMATI:.*?\]", re.IGNORECASE)
STOCK_TAG_RE = re.compile(r"\[STOCK\s*-\s*\d+\s+MOV\s+\d+\]", re.IGNORECASE)


def _build_api_block(deposito: str, qty: int, agotado: bool, observacion: str) -> str:
    ag = 'SI' if agotado else 'NO'
    clean_obs = (observacion or '').strip()
    # Mostrar 'DEPOSITO' en lugar de 'DEP' solo para el texto de la nota ML
    dep_print = 'DEPOSITO' if str(deposito or '').strip().upper() == 'DEP' else deposito
    return f"[APPMATI: {dep_print} qty={qty} agotado={ag} | {clean_obs}]"


def _merge_notes(existing: str, api_block: str, stock_tag: Optional[str]) -> str:
    """
    - Reemplaza cualquier bloque previo [APPMATI: ...] por el nuevo
    - Asegura presencia de stock_tag (si viene). Evita duplicados
    - Devuelve nota final compacta
    """
    base = existing or ''
    base = API_BLOCK_RE.sub('', base).strip()
    parts: list[str] = []
    if api_block:
        parts.append(api_block)
    if base:
        parts.append(base)
    final = ' '.join(part for part in parts if part).strip()
    if stock_tag:
        if not STOCK_TAG_RE.search(final):
            if final:
                final = f"{final} {stock_tag}"
            else:
                final = stock_tag
    return final[:2000]  # límite prudente


def publish_note_upsert(
    *,
    order_id: str,
    seller_id: Optional[str|int],
    deposito_asignado: str,
    qty: int,
    agotado: bool,
    observacion_mov: str,
    numero_mov: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, str|bool]:
    """
    Publica nota idempotente en la orden.
    Retorna {'ok': bool, 'status': int, 'error': str}
    """
    token, path = _get_access_token_for_seller(seller_id)
    if not path and not dry_run:
        return {'ok': False, 'status': 0, 'error': 'no_token_path'}

    def _do_post(tok: str, text: str) -> requests.Response:
        url = f"{API_BASE}/orders/{order_id}/notes"
        return requests.post(url, headers={
            'Authorization': f'Bearer {tok}',
            'Content-Type': 'application/json'
        }, json={'note': text}, timeout=20)
    
    def _do_put(tok: str, text: str, note_id: str) -> requests.Response:
        url = f"{API_BASE}/orders/{order_id}/notes/{note_id}"
        return requests.put(url, headers={
            'Authorization': f'Bearer {tok}',
            'Content-Type': 'application/json'
        }, json={'note': text}, timeout=20)

    # Construir texto
    api_block = _build_api_block(deposito_asignado, int(qty or 0), bool(agotado), observacion_mov)
    stock_tag = None
    if numero_mov is not None and int(qty or 0) > 0:
        stock_tag = f"[STOCK -{int(qty)} MOV {int(numero_mov)}]"

    # Obtener existentes y buscar nota APPMATI para editar
    if dry_run:
        existing = ''
        appmati_note_id = None
    else:
        if token:
            existing, appmati_note_id = _fetch_current_notes_with_ids(order_id, token)
        else:
            existing = ''
            appmati_note_id = None

    final_text = _merge_notes(existing, api_block, stock_tag)

    if dry_run:
        return {'ok': True, 'status': 0, 'error': '', 'note': final_text}

    # Decidir si editar nota existente o crear nueva
    tok = token or ''
    if appmati_note_id:
        # Editar nota existente con [APPMATI:]
        resp = _do_put(tok, final_text, appmati_note_id)
        # Si 401 -> refresh y reintento único
        if resp.status_code == 401 and path and _refresh_token_inplace(path):
            tok2 = _load_token(path).get('access_token', '')
            resp = _do_put(tok2, final_text, appmati_note_id)
    else:
        # Crear nueva nota
        resp = _do_post(tok, final_text)
        # Si 401 -> refresh y reintento único
        if resp.status_code == 401 and path and _refresh_token_inplace(path):
            tok2 = _load_token(path).get('access_token', '')
            resp = _do_post(tok2, final_text)

    ok = resp.status_code in (200, 201)
    err = '' if ok else (resp.text[:300] if resp is not None else 'unknown_error')
    # Siempre incluir el texto final para que el caller pueda persistirlo
    return {'ok': ok, 'status': resp.status_code, 'error': err, 'note': final_text}
