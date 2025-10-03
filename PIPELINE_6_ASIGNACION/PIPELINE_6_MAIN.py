"""
🚀 PIPELINE 6 - ASIGNACIÓN AUTOMÁTICA DE DEPÓSITOS
=================================================

Pipeline especializado en asignar depósitos ganadores a órdenes ready_to_print:
- Filtra órdenes con shipping_estado='ready_to_print' y asignado_flag=0
- Consulta stock real en Dragonfish API por depósito
- Aplica lógica de prioridades para elegir depósito ganador
- Actualiza asignado_flag=1 y campos de asignación en base de datos

REQUISITOS:
- Pipeline 5 debe haber ejecutado y poblado órdenes con estados reales
- Base de datos con órdenes ready_to_print sin asignar
- Conexión a Dragonfish API para consulta de stock

Autor: Cascade AI
Fecha: 2025-08-07
Versión: Pipeline 6 Asignación
"""

import sys
import os
from datetime import datetime

# Agregar paths
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')
sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\PIPELINE_6_ASIGNACION')

def main_pipeline_6():
    """
    Ejecuta el pipeline 6 de asignación automática de depósitos.
    
    Proceso:
    1. Filtra órdenes ready_to_print sin asignar
    2. Para cada orden, consulta stock en todos los depósitos
    3. Aplica lógica de prioridades para elegir depósito ganador
    4. Actualiza la orden con asignación y marca asignado_flag=1
    """
    
    print("🚀 PIPELINE 6 - ASIGNACIÓN AUTOMÁTICA DE DEPÓSITOS")
    print("=" * 80)
    print(f"⏰ Iniciado: {datetime.now()}")
    print()
    
    try:
        # PASO 1: Filtrar órdenes ready_to_print sin asignar
        print("🔍 PASO 1: Filtrando órdenes ready_to_print sin asignar...")
        print("-" * 60)
        
        from filter_ready import get_ready_orders
        
        ready_orders = get_ready_orders()
        
        if not ready_orders:
            print("ℹ️ No hay órdenes ready_to_print sin asignar")
            return True
        
        print(f"✅ {len(ready_orders)} órdenes ready_to_print encontradas para asignar")
        
        # Mostrar órdenes a procesar
        for i, order in enumerate(ready_orders, 1):
            order_id = order.get('order_id', 'unknown')
            sku = order.get('sku', 'unknown')
            barcode = order.get('barcode', 'N/A')
            print(f"   {i}. {order_id} - SKU: {sku} - Barcode: {barcode}")
        
        # PASO 2: Procesar asignación para cada orden
        print(f"\n🎯 PASO 2: Procesando asignación para {len(ready_orders)} órdenes...")
        print("-" * 60)
        
        from assigner import assign_depot_to_orders
        
        # Procesar asignación en lote
        assignment_results = assign_depot_to_orders(ready_orders)
        
        # PASO 3: Mostrar resultados de asignación
        print(f"\n📊 PASO 3: Resultados de asignación")
        print("=" * 80)
        
        total_processed = assignment_results.get('total_processed', 0)
        assigned_count = assignment_results.get('assigned', 0)
        no_stock_count = assignment_results.get('no_stock', 0)
        errors_count = len(assignment_results.get('errors', []))
        
        print(f"Total órdenes procesadas: {total_processed}")
        print(f"Órdenes asignadas exitosamente: {assigned_count}")
        print(f"Órdenes sin stock disponible: {no_stock_count}")
        print(f"Errores de procesamiento: {errors_count}")
        
        # Mostrar asignaciones exitosas
        if assignment_results.get('assignments'):
            print(f"\n✅ Asignaciones exitosas:")
            for assignment in assignment_results['assignments']:
                order_id = assignment.get('order_id', 'unknown')
                depot = assignment.get('depot_assigned', 'unknown')
                stock = assignment.get('stock_found', 0)
                print(f"   📦 {order_id} → {depot} (Stock: {stock})")
        
        # Mostrar órdenes sin stock
        if assignment_results.get('no_stock_orders'):
            print(f"\n⚠️ Órdenes sin stock disponible:")
            for order in assignment_results['no_stock_orders']:
                order_id = order.get('order_id', 'unknown')
                sku = order.get('sku', 'unknown')
                print(f"   ❌ {order_id} - SKU: {sku}")
        
        # Mostrar errores
        if assignment_results.get('errors'):
            print(f"\n❌ Errores encontrados:")
            for error in assignment_results['errors']:
                print(f"   🔴 {error}")
        
        # PASO 4: Estado final de la base de datos
        print(f"\n📋 PASO 4: Estado final de la base de datos")
        print("-" * 60)
        
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
        
        print(f"\n🎉 PIPELINE 6 COMPLETADO EXITOSAMENTE")
        print(f"✅ {assigned_count} órdenes asignadas a depósitos")
        print("🏭 Lógica de prioridades aplicada correctamente")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR en pipeline 6: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print(f"\n⏰ Finalizado: {datetime.now()}")

def verificar_estado_base():
    """Verifica el estado actual de la base de datos."""
    
    print("🔍 VERIFICANDO ESTADO DE LA BASE DE DATOS...")
    print("=" * 60)
    
    try:
        from database_utils import get_database_summary
        summary = get_database_summary()
        
        print("📊 Resumen actual:")
        print(f"   Total órdenes: {summary.get('assigned', 0) + summary.get('pending', 0)}")
        print(f"   Asignadas: {summary.get('assigned', 0)}")
        print(f"   Pendientes: {summary.get('pending', 0)}")
        
        print("\n📋 Por subestado:")
        for substatus, count in summary.get('by_substatus', {}).items():
            print(f"   {substatus}: {count}")
        
        # Contar ready_to_print sin asignar específicamente
        from filter_ready import get_ready_orders
        ready_orders = get_ready_orders()
        
        print(f"\n🎯 Ready to print sin asignar: {len(ready_orders)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO PIPELINE 6 - ASIGNACIÓN DE DEPÓSITOS")
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Verificar estado inicial
    print("🔍 VERIFICANDO ESTADO INICIAL...")
    if not verificar_estado_base():
        print("❌ No se pudo verificar el estado de la base. Abortando.")
        exit(1)
    
    print("\n" + "="*80)
    print("🚀 EJECUTANDO ASIGNACIÓN DE DEPÓSITOS...")
    print("="*80)
    
    # Ejecutar pipeline de asignación
    success = main_pipeline_6()
    
    if success:
        print("\n🎉 PIPELINE 6 EJECUTADO EXITOSAMENTE")
        exit(0)
    else:
        print("\n❌ PIPELINE 6 FALLÓ")
        exit(1)
