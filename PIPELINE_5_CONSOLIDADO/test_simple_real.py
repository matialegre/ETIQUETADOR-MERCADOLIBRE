"""
TEST SIMPLE CON ÓRDENES REALES
==============================

Prueba simple para obtener órdenes reales sin complicaciones.
"""

import sys
import os

# Agregar path
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')

def test_simple_real():
    """Test simple con cliente real."""
    
    print("🔥 TEST SIMPLE CON ÓRDENES REALES")
    print("=" * 50)
    
    try:
        # Importar cliente real
        from meli_client_01 import MeliClient
        
        print("✅ Cliente importado correctamente")
        
        # Crear cliente
        client = MeliClient()
        print("✅ Cliente creado")
        
        # Obtener órdenes con timeout corto
        print("🔄 Obteniendo órdenes reales...")
        
        orders = client.get_recent_orders(limit=5)
        
        print(f"✅ ÉXITO: {len(orders)} órdenes obtenidas")
        
        # Mostrar órdenes
        for i, order in enumerate(orders, 1):
            order_id = order.get('id', 'unknown')
            status = order.get('status', 'unknown')
            substatus = order.get('substatus', 'unknown')
            
            print(f"   {i}. {order_id} - {status}/{substatus}")
            
            # Mostrar items
            items = order.get('order_items', [])
            for item in items:
                item_data = item.get('item', {})
                sku = item_data.get('seller_custom_field', 'sin_sku')
                qty = item.get('quantity', 0)
                print(f"      SKU: {sku} (qty: {qty})")
        
        return orders
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    orders = test_simple_real()
    if orders:
        print(f"\n🎉 TEST EXITOSO: {len(orders)} órdenes reales obtenidas")
    else:
        print(f"\n❌ TEST FALLÓ")
