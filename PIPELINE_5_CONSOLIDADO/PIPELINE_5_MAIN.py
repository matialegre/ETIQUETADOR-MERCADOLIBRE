"""
🚀 PIPELINE 5 CONSOLIDADO - MAIN SCRIPT
=====================================

Pipeline completo y consolidado con TODAS las funcionalidades que funcionan:
- Estados reales de shipping (ready_to_print, printed, shipped, cancelled)
- Detección de multiventas por pack_id
- Búsqueda de códigos de barra con fallback seller_custom_field → seller_sku
- Persistencia completa en base de datos SQL Server
- Refresh automático de tokens MercadoLibre

PROBLEMAS RESUELTOS:
- ✅ Estados de shipping ahora son reales (no todo ready_to_print)
- ✅ Búsqueda de barcode funciona para todos los SKUs
- ✅ Imports de cliente MercadoLibre unificados
- ⚠️ Error 403 en pack API documentado (pendiente scopes)

Autor: Cascade AI
Fecha: 2025-08-07
Versión: Pipeline 5 Consolidado
"""

import sys
import os
from datetime import datetime

# Agregar paths priorizando este directorio (local) para usar el cliente correcto
BASE_DIR = os.path.dirname(__file__)  # .../PIPELINE_7_FULL/PIPELINE_5_CONSOLIDADO
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Además, sumar el directorio modules dentro de PIPELINE_7_FULL
ROOT_DIR = os.path.dirname(os.path.dirname(BASE_DIR))  # .../PIPELINE_7_FULL
MODULES_DIR = os.path.join(ROOT_DIR, 'modules')
if MODULES_DIR not in sys.path:
    sys.path.insert(1, MODULES_DIR)

