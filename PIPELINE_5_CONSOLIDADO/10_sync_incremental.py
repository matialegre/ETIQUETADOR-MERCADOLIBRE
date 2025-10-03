"""
PASO 10: Sync Incremental - PIPELINE 4
======================================

Sincronización incremental de estados con MercadoLibre.
Actualiza órdenes asignadas con cambios de estado/subestado/shipping/notas.

Extensiones:
- Trae las notas reales desde /orders/{id}/notes y las persiste en columna 'nota'.
- Si una orden asignada pasa a cancelada, revierte el movimiento WOO→WOO (Tipo inverso),
  pone deposito_asignado='CANCELADO' y resetea flags operativos (asignado_flag, ready_to_print, printed).
"""

import logging
import os
import json
import importlib.util
import requests
import sys
import pyodbc
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Config
def _mov_tipo_default() -> int:
    try:
        return int(os.getenv('MOV_TIPO_DEFAULT', '2'))
    except Exception:
        return 2

logger = logging.getLogger(__name__)

DEFAULT_CLIENT_ID = "5057564940459485"
DEFAULT_CLIENT_SECRET = "NM0wSta1bSNSt4CxSEOeSwRC2p9eHQD7"


def _token_paths() -> list[str]:
    paths: list[str] = []
    tp_env = os.getenv('TOKEN_PATH')
    if tp_env:
        paths.append(tp_env)
    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    paths.append(os.path.join(proj_root, 'config', 'token.json'))
    # Legacy GUI path como último recurso
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
        return False
    try:
        rt = data.get('refresh_token')
        cid = data.get('client_id') or os.getenv('ML_CLIENT_ID') or DEFAULT_CLIENT_ID
        cs = data.get('client_secret') or os.getenv('ML_CLIENT_SECRET') or DEFAULT_CLIENT_SECRET
        if not (rt and cid and cs):
            return False
        resp = requests.post(
            'https://api.mercadolibre.com/oauth/token',
            data={'grant_type': 'refresh_token', 'client_id': cid, 'client_secret': cs, 'refresh_token': rt},
            timeout=20
        )
        if resp.status_code != 200:
            return False
        td = resp.json()
        data['access_token'] = td.get('access_token', data.get('access_token', ''))
        if 'refresh_token' in td:
            data['refresh_token'] = td.get('refresh_token')
        with open(token_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
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
        if resp.status_code == 401 and _refresh_token_inplace():
            tok = _get_access_token()
            resp = requests.get(url, headers={'Authorization': f'Bearer {tok}'}, params={"role": "seller"}, timeout=20)
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
        texts: list[str] = []
        for n in notes_list:
            t = (n.get('note') or n.get('text') or n.get('plain_text') or '').strip()
            if t:
                texts.append(t)
        return ' | '.join(texts)
    except Exception:
        return ''


def _fetch_comments(order_id: str) -> str:
    tok = _get_access_token()
    if not tok:
        return ''
    url = f"https://api.mercadolibre.com/orders/{order_id}"
    try:
        resp = requests.get(url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if resp.status_code == 401 and _refresh_token_inplace():
            tok = _get_access_token()
            resp = requests.get(url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if resp.status_code != 200:
            return ''
        data = resp.json()
        return data.get('comments') or ''
    except Exception:
        return ''


def _fetch_merchant_comments_from_pack(order_id: str) -> str:
    tok = _get_access_token()
    if not tok:
        return ''
    # Orden -> pack
    o_url = f"https://api.mercadolibre.com/orders/{order_id}"
    try:
        o_resp = requests.get(o_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if o_resp.status_code == 401 and _refresh_token_inplace():
            tok = _get_access_token()
            o_resp = requests.get(o_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if o_resp.status_code != 200:
            return ''
        o_js = o_resp.json()
        pack_id = o_js.get('pack_id')
        if not pack_id:
            return ''
        # merchant_orders por pack
        m_url = f"https://api.mercadolibre.com/merchant_orders/search?pack_id={pack_id}"
        m_resp = requests.get(m_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if m_resp.status_code == 401 and _refresh_token_inplace():
            tok = _get_access_token()
            m_resp = requests.get(m_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
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


def _fetch_messages_from_pack(order_id: str) -> str:
    tok = _get_access_token()
    if not tok:
        return ''
    o_url = f"https://api.mercadolibre.com/orders/{order_id}"
    try:
        o_resp = requests.get(o_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if o_resp.status_code == 401 and _refresh_token_inplace():
            tok = _get_access_token()
            o_resp = requests.get(o_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if o_resp.status_code != 200:
            return ''
        pack_id = o_resp.json().get('pack_id')
        if not pack_id:
            return ''
        me = requests.get('https://api.mercadolibre.com/users/me', headers={'Authorization': f'Bearer {tok}'}, timeout=15)
        if me.status_code != 200:
            return ''
        seller_id = me.json().get('id')
        if not seller_id:
            return ''
        msg_url = f"https://api.mercadolibre.com/messages/packs/{pack_id}/sellers/{seller_id}"
        msg = requests.get(msg_url, headers={'Authorization': f'Bearer {tok}'}, timeout=20)
        if msg.status_code != 200:
            return ''
        mjs = msg.json()
        texts: list[str] = []
        if isinstance(mjs, dict):
            arr = mjs.get('messages') if isinstance(mjs.get('messages'), list) else mjs.get('results') if isinstance(mjs.get('results'), list) else None
            if arr:
                for it in arr:
                    if isinstance(it, dict):
                        t = (it.get('text') or it.get('plain') or it.get('message') or '').strip()
                        if not t and isinstance(it.get('message'), dict):
                            t = (it['message'].get('text') or it['message'].get('plain') or '').strip()
                        if t:
                            texts.append(t)
        for t in reversed(texts):
            if t:
                return t
        return ' | '.join(texts)
    except Exception:
        return ''


def _build_note_text(order_id: str) -> str:
    # 1) Notas del pedido
    nota = _fetch_notes(order_id)
    if nota:
        return nota
    # 2) comments del pedido
    nota = _fetch_comments(order_id)
    if nota:
        return nota
    # 3) comments desde merchant_orders por pack
    nota = _fetch_merchant_comments_from_pack(order_id)
    if nota:
        return nota
    # 4) mensajes del pack
    return _fetch_messages_from_pack(order_id)


def _load_move_func():
    """Carga dinámica de modules/09_dragon_movement.py y devuelve move_stock_woo_to_woo."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    path = os.path.join(base_dir, 'modules', '09_dragon_movement.py')
    spec = importlib.util.spec_from_file_location('modules.09_dragon_movement', path)
    if not spec or not spec.loader:
        raise ImportError('No se pudo cargar 09_dragon_movement.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return getattr(mod, 'move_stock_woo_to_woo')


def sync_status_changes() -> Dict:
    """
    Función principal de sincronización incremental.
    
    Lógica:
    1. Obtener órdenes recientes de MercadoLibre
    2. Para cada orden, verificar si existe en BD y está asignada
    3. Si existe y está asignada, actualizar estados/notas
    4. Si no existe, insertar nueva orden
    """
    try:
        logger.info("Iniciando sincronización incremental...")
        
        # 1. Obtener órdenes recientes de MercadoLibre
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        
        from meli_client import get_recent_orders
        
        nuevos = get_recent_orders(limit=2)  # Limitar a últimas 2 para validación
        logger.info(f"Órdenes obtenidas de MercadoLibre: {len(nuevos)}")
        
        updated_count = 0
        inserted_count = 0
        
        conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        
        # Notas se obtienen on-demand vía _build_note_text(order_id)
        
        # 2. Procesar cada orden
        for o in nuevos:
            try:
                order_id = o.get('id')
                if not order_id:
                    continue
                
                # Procesar items de la orden
                order_items = o.get('order_items', [])
                
                for it in order_items:
                    try:
                        # Extraer SKU del item
                        item_data = it.get('item', {})
                        sku = item_data.get('seller_custom_field', '')
                        
                        if not sku:
                            continue
                        
                        # Clave única: (order_id, sku)
                        key = (order_id, sku)
                        
                        # Buscar en BD
                        with pyodbc.connect(conn_str) as conn:
                            cursor = conn.cursor()
                            
                            cursor.execute("""
                                SELECT id, estado, subestado, shipping_estado, shipping_subestado,
                                       nota, asignado_flag, fecha_actualizacion,
                                       numero_movimiento, observacion_movimiento, movimiento_realizado,
                                       deposito_asignado, ready_to_print, printed, qty, barcode
                                FROM orders_meli
                                WHERE order_id = ? AND sku = ?
                            """, (key[0], key[1]))
                            
                            fila = cursor.fetchone()
                            
                            if fila:
                                # ORDEN EXISTE - Actualizar si está asignada
                                (db_id, current_estado, current_subestado, current_shipping_estado,
                                 current_shipping_subestado, current_nota, asignado_flag, fecha_actualizacion,
                                 numero_mov_anterior, obs_anterior, mov_realizado,
                                 depo_asignado, rtp, impreso, qty_db, barcode_db) = fila

                                if asignado_flag:
                                    # Extraer nuevos valores de MercadoLibre
                                    new_estado = o.get('status', '')
                                    new_subestado = o.get('substatus', '')
                                    
                                    shipping = o.get('shipping', {})
                                    new_shipping_estado = shipping.get('status', '')
                                    new_shipping_subestado = shipping.get('substatus', '')

                                    # Notas reales desde /orders/{id}/notes
                                    new_nota = _build_note_text(str(order_id))
                                    
                                    # Verificar si hay cambios
                                    changes = []
                                    if new_estado != current_estado:
                                        changes.append(f"estado: {current_estado} → {new_estado}")
                                    if new_subestado != current_subestado:
                                        changes.append(f"subestado: {current_subestado} → {new_subestado}")
                                    if new_shipping_estado != current_shipping_estado:
                                        changes.append(f"shipping_estado: {current_shipping_estado} → {new_shipping_estado}")
                                    if new_shipping_subestado != current_shipping_subestado:
                                        changes.append(f"shipping_subestado: {current_shipping_subestado} → {new_shipping_subestado}")
                                    if new_nota != current_nota:
                                        changes.append("nota actualizada")
                                    
                                    # Actualizar si hay cambios
                                    if changes:
                                        cursor.execute("BEGIN TRANSACTION")
                                        
                                        try:
                                            # Construir observación de cambios
                                            change_log = f"Sync ML ({datetime.now().strftime('%Y-%m-%d %H:%M')}): {'; '.join(changes)}"

                                            # Detectar cancelación
                                            became_cancelled = (
                                                (new_estado or '').lower() == 'cancelled' or
                                                (new_shipping_estado or '').lower() == 'cancelled'
                                            )

                                            if became_cancelled:
                                                # Reversa de movimiento: Tipo inverso
                                                tipo_inverso = 1 if int(_mov_tipo_default()) == 2 else 2
                                                obs_rev = f"REVERSA CANCEL ML | order_id={order_id} | sku={sku} | prev_num={numero_mov_anterior or ''}"
                                                try:
                                                    move_stock_woo_to_woo = _load_move_func()
                                                    mov_res = move_stock_woo_to_woo(
                                                        sku=sku,
                                                        qty=int(qty_db or it.get('quantity', 1) or 1),
                                                        observacion=obs_rev,
                                                        tipo=tipo_inverso,
                                                        barcode=barcode_db or it.get('item', {}).get('seller_sku') or None,
                                                    )
                                                except Exception as _e:
                                                    mov_res = {"ok": False, "status": 0, "error": str(_e), "numero": None}

                                                ok_rev = bool(mov_res.get('ok'))
                                                numero_rev = mov_res.get('numero')
                                                status_rev = mov_res.get('status')
                                                obs_concat = f"{obs_anterior or ''}; {change_log}; REVERSA status={status_rev} num={numero_rev}"

                                                cursor.execute("""
                                                    UPDATE orders_meli
                                                    SET estado = ?,
                                                        subestado = ?,
                                                        shipping_estado = ?,
                                                        shipping_subestado = ?,
                                                        nota = ?,
                                                        deposito_asignado = 'CANCELADO',
                                                        asignado_flag = 0,
                                                        ready_to_print = 0,
                                                        printed = 0,
                                                        movimiento_realizado = 1,
                                                        numero_movimiento = ?,
                                                        observacion_movimiento = ?,
                                                        fecha_actualizacion = GETDATE()
                                                    WHERE id = ?
                                                """, (
                                                    new_estado,
                                                    new_subestado,
                                                    new_shipping_estado,
                                                    new_shipping_subestado,
                                                    new_nota,
                                                    numero_rev,
                                                    obs_concat,
                                                    db_id,
                                                ))
                                            else:
                                                cursor.execute("""
                                                    UPDATE orders_meli 
                                                    SET estado = ?,
                                                        subestado = ?,
                                                        shipping_estado = ?,
                                                        shipping_subestado = ?,
                                                        nota = ?,
                                                        fecha_actualizacion = GETDATE(),
                                                        observacion_movimiento = CONCAT(
                                                            ISNULL(observacion_movimiento, ''), 
                                                            '; ', ?
                                                        )
                                                    WHERE id = ?
                                                """, (
                                                    new_estado,
                                                    new_subestado, 
                                                    new_shipping_estado,
                                                    new_shipping_subestado,
                                                    new_nota,
                                                    change_log,
                                                    db_id
                                                ))
                                            
                                            cursor.execute("COMMIT TRANSACTION")
                                            updated_count += 1
                                            
                                            logger.info(f"Actualizado {order_id}-{sku}: {'; '.join(changes)}")
                                            
                                        except Exception as e:
                                            cursor.execute("ROLLBACK TRANSACTION")
                                            logger.error(f"Error actualizando {order_id}-{sku}: {e}")
                                
                            else:
                                # ORDEN NO EXISTE - Insertar nueva con nota
                                try:
                                    new_estado = o.get('status', '')
                                    new_subestado = o.get('substatus', '')
                                    shipping = o.get('shipping', {})
                                    new_shipping_estado = shipping.get('status', '')
                                    new_shipping_subestado = shipping.get('substatus', '')
                                    qty_val = int(it.get('quantity', 1) or 1)
                                    # Nota real (con fallbacks)
                                    new_nota = _build_note_text(str(order_id))

                                    cursor.execute("""
                                        INSERT INTO orders_meli (
                                            order_id, sku, qty, estado, subestado,
                                            shipping_estado, shipping_subestado, nota,
                                            asignado_flag, ready_to_print, printed,
                                            movimiento_realizado, deposito_asignado,
                                            fecha_actualizacion
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, NULL, GETDATE())
                                    """, (
                                        order_id,
                                        sku,
                                        qty_val,
                                        new_estado,
                                        new_subestado,
                                        new_shipping_estado,
                                        new_shipping_subestado,
                                        new_nota,
                                    ))
                                    conn.commit()
                                    inserted_count += 1
                                    logger.info(f"Nueva orden insertada: {order_id}-{sku} (nota_len={len(new_nota or '')})")
                                except Exception as e:
                                    logger.error(f"Error insertando nueva orden {order_id}-{sku}: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error procesando item de orden {order_id}: {e}")
                        continue
            
            except Exception as e:
                logger.error(f"Error procesando orden {o.get('id', 'unknown')}: {e}")
                continue
        
        # Resultado final
        result = {
            'status': 'success',
            'updated': updated_count,
            'inserted': inserted_count,
            'total_processed': len(nuevos),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Sync completado: {updated_count} actualizadas, {inserted_count} insertadas")
        
        return result
        
    except Exception as e:
        logger.error(f"Error en sync_status_changes: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'updated': 0,
            'inserted': 0
        }

def get_orders_for_status_sync(days_back: int = 7) -> List[Dict]:
    """
    Obtiene órdenes asignadas de los últimos N días para sincronización.
    """
    try:
        conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT order_id, sku, estado, subestado, shipping_estado, 
                       shipping_subestado, asignado_flag, fecha_asignacion
                FROM orders_meli 
                WHERE asignado_flag = 1 
                AND fecha_asignacion >= DATEADD(day, -?, GETDATE())
                ORDER BY fecha_asignacion DESC
            """, (days_back,))
            
            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'order_id': row[0],
                    'sku': row[1],
                    'estado': row[2],
                    'subestado': row[3],
                    'shipping_estado': row[4],
                    'shipping_subestado': row[5],
                    'asignado_flag': row[6],
                    'fecha_asignacion': row[7]
                })
            
            return orders
            
    except Exception as e:
        logger.error(f"Error obteniendo órdenes para sync: {e}")
        return []

if __name__ == "__main__":
    # Test del sync incremental
    result = sync_status_changes()
    print(f"Resultado del sync: {result}")
