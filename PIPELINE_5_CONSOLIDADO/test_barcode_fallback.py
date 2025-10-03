"""
🔍 TEST BARCODE SEARCH WITH FALLBACK
===================================

Script para probar la nueva lógica de búsqueda de barcode con fallback
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import con manejo de errores
try:
    from modules import dragon_db_02 as dragon_db
except ImportError:
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'modules'))
    import dragon_db_02 as dragon_db
from meli_client_01 import MeliClient

def test_barcode_fallback():
    """Probar la búsqueda de barcode con fallback usando datos reales"""
    
    print("🔍 TEST BARCODE SEARCH WITH FALLBACK")
    print("=" * 50)
    
    try:
        # Obtener una orden real para probar
        client = MeliClient()
        orders = client.get_recent_orders(limit=5)
        
        if not orders:
            print("❌ No se pudieron obtener órdenes")
            return
        
        print(f"✅ {len(orders)} órdenes obtenidas para testing")
        print()
        
        for i, order in enumerate(orders, 1):
            order_id = order.get('id')
            order_items = order.get('order_items', [])
            
            if not order_items:
                continue
                
            first_item = order_items[0]
            item_data = first_item.get('item', {})
            
            # Extraer ambos SKUs
            seller_custom_field = item_data.get('seller_custom_field')
            seller_sku = item_data.get('seller_sku')
            
            print(f"🔍 ORDEN {i}: {order_id}")
            print(f"   📊 seller_custom_field: {seller_custom_field}")
            print(f"   📊 seller_sku: {seller_sku}")
            
            # Probar la búsqueda con fallback
            barcode = dragon_db.get_barcode_with_fallback(seller_custom_field, seller_sku)
            
            if barcode:
                print(f"   ✅ BARCODE ENCONTRADO: {barcode}")
            else:
                print(f"   ❌ BARCODE NO ENCONTRADO")
            
            print("-" * 50)
        
        print("\n🎯 TEST COMPLETADO")
        
    except Exception as e:
        print(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_barcode_fallback()
