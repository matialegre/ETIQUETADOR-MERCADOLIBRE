"""
MÓDULO DE FILTRO PARA ÓRDENES READY_TO_PRINT
============================================

Filtra órdenes que están listas para asignar depósito:
- shipping_estado = 'ready_to_print'
- asignado_flag = 0 (sin asignar)
- Tienen código de barra disponible

Compatible con database_utils.py del Pipeline 5.

Autor: Cascade AI
Fecha: 2025-08-07
"""

import pyodbc
from typing import List, Dict, Optional
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

def get_ready_orders() -> List[Dict]:
    """
    Obtiene órdenes ready_to_print sin asignar.
    
    Filtra por:
    - shipping_subestado = 'ready_to_print'
    - asignado_flag = 0 (sin asignar)
    - barcode IS NOT NULL (tiene código de barra)
    
    Returns:
        List[Dict]: Lista de órdenes listas para asignar
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Consulta para órdenes ready_to_print sin asignar
            query = """
            SELECT 
                order_id,
                sku,
                seller_sku,
                barcode,
                item_id,
                quantity,
                shipping_id,
                shipping_estado,
                shipping_subestado,
                date_created,
                multiventa_grupo,
                pack_id
            FROM orders_meli 
            WHERE 
                shipping_subestado = 'ready_to_print'
                AND asignado_flag = 0
                AND barcode IS NOT NULL
                AND barcode != ''
            ORDER BY date_created ASC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convertir a lista de diccionarios
            orders = []
            for row in rows:
                order = {
                    'order_id': row[0],
                    'sku': row[1],
                    'seller_sku': row[2],
                    'barcode': row[3],
                    'item_id': row[4],
                    'quantity': row[5],
                    'shipping_id': row[6],
                    'shipping_estado': row[7],
                    'shipping_subestado': row[8],
                    'date_created': row[9],
                    'multiventa_grupo': row[10],
                    'pack_id': row[11]
                }
                orders.append(order)
            
            print(f"🔍 Órdenes ready_to_print encontradas: {len(orders)}")
            return orders
            
    except Exception as e:
        print(f"❌ Error obteniendo órdenes ready_to_print: {e}")
        return []

def count_ready_orders() -> int:
    """
    Cuenta órdenes ready_to_print sin asignar.
    
    Returns:
        int: Número de órdenes ready_to_print sin asignar
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM orders_meli 
                WHERE 
                    shipping_subestado = 'ready_to_print'
                    AND asignado_flag = 0
                    AND barcode IS NOT NULL
                    AND barcode != ''
            """)
            
            count = cursor.fetchone()[0]
            return count
            
    except Exception as e:
        print(f"❌ Error contando órdenes ready_to_print: {e}")
        return 0


if __name__ == "__main__":
    # Test básico
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        pending = get_pending_ready()
        print(f"✅ Órdenes pendientes encontradas: {len(pending)}")
        
        for order in pending[:3]:  # Mostrar solo las primeras 3
            print(f"   📋 Order: {order.order_id}, SKU: {order.sku}, Fecha: {order.fecha_orden}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
