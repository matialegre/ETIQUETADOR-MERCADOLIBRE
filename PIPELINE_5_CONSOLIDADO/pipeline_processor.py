"""
PROCESADOR DE PIPELINE PARA ÓRDENES REALES
==========================================

Procesa órdenes reales de MercadoLibre e inserta/actualiza en la base de datos.
"""

import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Agregar paths
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')

def process_orders_batch(orders: list, meli_client=None) -> dict:
    """
    Procesa un lote de órdenes reales con estados de shipping y multiventas.
    
    Args:
        orders: Lista de órdenes de MercadoLibre
        meli_client: Cliente MercadoLibre para consultas adicionales
        
    Returns:
        Dict con estadísticas del procesamiento
    """
    
    result = {
        'total_processed': 0,
        'new_orders': 0,
        'updated_orders': 0,
        'ready_orders': 0,
        'assigned_orders': 0,
        'errors': []
    }
    
    try:
        # Importar módulos necesarios
        from database_utils import insert_or_update_order
        from order_processor import extract_order_data

        # Config de paralelismo y rate limit
        try:
            max_workers = int(os.getenv('MAX_WORKERS_ENRICH', '8'))
        except Exception:
            max_workers = 8
        try:
            qps = float(os.getenv('RATE_LIMIT_QPS', '5'))  # llamadas/seg al API ML por cuenta
            if qps <= 0:
                qps = 5.0
        except Exception:
            qps = 5.0

        # Wrapper simple para rate-limitar métodos del cliente ML
        def _wrap_rate_limited_client(cli):
            if not cli:
                return None
            lock = threading.Lock()
            last_call = {'t': 0.0}
            min_interval = 1.0 / qps

            def _sleep_if_needed():
                with lock:
                    now = time.monotonic()
                    delta = now - last_call['t']
                    if delta < min_interval:
                        time.sleep(min_interval - delta)
                    last_call['t'] = time.monotonic()

            class _RateLimited:
                def __init__(self, inner):
                    self._inner = inner
                    # Propagar atributos comunes (p.ej. user_id)
                    for k in dir(inner):
                        if k.startswith('_'):
                            continue
                        try:
                            setattr(self, k, getattr(inner, k))
                        except Exception:
                            pass

                def get_shipping_details(self, *a, **kw):
                    _sleep_if_needed()
                    return self._inner.get_shipping_details(*a, **kw)

                def get_item(self, *a, **kw):
                    _sleep_if_needed()
                    return self._inner.get_item(*a, **kw)

                def get_item_details(self, *a, **kw):
                    _sleep_if_needed()
                    return self._inner.get_item_details(*a, **kw)

                def get_pack_details(self, *a, **kw):
                    _sleep_if_needed()
                    return self._inner.get_pack_details(*a, **kw)

            return _RateLimited(cli)

        rl_client = _wrap_rate_limited_client(meli_client)
        
        print(f"🔄 Procesando {len(orders)} órdenes con estados reales...")
        if meli_client:
            print(f"✅ Cliente MercadoLibre disponible para consultas de shipping y multiventas")
        else:
            print(f"⚠️ Sin cliente MercadoLibre - usando datos básicos")
        
        # Worker por orden
        def _process_one(idx_order_tuple):
            idx, order = idx_order_tuple
            order_id = order.get('id', 'unknown')
            print(f"\n🔍 Procesando orden {idx}/{len(orders)}: {order_id}")
            order_data = extract_order_data(order, rl_client)
            if not order_data:
                print("   ⚠️  No se pudieron extraer datos")
                return ('error', order_id, 'extract_failed', None)
            action = insert_or_update_order(order_data)
            return (action, order_id, order_data.get('shipping_subestado'), order_data)

        # Ejecutar en paralelo con límite de workers
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = [ex.submit(_process_one, (i, o)) for i, o in enumerate(orders, 1)]
            for fut in as_completed(futures):
                try:
                    action, order_id, subest, od = fut.result()
                    if action == 'inserted':
                        result['new_orders'] += 1
                        print("   ✅ Nueva orden insertada")
                    elif action == 'updated':
                        result['updated_orders'] += 1
                        print("   🔄 Orden actualizada")
                    elif action == 'error':
                        result['errors'].append(f"Orden {order_id}: error worker")
                    if od and (od.get('shipping_subestado') == 'ready_to_print'):
                        result['ready_orders'] += 1
                    result['total_processed'] += 1
                except Exception as e:
                    msg = f"Error en futuro de orden: {e}"
                    print(f"   ❌ {msg}")
                    result['errors'].append(msg)
        
        print(f"\n✅ Procesamiento completado:")
        print(f"   Total: {result['total_processed']}")
        print(f"   Nuevas: {result['new_orders']}")
        print(f"   Actualizadas: {result['updated_orders']}")
        print(f"   Ready: {result['ready_orders']}")
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR en procesamiento: {e}")
        result['errors'].append(str(e))
        return result
