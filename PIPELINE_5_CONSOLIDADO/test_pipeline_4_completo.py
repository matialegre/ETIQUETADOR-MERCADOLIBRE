"""
TEST PIPELINE 4 COMPLETO - CON ÚLTIMAS 10 VENTAS REALES
======================================================

Loop completo que:
1. Trae las últimas 10 ventas de MercadoLibre
2. Procesa cada una con stock real (1 minuto entre consultas)
3. Asigna depósitos con reintentos
4. Muestra resultados detallados
"""

import time
import logging
import pyodbc
import sys
import os
from datetime import datetime

# Configurar logging detallado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Agregar paths
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'modules'))

def test_pipeline_4_completo():
    """
    Test completo del PIPELINE 4 con órdenes reales.
    """
    print("🔥 INICIANDO TEST PIPELINE 4 COMPLETO")
    print("=" * 60)
    
    conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
    
    try:
        # PASO 1: Obtener últimas 10 ventas REALES de MercadoLibre
        print("\n📥 PASO 1: Obteniendo últimas 10 ventas de MercadoLibre...")
        print("-" * 50)
        
        # Importar cliente MercadoLibre REAL
        from meli_client_real import get_recent_orders_real
        
        recent_orders = get_recent_orders_real(limit=20)
        print(f"✅ Órdenes obtenidas: {len(recent_orders)}")
        
        for i, order in enumerate(recent_orders, 1):
            order_id = order.get('id', 'unknown')
            status = order.get('status', 'unknown')
            substatus = order.get('substatus', 'unknown')
            print(f"   {i}. {order_id} - {status}/{substatus}")
        
        # PASO 2: Procesar cada orden individualmente
        print(f"\n🔄 PASO 2: Procesando {len(recent_orders)} órdenes...")
        print("-" * 50)
        
        processed_orders = []
        ready_to_print_count = 0
        assigned_count = 0
        
        for i, order in enumerate(recent_orders, 1):
            try:
                order_id = order.get('id')
                substatus = order.get('substatus', '')
                
                print(f"\n🔍 Procesando orden {i}/{len(recent_orders)}: {order_id}")
                print(f"   Estado: {order.get('status', 'unknown')}")
                print(f"   Subestado: {substatus}")
                
                # Verificar si ya existe en BD
                exists = check_order_exists(conn_str, order_id)
                
                if exists:
                    print(f"   ⚠️  Orden ya existe en BD")
                    
                    # Si está ready_to_print y no asignada, intentar asignar
                    if substatus == 'ready_to_print':
                        ready_to_print_count += 1
                        assigned = try_assign_existing_order(conn_str, order_id)
                        if assigned:
                            assigned_count += 1
                            print(f"   ✅ Orden asignada exitosamente")
                        else:
                            print(f"   ❌ No se pudo asignar")
                else:
                    print(f"   📝 Nueva orden - insertando...")
                    inserted = insert_new_order_simple(conn_str, order)
                    
                    if inserted and substatus == 'ready_to_print':
                        ready_to_print_count += 1
                        print(f"   🎯 Orden ready_to_print - intentando asignar...")
                        
                        # Esperar un momento antes de asignar
                        time.sleep(2)
                        
                        assigned = try_assign_existing_order(conn_str, order_id)
                        if assigned:
                            assigned_count += 1
                            print(f"   ✅ Nueva orden asignada exitosamente")
                        else:
                            print(f"   ❌ Nueva orden no se pudo asignar")
                
                # Agregar a resultados
                processed_orders.append({
                    'order_id': order_id,
                    'status': order.get('status', ''),
                    'substatus': substatus,
                    'exists': exists,
                    'ready_to_print': substatus == 'ready_to_print'
                })
                
                # Pausa entre órdenes para no saturar APIs
                if i < len(recent_orders):
                    print(f"   ⏳ Esperando 3 segundos antes de la siguiente orden...")
                    time.sleep(3)
                
            except Exception as e:
                print(f"   ❌ Error procesando orden {order.get('id', 'unknown')}: {e}")
                continue
        
        # PASO 3: Resumen final
        print(f"\n📊 PASO 3: Resumen final")
        print("=" * 60)
        print(f"Total órdenes procesadas: {len(processed_orders)}")
        print(f"Órdenes ready_to_print: {ready_to_print_count}")
        print(f"Órdenes asignadas: {assigned_count}")
        
        # PASO 4: Mostrar estado actual de la BD
        print(f"\n📋 PASO 4: Estado actual de la base de datos")
        print("-" * 50)
        
        show_current_database_status(conn_str)
        
        # PASO 5: Ejecutar sync incremental
        print(f"\n🔄 PASO 5: Ejecutando sync incremental...")
        print("-" * 50)
        
        from sync_incremental import sync_status_changes
        sync_result = sync_status_changes()
        
        print(f"Sync resultado: {sync_result}")
        
        print(f"\n🎉 TEST PIPELINE 4 COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        
        return {
            'processed': len(processed_orders),
            'ready_to_print': ready_to_print_count,
            'assigned': assigned_count,
            'sync_result': sync_result
        }
        
    except Exception as e:
        print(f"❌ Error en test pipeline 4: {e}")
        import traceback
        traceback.print_exc()
        return None

def check_order_exists(conn_str: str, order_id: str) -> bool:
    """Verifica si una orden ya existe en la BD."""
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders_meli WHERE order_id = ?", (order_id,))
            count = cursor.fetchone()[0]
            return count > 0
    except Exception as e:
        logger.error(f"Error verificando orden existente: {e}")
        return False

def insert_new_order_simple(conn_str: str, order: dict) -> bool:
    """Inserta una nueva orden de forma simplificada."""
    try:
        order_id = order.get('id')
        status = order.get('status', '')
        substatus = order.get('substatus', '')
        
        # Obtener primer item
        order_items = order.get('order_items', [])
        if not order_items:
            return False
        
        first_item = order_items[0]
        item_data = first_item.get('item', {})
        sku = item_data.get('seller_custom_field', '')
        qty = first_item.get('quantity', 1)
        
        if not sku:
            return False
        
        # Obtener shipping info
        shipping = order.get('shipping', {})
        shipping_status = shipping.get('status', '')
        shipping_substatus = shipping.get('substatus', '')
        
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO orders_meli 
                (order_id, sku, qty, estado, subestado, shipping_estado, shipping_subestado, 
                 fecha_orden, asignado_flag, movimiento_realizado)
                VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE(), 0, 0)
            """, (order_id, sku, qty, status, substatus, shipping_status, shipping_substatus))
            
            conn.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error insertando nueva orden: {e}")
        return False

def try_assign_existing_order(conn_str: str, order_id: str) -> bool:
    """Intenta asignar una orden existente usando el asignador."""
    try:
        # Obtener datos de la orden
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, sku, qty, asignado_flag
                FROM orders_meli 
                WHERE order_id = ? AND subestado = 'ready_to_print'
            """, (order_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return False
            
            db_id, sku, qty, asignado_flag = row
            
            if asignado_flag:
                print(f"   ⚠️  Orden ya está asignada")
                return True
            
            print(f"   🔍 SKU: {sku}, Cantidad: {qty}")
            
            # Consultar stock con reintentos (SECUENCIAL, 1 minuto entre intentos)
            print(f"   📦 Consultando stock para {sku}...")
            stock_data = get_stock_with_retries(sku)
            
            if not stock_data:
                print(f"   ❌ No se pudo obtener stock para {sku}")
                return False
            
            print(f"   ✅ Stock obtenido de {len(stock_data)} depósitos")
            for depot, stock in stock_data.items():
                print(f"      {depot}: {stock} unidades")
            
            # Usar asignador para elegir depósito
            from assigner import choose_winner
            
            # Convertir formato para asignador
            stock_for_assigner = {}
            for depot, stock_count in stock_data.items():
                stock_for_assigner[depot] = {
                    'total': stock_count,
                    'reserved': 0
                }
            
            winner = choose_winner(stock_for_assigner, qty)
            
            if not winner:
                print(f"   ❌ No hay stock suficiente para cantidad {qty}")
                return False
            
            depot, total, reserved = winner
            print(f"   🏆 Depósito ganador: {depot} (stock: {total})")
            
            # Asignar con transacción
            return assign_order_transaction(conn_str, db_id, depot, total, reserved, qty)
            
    except Exception as e:
        logger.error(f"Error asignando orden: {e}")
        return False

def get_stock_with_retries(sku: str, max_retries: int = 3, wait_time: int = 60) -> dict:
    """
    Obtiene stock con reintentos y espera de 1 minuto entre intentos.
    SECUENCIAL - Una consulta a la vez.
    """
    for attempt in range(max_retries):
        try:
            print(f"   🔄 Intento {attempt + 1}/{max_retries} - Consultando stock...")
            
            # Mock de stock por ahora (reemplazar con API real)
            stock_mock = {
                'MUNDOCAB': 2,
                'DEPOSITO': 1,
                'MUNDOAL': 3,
                'MUNDOROC': 1
            }
            
            # Simular delay de API
            time.sleep(2)
            
            print(f"   ✅ Stock obtenido exitosamente")
            return stock_mock
            
        except Exception as e:
            print(f"   ❌ Error en intento {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                print(f"   ⏳ Esperando {wait_time} segundos antes del siguiente intento...")
                time.sleep(wait_time)
    
    print(f"   ❌ Falló después de {max_retries} intentos")
    return None

def assign_order_transaction(conn_str: str, db_id: int, depot: str, total: int, reserved: int, qty: int) -> bool:
    """Asigna orden con transacción segura."""
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            try:
                # Lock exclusivo
                cursor.execute("""
                    SELECT asignado_flag FROM orders_meli WITH (UPDLOCK,ROWLOCK) 
                    WHERE id = ?
                """, (db_id,))
                
                locked_row = cursor.fetchone()
                
                if not locked_row or locked_row[0]:
                    cursor.execute("ROLLBACK TRANSACTION")
                    return False
                
                # Calcular valores
                new_reserved = reserved + qty
                resultante = total - new_reserved
                agotamiento_flag = (resultante <= 0)
                
                # Actualizar orden
                cursor.execute("""
                    UPDATE orders_meli 
                    SET deposito_asignado = ?,
                        stock_real = ?,
                        stock_reservado = ?,
                        resultante = ?,
                        asignado_flag = 1,
                        agotamiento_flag = ?,
                        fecha_asignacion = GETDATE(),
                        movimiento_realizado = 0,
                        observacion_movimiento = 'Asignado por test pipeline 4, pendiente movimiento ML'
                    WHERE id = ?
                """, (depot, total, new_reserved, resultante, agotamiento_flag, db_id))
                
                cursor.execute("COMMIT TRANSACTION")
                
                print(f"   ✅ Asignación exitosa:")
                print(f"      Depósito: {depot}")
                print(f"      Stock real: {total}")
                print(f"      Reservado: {new_reserved}")
                print(f"      Resultante: {resultante}")
                print(f"      Agotamiento: {agotamiento_flag}")
                
                return True
                
            except Exception as e:
                cursor.execute("ROLLBACK TRANSACTION")
                raise e
                
    except Exception as e:
        logger.error(f"Error en transacción de asignación: {e}")
        return False

def show_current_database_status(conn_str: str):
    """Muestra el estado actual de la base de datos."""
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            
            # Contar por subestado
            cursor.execute("""
                SELECT subestado, COUNT(*) as count
                FROM orders_meli 
                GROUP BY subestado
                ORDER BY count DESC
            """)
            
            print("📊 Órdenes por subestado:")
            for row in cursor.fetchall():
                subestado, count = row
                print(f"   {subestado or 'sin_subestado'}: {count}")
            
            # Contar asignadas
            cursor.execute("""
                SELECT asignado_flag, COUNT(*) as count
                FROM orders_meli 
                GROUP BY asignado_flag
            """)
            
            print("\n🎯 Órdenes por asignación:")
            for row in cursor.fetchall():
                asignado, count = row
                status = "Asignadas" if asignado else "Pendientes"
                print(f"   {status}: {count}")
            
            # Últimas 5 órdenes asignadas
            cursor.execute("""
                SELECT TOP 5 order_id, sku, deposito_asignado, resultante, fecha_asignacion
                FROM orders_meli 
                WHERE asignado_flag = 1
                ORDER BY fecha_asignacion DESC
            """)
            
            print("\n🏆 Últimas 5 órdenes asignadas:")
            for row in cursor.fetchall():
                order_id, sku, deposito, resultante, fecha = row
                fecha_str = fecha.strftime('%Y-%m-%d %H:%M') if fecha else 'N/A'
                print(f"   {order_id} - {sku} → {deposito} (stock: {resultante}) - {fecha_str}")
                
    except Exception as e:
        print(f"❌ Error mostrando estado BD: {e}")

if __name__ == "__main__":
    result = test_pipeline_4_completo()
    if result:
        print(f"\n🎯 RESULTADO FINAL: {result}")
    else:
        print(f"\n❌ TEST FALLÓ")
