"""
PIPELINE 4 - SOLO ÓRDENES REALES
================================

Test del pipeline 4 usando únicamente órdenes reales de MercadoLibre.
Sin mock, sin datos de test, solo datos reales.
"""

import sys
import os
from datetime import datetime

# Agregar paths
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\PIPELINE_4_COMPLETO')

def test_pipeline_4_pure_real():
    """Test del pipeline 4 con órdenes 100% reales."""
    
    print("🔥 PIPELINE 4 - SOLO ÓRDENES REALES")
    print("=" * 60)
    
    try:
        # PASO 1: Obtener órdenes reales
        print("\n📥 PASO 1: Obteniendo órdenes reales de MercadoLibre...")
        print("-" * 50)
        
        from meli_client_pure_real import get_recent_orders_pure_real
        
        # Obtener 20 órdenes reales
        recent_orders = get_recent_orders_pure_real(limit=20)
        
        if not recent_orders:
            print("❌ No se pudieron obtener órdenes reales")
            return False
        
        print(f"✅ {len(recent_orders)} órdenes reales obtenidas")
        
        # PASO 2: Procesar órdenes CON ESTADOS REALES Y MULTIVENTAS
        print(f"\n🔄 PASO 2: Procesando {len(recent_orders)} órdenes con estados reales...")
        print("-" * 50)
        
        # Importar módulos necesarios
        from pipeline_processor import process_orders_batch
        from meli_client_01 import MeliClient
        
        # 🔥 CREAR CLIENTE MERCADOLIBRE PARA CONSULTAS ADICIONALES
        print("🚀 Inicializando cliente MercadoLibre para consultas de shipping y multiventas...")
        meli_client = MeliClient()
        
        # 🔥 PROCESAR TODAS LAS ÓRDENES CON CLIENTE MERCADOLIBRE
        result = process_orders_batch(recent_orders, meli_client)
        
        # PASO 3: Mostrar resultados
        print(f"\n📊 PASO 3: Resultados del procesamiento")
        print("=" * 60)
        
        print(f"Total órdenes procesadas: {result.get('total_processed', 0)}")
        print(f"Órdenes nuevas insertadas: {result.get('new_orders', 0)}")
        print(f"Órdenes actualizadas: {result.get('updated_orders', 0)}")
        print(f"Órdenes ready_to_print: {result.get('ready_orders', 0)}")
        print(f"Órdenes asignadas: {result.get('assigned_orders', 0)}")
        
        # PASO 4: Estado de la base
        print(f"\n📋 PASO 4: Estado actual de la base de datos")
        print("-" * 50)
        
        from database_utils import get_database_summary
        summary = get_database_summary()
        
        print("📊 Órdenes por subestado:")
        for substatus, count in summary.get('by_substatus', {}).items():
            print(f"   {substatus}: {count}")
        
        print("\n🎯 Órdenes por asignación:")
        assigned = summary.get('assigned', 0)
        pending = summary.get('pending', 0)
        print(f"   Asignadas: {assigned}")
        print(f"   Pendientes: {pending}")
        
        # PASO 5: Mostrar últimas órdenes
        print(f"\n🏆 Últimas 5 órdenes en la base:")
        recent_in_db = summary.get('recent_orders', [])
        for order in recent_in_db[:5]:
            order_id = order.get('order_id', 'unknown')
            substatus = order.get('shipping_subestado', 'unknown')
            assigned = "✅" if order.get('asignado_flag') else "⏳"
            print(f"   {assigned} {order_id} - {substatus}")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR en pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print(f"🚀 Iniciando PIPELINE 4 PURE REAL - {datetime.now()}")
    
    success = test_pipeline_4_pure_real()
    
    if success:
        print(f"\n🎉 PIPELINE 4 COMPLETADO EXITOSAMENTE")
        print("🔥 Todas las órdenes son REALES de MercadoLibre")
    else:
        print(f"\n❌ PIPELINE 4 FALLÓ")
    
    print(f"\n⏰ Finalizado: {datetime.now()}")
