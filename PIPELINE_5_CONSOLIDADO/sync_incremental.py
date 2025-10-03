"""
PASO 10: Sync Incremental - PIPELINE 4
======================================

Sincronización incremental de estados con MercadoLibre.
Actualiza órdenes asignadas con cambios de estado/subestado/shipping/notas.
"""

import logging
import pyodbc
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

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
        
        nuevos = get_recent_orders(limit=15)  # Más órdenes para mejor sync
        logger.info(f"Órdenes obtenidas de MercadoLibre: {len(nuevos)}")
        
        updated_count = 0
        inserted_count = 0
        
        conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        
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
                                       nota, asignado_flag, fecha_actualizacion
                                FROM orders_meli 
                                WHERE order_id = ? AND sku = ?
                            """, (key[0], key[1]))
                            
                            fila = cursor.fetchone()
                            
                            if fila:
                                # ORDEN EXISTE - Actualizar si está asignada
                                db_id, current_estado, current_subestado, current_shipping_estado, current_shipping_subestado, current_nota, asignado_flag, fecha_actualizacion = fila
                                
                                if asignado_flag:
                                    # Extraer nuevos valores de MercadoLibre
                                    new_estado = o.get('status', '')
                                    new_subestado = o.get('substatus', '')
                                    
                                    shipping = o.get('shipping', {})
                                    new_shipping_estado = shipping.get('status', '')
                                    new_shipping_subestado = shipping.get('substatus', '')
                                    
                                    new_nota = o.get('comments', '')
                                    
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
                                # ORDEN NO EXISTE - Insertar nueva
                                try:
                                    # Por ahora, solo logear órdenes nuevas sin insertar
                                    logger.info(f"Nueva orden detectada: {order_id}-{sku} (inserción pendiente)")
                                    # TODO: Implementar inserción de nuevas órdenes
                                
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
