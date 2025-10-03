from __future__ import annotations
"""
Backfill rápido de NOTAS para la última venta (o todas si se desea).
- Toma el último order_id por date_created
- Llama a /orders/{id}/notes (role=seller)
- Persiste en orders_meli.nota

Uso:
  python backfill_notes_once.py               # actualiza solo la última venta
  python backfill_notes_once.py --all N       # actualiza las últimas N ventas
  python backfill_notes_once.py --order <id>  # actualiza una orden específica
"""
import argparse
import os
import json
import requests
import pyodbc
from datetime import datetime

CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'

# Defaults alineados con la GUI (daemon app)
DEFAULT_CLIENT_ID = "5057564940459485"
DEFAULT_CLIENT_SECRET = "NM0wSta1bSNSt4CxSEOeSwRC2p9eHQD7"


TOKEN_PATH_OVERRIDE: str = ''
DEBUG: bool = False


def _token_paths() -> list[str]:
    paths: list[str] = []
    # 0) CLI override
    if TOKEN_PATH_OVERRIDE:
        paths.append(TOKEN_PATH_OVERRIDE)
    # 1) Env override
    tp_env = os.getenv('TOKEN_PATH')
    if tp_env:
        paths.append(tp_env)
    # 2) Proyecto config/token.json
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    paths.append(os.path.join(proj_root, 'config', 'token.json'))
    # 3) Legacy GUI token (detectado en el código antiguo)
    paths.append(r'C:\Users\Mundo Outdoor\Desktop\Develop_Mati\Escritor Meli\token.json')
    return paths


def _load_token_file() -> tuple[str, dict] | tuple[None, dict]:
    for p in _token_paths():
        try:
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data.get('access_token'):
                    return p, data
        except Exception:
            pass
    return None, {}


def _get_access_token() -> str:
    p, data = _load_token_file()
    return data.get('access_token', '')


