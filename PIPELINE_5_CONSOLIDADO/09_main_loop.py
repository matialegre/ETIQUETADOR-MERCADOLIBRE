"""
PASO 09: Main Loop - PIPELINE 4
===============================

Loop principal que ejecuta todos los procesos de forma coordinada:
- run_cycle_a(): Procesa nuevas órdenes y asigna depósitos
- assign_pending(): Asigna órdenes pendientes
- sync_status(): Sincroniza estados con MercadoLibre (PASO 10)
"""

import time
import logging
import argparse
from datetime import datetime
from typing import Optional

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_cycle_a():
    """
    Ciclo A: Procesar nuevas órdenes de MercadoLibre y asignar depósitos.
    Integra PASOS 01-08 del pipeline.
    """
    try:
        logger.info("=== INICIANDO CICLO A: NUEVAS ÓRDENES ===")
        
        # Importar módulos necesarios
        from modules.meli_client import get_recent_orders
        from modules.dragon_db import get_barcode_for_sku
        from modules.assigner import choose_winner
        from modules.assign_tx import assign_order_to_deposit
        
        # 1. Obtener órdenes recientes de MercadoLibre
        logger.info("1. Obteniendo órdenes recientes de MercadoLibre...")
        recent_orders = get_recent_orders(limit=10)
        logger.info(f"   Órdenes obtenidas: {len(recent_orders)}")
        
        # 2. Procesar cada orden
        new_assignments = 0
        for order in recent_orders:
            try:
                order_id = order.get('id')
                logger.info(f"   Procesando orden: {order_id}")
                
                # Verificar si ya existe en BD
                if order_already_exists(order_id):
                    logger.debug(f"   Orden {order_id} ya existe, saltando...")
                    continue
                
                # Insertar nueva orden
                inserted = insert_new_order(order)
                if inserted:
                    logger.info(f"   Nueva orden insertada: {order_id}")
                    
                    # Si está ready_to_print, intentar asignar inmediatamente
                    if order.get('subestado') == 'ready_to_print':
                        assigned = try_assign_immediately(order)
                        if assigned:
                            new_assignments += 1
                            logger.info(f"   Orden asignada inmediatamente: {order_id}")
                
            except Exception as e:
                logger.error(f"   Error procesando orden {order.get('id', 'unknown')}: {e}")
                continue
        
        logger.info(f"=== CICLO A COMPLETADO: {new_assignments} nuevas asignaciones ===")
        return new_assignments
        
    except Exception as e:
        logger.error(f"Error en run_cycle_a: {e}")
        return 0

def assign_pending():
    """
    Asignar órdenes pendientes que están ready_to_print pero no asignadas.
    Usa el asignador del PASO 08.
    """
    try:
        logger.info("=== INICIANDO ASIGNACIÓN PENDIENTES ===")
        
        from modules.assign_tx import process_pending_orders
        
        # Procesar órdenes pendientes
        result = process_pending_orders()
        
        assigned = result.get('assigned', 0)
        logger.info(f"=== ASIGNACIÓN COMPLETADA: {assigned} órdenes asignadas ===")
        
        return assigned
        
    except Exception as e:
        logger.error(f"Error en assign_pending: {e}")
        return 0

def sync_status():
    """
    PASO 10: Sincronización incremental de estados con MercadoLibre.
    """
    try:
        logger.info("=== INICIANDO SYNC STATUS ===")
        
        from modules.sync_incremental import sync_status_changes
        
        # Sincronizar cambios de estado
        result = sync_status_changes()
        
        updated = result.get('updated', 0)
        logger.info(f"=== SYNC COMPLETADO: {updated} órdenes actualizadas ===")
        
        return updated
        
    except Exception as e:
        logger.error(f"Error en sync_status: {e}")
        return 0

def order_already_exists(order_id: str) -> bool:
    """Verifica si una orden ya existe en la base de datos."""
    try:
        import pyodbc
        
        conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders_meli WHERE order_id = ?", (order_id,))
            count = cursor.fetchone()[0]
            return count > 0
            
    except Exception as e:
        logger.error(f"Error verificando orden existente: {e}")
        return False

def insert_new_order(order: dict) -> bool:
    """Inserta una nueva orden en la base de datos."""
    try:
        # Importar función de inserción del pipeline anterior
        from modules.integration_v2 import build_order_data, insert_order_if_new
        
        # Construir datos de la orden
        order_data = build_order_data(order)
        
        # Insertar si es nueva
        inserted = insert_order_if_new(order_data)
        
        return inserted
        
    except Exception as e:
        logger.error(f"Error insertando nueva orden: {e}")
        return False

def try_assign_immediately(order: dict) -> bool:
    """Intenta asignar una orden inmediatamente si está ready_to_print."""
    try:
        from modules.assign_tx import assign_single_order
        
        order_id = order.get('id')
        
        # Buscar la orden en BD para obtener el ID interno
        import pyodbc
        conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM orders_meli WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            
            if row:
                db_id = row[0]
                result = assign_single_order(db_id)
                return result.get('success', False)
        
        return False
        
    except Exception as e:
        logger.error(f"Error en asignación inmediata: {e}")
        return False

def main_loop(cycles: Optional[int] = None, sleep: int = 60):
    """
    Loop principal del pipeline.
    
    Args:
        cycles: Número de ciclos a ejecutar (None = infinito)
        sleep: Segundos entre ciclos
    """
    logger.info("=== INICIANDO MAIN LOOP PIPELINE 4 ===")
    logger.info(f"Configuración: cycles={cycles}, sleep={sleep}s")
    
    n = 0
    start_time = datetime.now()
    
    try:
        while cycles is None or n < cycles:
            cycle_start = datetime.now()
            logger.info(f"\n--- CICLO {n + 1} ---")
            
            try:
                # Ejecutar los 3 pasos principales
                new_orders = run_cycle_a()
                pending_assigned = assign_pending() 
                status_updated = sync_status()
                
                # Resumen del ciclo
                cycle_duration = (datetime.now() - cycle_start).total_seconds()
                logger.info(f"--- CICLO {n + 1} COMPLETADO en {cycle_duration:.1f}s ---")
                logger.info(f"    Nuevas órdenes: {new_orders}")
                logger.info(f"    Pendientes asignadas: {pending_assigned}")
                logger.info(f"    Estados actualizados: {status_updated}")
                
            except Exception as e:
                logger.error(f"Error en ciclo {n + 1}: {e}")
            
            n += 1
            
            # Dormir entre ciclos (excepto en el último)
            if cycles is None or n < cycles:
                logger.info(f"Esperando {sleep}s hasta próximo ciclo...")
                time.sleep(sleep)
    
    except KeyboardInterrupt:
        logger.info("Loop interrumpido por usuario")
    
    except Exception as e:
        logger.error(f"Error fatal en main loop: {e}")
    
    finally:
        total_duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"=== MAIN LOOP FINALIZADO ===")
        logger.info(f"Ciclos ejecutados: {n}")
        logger.info(f"Duración total: {total_duration:.1f}s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Main Loop Pipeline 4')
    parser.add_argument('--cycles', type=int, default=None, help='Número de ciclos (default: infinito)')
    parser.add_argument('--sleep', type=int, default=60, help='Segundos entre ciclos (default: 60)')
    
    args = parser.parse_args()
    
    main_loop(cycles=args.cycles, sleep=args.sleep)
