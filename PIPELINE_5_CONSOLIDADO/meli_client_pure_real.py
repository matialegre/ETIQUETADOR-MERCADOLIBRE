"""
CLIENTE MERCADOLIBRE 100% REAL
==============================

Cliente puro sin mock ni datos de test.
Solo órdenes reales de MercadoLibre.
"""

import sys
import os

# Agregar path al módulo real
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')

def get_recent_orders_pure_real(limit: int = 20) -> list:
    """
    Obtiene órdenes reales de MercadoLibre sin ningún mock.
    
    Args:
        limit: Número máximo de órdenes a obtener
        
    Returns:
        Lista de órdenes reales de MercadoLibre
    """
    
    try:
        print(f"🔥 OBTENIENDO {limit} ÓRDENES REALES DE MERCADOLIBRE")
        print("=" * 60)
        
        # Importar el cliente real original
        from meli_client_01 import MeliClient
        
        # Crear cliente
        client = MeliClient()
        print("✅ Cliente MercadoLibre inicializado")
        
        # Obtener órdenes reales con paginación (limit por request <= 51)
        print(f"🔄 Consultando últimas {limit} órdenes con paginación...")
        collected = []
        offset = 0
        per_page = 51
        while len(collected) < limit:
            remaining = limit - len(collected)
            page_size = remaining if remaining < per_page else per_page
            page = client.get_recent_orders(limit=page_size, offset=offset)
            if not page:
                break
            collected.extend(page)
            offset += len(page)
            # Si la API devolvió menos que page_size, no hay más páginas
            if len(page) < page_size:
                break
        
        print(f"✅ {len(collected)} órdenes reales obtenidas")
        
        # Mostrar resumen
        for i, order in enumerate(collected, 1):
            order_id = order.get('id', 'unknown')
            status = order.get('status', 'unknown')
            substatus = order.get('substatus', 'unknown')
            print(f"   {i}. {order_id} - {status}/{substatus}")
        
        return collected
        
    except Exception as e:
        print(f"❌ ERROR obteniendo órdenes reales: {e}")
        return []

if __name__ == "__main__":
    # Test directo
    orders = get_recent_orders_pure_real(limit=10)
    print(f"\n🎯 RESULTADO: {len(orders)} órdenes reales obtenidas")