def _refresh_token_inplace() -> bool:
    token_path, data = _load_token_file()
    if not token_path:
        print('[auth] No se encontró token.json para refrescar (ni env TOKEN_PATH)')
        return False
    try:
        rt = data.get('refresh_token')
        cid = data.get('client_id') or os.getenv('ML_CLIENT_ID') or DEFAULT_CLIENT_ID
        cs = data.get('client_secret') or os.getenv('ML_CLIENT_SECRET') or DEFAULT_CLIENT_SECRET
        if not (rt and cid and cs):
            print('[auth] Faltan credenciales para refresh_token')
            return False
        resp = requests.post(
            'https://api.mercadolibre.com/oauth/token',
            data={'grant_type': 'refresh_token', 'client_id': cid, 'client_secret': cs, 'refresh_token': rt},
            timeout=20
        )
        if resp.status_code != 200:
            print(f"[auth] Refresh falló {resp.status_code}: {resp.text[:200]}")
            return False
        td = resp.json()
        data['access_token'] = td.get('access_token', data.get('access_token', ''))
        if 'refresh_token' in td:
            data['refresh_token'] = td.get('refresh_token')
        with open(token_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print('[auth] Token refrescado y guardado en config/token.json')
        return True
    except Exception as e:
        print(f"[auth] Excepción refrescando token: {e}")
        return False


def _fetch_notes(order_id: str) -> str:
    tok = _get_access_token()
    if not tok:
        return ''
    url = f"https://api.mercadolibre.com/orders/{order_id}/notes"
    try:
        resp = requests.get(url, headers={
            'Authorization': f'Bearer {tok}',
            'Content-Type': 'application/json'
        }, params={"role": "seller"}, timeout=20)
        if resp.status_code == 401:
            # intentar refresh y reintento único
            if _refresh_token_inplace():
                tok2 = _get_access_token()
                resp = requests.get(url, headers={
                    'Authorization': f'Bearer {tok2}',
                    'Content-Type': 'application/json'
                }, params={"role": "seller"}, timeout=20)
        if DEBUG:
            print(f"[notes] {order_id} status={resp.status_code} body={resp.text[:400]}")
        if resp.status_code != 200:
            return ''
        data = resp.json()
        # Normalizar a lista de notas
        notes_list: list[dict] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if 'results' in item:
                        res = item.get('results')
                        if isinstance(res, list):
                            notes_list.extend([r for r in res if isinstance(r, dict)])
                        elif isinstance(res, dict):
                            notes_list.append(res)
                    else:
                        notes_list.append(item)
        elif isinstance(data, dict):
            if 'results' in data:
                res = data.get('results')
                if isinstance(res, list):
                    notes_list.extend([r for r in res if isinstance(r, dict)])
                elif isinstance(res, dict):
                    notes_list.append(res)
            else:
                notes_list.append(data)
        # Extraer textos
        texts: list[str] = []
        for n in notes_list:
            t = (n.get('note') or n.get('text') or n.get('plain_text') or '').strip()
            if t:
                texts.append(t)
        return ' | '.join(texts)
    except Exception:
        return ''


def _fetch_messages_from_pack(order_id: str) -> str:
    """Obtiene el último mensaje del pack (conversaciones ML) y devuelve el texto.
    - /orders/{id} -> pack_id
    - /users/me -> seller_id (si no está en token)
    - /messages/packs/{pack_id}/sellers/{seller_id}
    """
    tok = _get_access_token()
    if not tok:
        return ''
    # 1) Order -> pack
    o_url = f"https://api.mercadolibre.com/orders/{order_id}"
    try:
        o_resp = requests.get(o_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if o_resp.status_code == 401 and _refresh_token_inplace():
            tok = _get_access_token()
            o_resp = requests.get(o_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if DEBUG:
            print(f"[order.pack] {order_id} status={o_resp.status_code} body={o_resp.text[:400]}")
        if o_resp.status_code != 200:
            return ''
        o_js = o_resp.json()
        pack_id = o_js.get('pack_id')
        if not pack_id:
            return ''
        # 2) users/me -> seller_id
        me_url = "https://api.mercadolibre.com/users/me"
        me_resp = requests.get(me_url, headers={'Authorization': f'Bearer {tok}'}, timeout=15)
        if DEBUG:
            print(f"[users.me] status={me_resp.status_code} body={me_resp.text[:200]}")
        if me_resp.status_code != 200:
            return ''
        seller_id = me_resp.json().get('id')
        if not seller_id:
            return ''
        # 3) messages by pack & seller
        msg_url = f"https://api.mercadolibre.com/messages/packs/{pack_id}/sellers/{seller_id}"
        msg_resp = requests.get(msg_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if DEBUG:
            print(f"[messages] pack={pack_id} status={msg_resp.status_code} body={msg_resp.text[:400]}")
        if msg_resp.status_code != 200:
            return ''
        mjs = msg_resp.json()
        texts: list[str] = []
        # Intentar formatos comunes
        if isinstance(mjs, dict):
            # Algunas versiones traen 'messages' o 'results'
            arr = None
            if 'messages' in mjs and isinstance(mjs['messages'], list):
                arr = mjs['messages']
            elif 'results' in mjs and isinstance(mjs['results'], list):
                arr = mjs['results']
            if arr:
                for it in arr:
                    if isinstance(it, dict):
                        t = (it.get('text') or it.get('plain') or it.get('message') or '').strip()
                        if not t and isinstance(it.get('message'), dict):
                            t = (it['message'].get('text') or it['message'].get('plain') or '').strip()
                        if t:
                            texts.append(t)
        # Devolver el último no vacío
        for t in reversed(texts):
            if t:
                return t
        # O concatenar si no hay orden
        return ' | '.join(texts)
    except Exception:
        return ''

def _fetch_comments_fallback(order_id: str) -> str:
    tok = _get_access_token()
    if not tok:
        return ''
    url = f"https://api.mercadolibre.com/orders/{order_id}"
    try:
        resp = requests.get(url, headers={
            'Authorization': f'Bearer {tok}',
            'Content-Type': 'application/json'
        }, timeout=20)
        if resp.status_code == 401:
            if _refresh_token_inplace():
                tok2 = _get_access_token()
                resp = requests.get(url, headers={
                    'Authorization': f'Bearer {tok2}',
                    'Content-Type': 'application/json'
                }, timeout=20)
        if DEBUG:
            print(f"[order] {order_id} status={resp.status_code} body={resp.text[:400]}")
        if resp.status_code != 200:
            return ''
        data = resp.json()
        comments = data.get('comments') or ''
        return comments if isinstance(comments, str) else ''
    except Exception:
        return ''


def _fetch_merchant_comments_from_pack(order_id: str) -> str:
    """Obtiene comentarios desde merchant_orders usando pack_id de la orden.
    - /orders/{id} -> pack_id
    - /merchant_orders/search?pack_id={pack_id} -> results[].comments
    """
    tok = _get_access_token()
    if not tok:
        return ''
    # 1) Obtener pack_id desde la orden
    o_url = f"https://api.mercadolibre.com/orders/{order_id}"
    try:
        o_resp = requests.get(o_url, headers={
            'Authorization': f'Bearer {tok}',
            'Content-Type': 'application/json'
        }, timeout=20)
        if o_resp.status_code == 401:
            if _refresh_token_inplace():
                tok2 = _get_access_token()
                o_resp = requests.get(o_url, headers={
                    'Authorization': f'Bearer {tok2}',
                    'Content-Type': 'application/json'
                }, timeout=20)
        if DEBUG:
            print(f"[order.pack] {order_id} status={o_resp.status_code} body={o_resp.text[:400]}")
        if o_resp.status_code != 200:
            return ''
        o_js = o_resp.json()
        pack_id = o_js.get('pack_id') or o_js.get('pack_id', None)
        if not pack_id:
            return ''
        # 2) Buscar merchant_orders por pack_id
        m_url = f"https://api.mercadolibre.com/merchant_orders/search?pack_id={pack_id}"
        m_resp = requests.get(m_url, headers={
            'Authorization': f'Bearer {tok}',
            'Content-Type': 'application/json'
        }, timeout=20)
        if m_resp.status_code == 401:
            if _refresh_token_inplace():
                tok2 = _get_access_token()
                m_resp = requests.get(m_url, headers={
                    'Authorization': f'Bearer {tok2}',
                    'Content-Type': 'application/json'
                }, timeout=20)
        if DEBUG:
            print(f"[merchant_orders] pack={pack_id} status={m_resp.status_code} body={m_resp.text[:400]}")
        if m_resp.status_code != 200:
            return ''
        m_js = m_resp.json() or {}
        results = m_js.get('results') if isinstance(m_js, dict) else None
        texts: list[str] = []
        if isinstance(results, list):
            for it in results:
                if isinstance(it, dict):
                    comm = it.get('comments')
                    if isinstance(comm, str) and comm:
                        texts.append(comm)
        return ' | '.join(texts)
    except Exception:
        return ''


essql_last = (
    "SELECT TOP 1 order_id FROM orders_meli ORDER BY date_created DESC"
)

essql_last_n = (
    "SELECT TOP (?) order_id FROM orders_meli ORDER BY date_created DESC"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', type=int, default=0, help='Actualizar las últimas N ventas (0=solo la última)')
    ap.add_argument('--order', type=str, default='', help='Actualizar una orden específica por order_id')
    ap.add_argument('--token-path', type=str, default='', help='Ruta a token.json para usar en esta ejecución')
    ap.add_argument('--debug', action='store_true', help='Loguear respuestas crudas de ML (para diagnóstico)')
    args = ap.parse_args()

    global TOKEN_PATH_OVERRIDE
    TOKEN_PATH_OVERRIDE = args.token_path.strip()
    global DEBUG
    DEBUG = bool(args.debug)

    with pyodbc.connect(CONN_STR) as cn:
        cur = cn.cursor()
        if args.order:
            ids = [args.order]
        elif args.all and args.all > 0:
            cur.execute(essql_last_n, (args.all,))
            ids = [str(r[0]) for r in cur.fetchall()]
        else:
            cur.execute(essql_last)
            row = cur.fetchone()
            if not row:
                print('No hay órdenes en la base')
                return 0
            ids = [str(row[0])]

        print(f"Procesando {len(ids)} órdenes…")
        updated = 0
        for oid in ids:
            nota = _fetch_notes(oid)
            if not nota:
                nota = _fetch_comments_fallback(oid)
            if not nota:
                nota = _fetch_merchant_comments_from_pack(oid)
            if not nota:
                nota = _fetch_messages_from_pack(oid)
            cur.execute("UPDATE orders_meli SET nota = ?, fecha_actualizacion = GETDATE() WHERE order_id = ?", (nota, oid))
            cn.commit()
            print(f"{oid}: nota_len={len(nota)}")
            updated += 1

        print(f"Listo: {updated} actualizadas a {datetime.now().isoformat()}")
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
