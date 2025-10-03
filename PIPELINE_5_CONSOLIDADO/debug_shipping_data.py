"""
🔍 DEBUG SHIPPING DATA
====================

Script para investigar qué datos de shipping reales trae MercadoLibre
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from meli_client_01 import MeliClient
import json
from datetime import datetime

def debug_shipping_data():
    """Investigar datos de shipping de una orden específica"""
    
    print("🔍 DEBUG SHIPPING DATA - Investigando datos reales de MercadoLibre")
    print("=" * 70)
    
    try:
        # Inicializar cliente
        client = MeliClient()
        print("✅ Cliente MercadoLibre inicializado")
        
        # Obtener una orden reciente
        orders = client.get_recent_orders(limit=1)
        if not orders:
            print("❌ No se pudieron obtener órdenes")
            return
        
        order = orders[0]
        order_id = order.get('id')
        
        print(f"\n🎯 ANALIZANDO ORDEN: {order_id}")
        print("-" * 50)
        
        # Mostrar estructura completa de la orden
        print("📋 ESTRUCTURA COMPLETA DE LA ORDEN:")
        print(json.dumps(order, indent=2, ensure_ascii=False))
        
        print("\n" + "="*70)
        
        # Extraer campos específicos que buscamos
        print("🔍 CAMPOS ESPECÍFICOS DE SHIPPING:")
        print("-" * 40)
        
        # Status y substatus generales
        status = order.get('status')
        substatus = order.get('substatus')
        print(f"📊 Status general: {status}")
        print(f"📊 Substatus general: {substatus}")
        
        # Tags
        tags = order.get('tags', [])
        print(f"🏷️ Tags: {tags}")
        
        # Datos de shipping
        shipping = order.get('shipping', {})
        print(f"📦 Shipping completo: {json.dumps(shipping, indent=2, ensure_ascii=False)}")
        
        if shipping:
            shipping_status = shipping.get('status')
            shipping_substatus = shipping.get('substatus')
            shipping_tags = shipping.get('tags', [])
            
            print(f"📦 Shipping status: {shipping_status}")
            print(f"📦 Shipping substatus: {shipping_substatus}")
            print(f"📦 Shipping tags: {shipping_tags}")
        
        # Buscar en otros lugares posibles
        print("\n🔍 BUSCANDO EN OTROS CAMPOS:")
        print("-" * 40)
        
        # Order items
        order_items = order.get('order_items', [])
        if order_items:
            first_item = order_items[0]
            print(f"📦 Primer item: {json.dumps(first_item, indent=2, ensure_ascii=False)}")
        
        # Payments
        payments = order.get('payments', [])
        if payments:
            print(f"💳 Payments: {json.dumps(payments, indent=2, ensure_ascii=False)}")
        
        print("\n" + "="*70)
        print("🎯 ANÁLISIS COMPLETADO")
        
    except Exception as e:
        print(f"❌ Error en debug: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_shipping_data()