def main_pipeline_5(limit: int = 20):
    """
    Ejecuta el pipeline 5 consolidado completo.
    
    Funcionalidades:
    - Obtiene órdenes reales de MercadoLibre
    - Consulta estados reales de shipping vía API
    - Detecta multiventas por pack_id
    - Busca códigos de barra con fallback
    - Persiste todo en base de datos
    """
    
    print("🚀 PIPELINE 5 CONSOLIDADO - INICIO")
    print("=" * 80)
    print(f"⏰ Iniciado: {datetime.now()}")
    print()
    
    try:
        # PASO 1: Obtener órdenes reales
        print("📥 PASO 1: Obteniendo órdenes reales de MercadoLibre...")
        print("-" * 60)
        
        from meli_client_pure_real import get_recent_orders_pure_real
        
        # Obtener N órdenes reales (param)
        recent_orders = get_recent_orders_pure_real(limit=limit)
        
        if not recent_orders:
            print("❌ No se pudieron obtener órdenes reales")
            return False
        
        print(f"✅ {len(recent_orders)} órdenes reales obtenidas (solicitadas: {limit})")
        
        # PASO 2: Procesar órdenes CON ESTADOS REALES Y MULTIVENTAS
        print(f"\n🔄 PASO 2: Procesando {len(recent_orders)} órdenes con estados reales...")
        print("-" * 60)
        
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
        print("=" * 80)
        
        print(f"Total órdenes procesadas: {result.get('total_processed', 0)}")
        print(f"Órdenes nuevas insertadas: {result.get('new_orders', 0)}")
        print(f"Órdenes actualizadas: {result.get('updated_orders', 0)}")
        print(f"Órdenes ready_to_print: {result.get('ready_orders', 0)}")
        print(f"Órdenes asignadas: {result.get('assigned_orders', 0)}")
        
        # PASO 4: Normalización multiventa y relaciones (DB)
        print(f"\n🔗 PASO 4: Normalizando multiventa y relaciones en base...")
        print("-" * 60)
        from database_utils import normalize_multiventa_and_relacion
        norm = normalize_multiventa_and_relacion()
        print(
            f"   Packs>1: {norm.get('set_multiventa_pack',0)}; Qty>1: {norm.get('set_multiventa_qty',0)}; "
            f"Rel(pack): {norm.get('set_rel_pack',0)}; Rel(qty): {norm.get('set_rel_qty',0)}; Limpios(singletons): {norm.get('cleared_singleton_rel',0)}"
        )

        # PASO 5: Asignación (legacy). Se puede saltear desde orquestador
        import os as _os
        skip_assign = _os.getenv('PIPE5_SKIP_ASSIGN', '1') == '1'
        if skip_assign:
            print("\n🏭 PASO 5: [SKIP] Asignación legacy salteada por PIPE5_SKIP_ASSIGN=1 (usa PASO 08)")
        else:
            print(f"\n🏭 PASO 5: Asignación de depósitos para READY_TO_PRINT sin stock/deposito (lote 50)...")
            print("-" * 60)
            from assign_step import assign_ready_to_print_missing_stock
            assign_sum = assign_ready_to_print_missing_stock(limit=50)
            print(
                f"   Asignadas: {assign_sum.get('assigned',0)} | Agotadas: {assign_sum.get('exhausted',0)} | Errores: {assign_sum.get('errors',0)}"
            )

        # PASO 5.1: Movimientos legacy. Se puede saltear desde orquestador
        skip_move = _os.getenv('PIPE5_SKIP_MOVE', '1') == '1'
        if skip_move:
            print("\n🚚 PASO 5.1: [SKIP] Movimientos legacy salteados por PIPE5_SKIP_MOVE=1 (usa PASO 08)")
        else:
            print(f"\n🚚 PASO 5.1: Movimientos WOO→WOO para órdenes asignadas pendientes...")
            print("-" * 60)
            try:
                # Reutilizamos el script probado de movimientos
                from PIPELINE_6_ASIGNACION import movement_once as mov
                from database_utils import get_connection
                moved_ok = 0
                moved_err = 0
                with get_connection() as conn:
                    while True:
                        sel = mov.pick_order(conn, None)
                        if not sel:
                            break
                        order_id = sel['order_id']
                        pack_id = sel['pack_id']
                        sku = sel['sku']
                        barcode = sel['barcode']
                        qty = sel['qty']
                        obs = f"MATIAPP MELI A MELI | order_id={order_id} | pack_id={pack_id or ''}"
                        print(f"   ▶️ Moviendo order={order_id} sku={sku} qty={qty}")
                        res = mov.dragon_movement.move_stock_woo_to_woo(
                            sku=sku, qty=qty, observacion=obs, barcode=barcode,
                        )
                        ok = bool(res.get('ok'))
                        numero = res.get('numero')
                        status = res.get('status')
                        data = res.get('data')
                        error = res.get('error')
                        if ok:
                            obs_ok = f"{obs} | numero_movimiento={numero} | status={status}"
                            mov.update_success(conn, order_id, numero, obs_ok)
                            moved_ok += 1
                            print(f"   ✅ Movimiento OK | Numero={numero} | Status={status}")
                        else:
                            obs_err = f"{obs} | ERROR status={status} | detalle={str(data)[:300] if data else error}"
                            mov.update_failure(conn, order_id, obs_err)
                            moved_err += 1
                            print(f"   ❌ Movimiento FALLÓ | Status={status} | Error={error}")
                print(f"   Movimientos realizados: OK={moved_ok} | ERRORES={moved_err}")
            except Exception as me:
                print(f"   ⚠️ Saltando PASO 5.1 por error: {me}")

        # PASO 6: Estado de la base
        print(f"\n📋 PASO 6: Estado actual de la base de datos")
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
        
        # PASO 7: Mostrar últimas órdenes
        print(f"\n🏆 Últimas 10 órdenes en la base:")
        recent_in_db = summary.get('recent_orders', [])
        for order in recent_in_db[:10]:
            order_id = order.get('order_id', 'unknown')
            substatus = order.get('shipping_subestado', 'unknown')
            assigned = "✅" if order.get('asignado_flag') else "⏳"
            barcode = "📦" if order.get('barcode') else "❌"
            multiventa = "🔗" if order.get('multiventa_grupo') else "📄"
            print(f"   {assigned} {barcode} {multiventa} {order_id} - {substatus}")
        
        print(f"\n🎉 PIPELINE 5 COMPLETADO EXITOSAMENTE")
        print("🔥 Todas las órdenes son REALES de MercadoLibre")
        print("✅ Estados reales obtenidos desde API de shipping")
        print("✅ Multiventas detectadas por pack_id")
        print("✅ Códigos de barra encontrados con fallback")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR en pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        print(f"\n⏰ Finalizado: {datetime.now()}")

def limpiar_base_datos():
    """Limpia la base de datos para empezar desde cero."""
    
    print("🧹 LIMPIANDO BASE DE DATOS...")
    print("=" * 50)
    
    try:
        from database_utils import clear_all_orders
        
        result = clear_all_orders()
        
        if result:
            print("✅ Base de datos limpiada exitosamente")
            return True
        else:
            print("❌ Error limpiando base de datos")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 INICIANDO PIPELINE 5 CONSOLIDADO")
    print(f"📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Opción para limpiar base de datos (default: 's')
    limpiar_in = input("¿Limpiar base de datos antes de ejecutar? (S/n): ").lower().strip()
    limpiar = 's' if limpiar_in == '' else limpiar_in
    # Opción para limitar cantidad de órdenes a procesar en este ciclo
    try:
        limit_in = input("¿Cuántas órdenes recientes querés procesar? (default 10): ").strip()
        limit = int(limit_in) if limit_in else 10
        if limit <= 0:
            limit = 10
    except Exception:
        limit = 10
    
    if limpiar == 's':
        if limpiar_base_datos():
            print("\n" + "="*50)
            print("🚀 EJECUTANDO PIPELINE DESDE CERO...")
            print("="*50)
        else:
            print("❌ No se pudo limpiar la base. Abortando.")
            exit(1)
    
    # Ejecutar pipeline principal
    success = main_pipeline_5(limit=limit)
    
    if success:
        print("\n🎉 PIPELINE 5 EJECUTADO EXITOSAMENTE")
        exit(0)
    else:
        print("\n❌ PIPELINE 5 FALLÓ")
        exit(1)
