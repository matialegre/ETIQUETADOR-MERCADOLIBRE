"""
UTILIDADES DE BASE DE DATOS PARA ÓRDENES REALES
===============================================

Manejo de base de datos para órdenes reales de MercadoLibre.
"""

import pyodbc
from typing import Dict, Optional, List
from datetime import datetime

# Connection string para SQL Server Express
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=.\\SQLEXPRESS;"
    "DATABASE=meli_stock;"
    "Trusted_Connection=yes;"
)

def get_connection():
    """Obtiene conexión a la base de datos."""
    return pyodbc.connect(CONNECTION_STRING)

def insert_or_update_order(order_data: Dict) -> str:
    """
    Inserta o actualiza una orden en la base de datos.
    
    Args:
        order_data: Datos de la orden procesada
        
    Returns:
        'inserted' o 'updated'
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Verificar si la orden existe
            cursor.execute(
                "SELECT COUNT(*) FROM orders_meli WHERE order_id = ?",
                (order_data['order_id'],)
            )
            
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Actualizar orden existente
                update_sql = """
                UPDATE orders_meli SET
                    sku = ?,
                    seller_sku = ?,
                    barcode = ?,
                    item_id = ?,
                    pack_id = ?,
                    qty = ?,
                    total_amount = ?,
                    estado = ?,
                    subestado = ?,
                    shipping_id = ?,
                    shipping_estado = ?,
                    shipping_subestado = ?,
                    date_created = ?,
                    date_closed = ?,
                    display_color = ?,
                    fecha_actualizacion = ?
                WHERE order_id = ?
                """
                
                cursor.execute(update_sql, (
                    order_data['sku'],
                    order_data['seller_sku'],
                    order_data['barcode'],  # NUEVO: Campo barcode
                    order_data['item_id'],
                    order_data['pack_id'],
                    order_data['quantity'],
                    order_data['total_amount'],
                    order_data['status'],
                    order_data['substatus'],
                    order_data['shipping_id'],
                    order_data['shipping_estado'],
                    order_data['shipping_subestado'],
                    order_data['date_created'],
                    order_data['date_closed'],
                    order_data['display_color'],
                    order_data['fecha_actualizacion'],
                    order_data['order_id']
                ))
                
                conn.commit()
                return 'updated'
                
            else:
                # Insertar nueva orden
                insert_sql = """
                INSERT INTO orders_meli (
                    order_id, sku, seller_sku, barcode, item_id, pack_id, qty, total_amount,
                    estado, subestado, shipping_id, shipping_estado, shipping_subestado,
                    date_created, date_closed, display_color, asignado_flag,
                    movimiento_realizado, fecha_actualizacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor.execute(insert_sql, (
                    order_data['order_id'],
                    order_data['sku'],
                    order_data['seller_sku'],
                    order_data['barcode'],  # NUEVO: Campo barcode
                    order_data['item_id'],
                    order_data['pack_id'],
                    order_data['quantity'],
                    order_data['total_amount'],
                    order_data['status'],
                    order_data['substatus'],
                    order_data['shipping_id'],
                    order_data['shipping_estado'],
                    order_data['shipping_subestado'],
                    order_data['date_created'],
                    order_data['date_closed'],
                    order_data['display_color'],
                    order_data['asignado_flag'],
                    order_data['movimiento_realizado'],
                    order_data['fecha_actualizacion']
                ))
                
                conn.commit()
                return 'inserted'
                
    except Exception as e:
        print(f"❌ Error en base de datos: {e}")
        raise

def get_database_summary() -> Dict:
    """
    Obtiene resumen del estado de la base de datos.
    
    Returns:
        Dict con estadísticas de la base
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Contar por subestado
            cursor.execute("""
                SELECT shipping_subestado, COUNT(*) 
                FROM orders_meli 
                GROUP BY shipping_subestado
            """)
            
            by_substatus = {}
            for row in cursor.fetchall():
                substatus = row[0] or 'sin_subestado'
                count = row[1]
                by_substatus[substatus] = count
            
            # Contar asignadas vs pendientes
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN asignado_flag = 1 THEN 1 ELSE 0 END) as assigned,
                    SUM(CASE WHEN asignado_flag = 0 THEN 1 ELSE 0 END) as pending
                FROM orders_meli
            """)
            
            assignment_row = cursor.fetchone()
            assigned = assignment_row[0] or 0
            pending = assignment_row[1] or 0
            
            # Últimas órdenes
            cursor.execute("""
                SELECT TOP 10 order_id, shipping_subestado, asignado_flag, fecha_actualizacion
                FROM orders_meli 
                ORDER BY fecha_actualizacion DESC
            """)
            
            recent_orders = []
            for row in cursor.fetchall():
                recent_orders.append({
                    'order_id': row[0],
                    'shipping_subestado': row[1],
                    'asignado_flag': bool(row[2]),
                    'fecha_actualizacion': row[3]
                })
            
            return {
                'by_substatus': by_substatus,
                'assigned': assigned,
                'pending': pending,
                'recent_orders': recent_orders
            }
            
    except Exception as e:
        print(f"❌ Error obteniendo resumen: {e}")
        return {
            'by_substatus': {},
            'assigned': 0,
            'pending': 0,
            'recent_orders': []
        }

def clear_all_orders() -> bool:
    """
    Limpia todas las órdenes de la base de datos.
    
    Returns:
        True si se limpió exitosamente, False si hubo error
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Contar órdenes antes de limpiar
            cursor.execute("SELECT COUNT(*) FROM orders_meli")
            count_before = cursor.fetchone()[0]
            
            print(f"📄 Órdenes en base antes de limpiar: {count_before}")
            
            # Limpiar todas las órdenes
            cursor.execute("DELETE FROM orders_meli")
            conn.commit()
            
            # Verificar que se limpió
            cursor.execute("SELECT COUNT(*) FROM orders_meli")
            count_after = cursor.fetchone()[0]
            
            print(f"🧹 Órdenes en base después de limpiar: {count_after}")
            
            if count_after == 0:
                print(f"✅ Base de datos limpiada exitosamente ({count_before} órdenes eliminadas)")
                return True
            else:
                print(f"⚠️ Advertencia: Aún quedan {count_after} órdenes en la base")
                return False
                
    except Exception as e:
        print(f"❌ Error limpiando base de datos: {e}")
        return False
