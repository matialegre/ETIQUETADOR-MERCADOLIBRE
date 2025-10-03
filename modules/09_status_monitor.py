"""
Módulo 09: Monitor de Estados
============================

Monitorea cambios de subestado en MercadoLibre y actualiza la base de datos.
Implementa estrategia híbrida: polling + webhooks.
"""

import pyodbc
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class StatusMonitor:
    def __init__(self):
        self.conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        self.polling_interval = 60  # 60 segundos
        self.last_check = datetime.now()
        
    def get_orders_to_monitor(self) -> List[Dict]:
        """
        Obtiene órdenes que necesitan monitoreo de cambio de estado.
        """
        with pyodbc.connect(self.conn_str) as conn:
            cursor = conn.cursor()
            
            # Órdenes asignadas que pueden cambiar de estado
            cursor.execute("""
                SELECT id, order_id, sku, subestado, asignado_flag, 
                       deposito_asignado, fecha_asignacion
                FROM orders_meli 
                WHERE asignado_flag = 1 
                AND subestado IN ('ready_to_print', 'printed', 'shipped')
                AND fecha_asignacion >= DATEADD(day, -7, GETDATE())
                ORDER BY fecha_asignacion DESC
            """)
            
            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'id': row[0],
                    'order_id': row[1], 
                    'sku': row[2],
                    'subestado': row[3],
                    'asignado_flag': row[4],
                    'deposito_asignado': row[5],
                    'fecha_asignacion': row[6]
                })
                
            return orders
    
    def check_meli_status_changes(self, orders: List[Dict]) -> List[Dict]:
        """
        Consulta MercadoLibre para verificar cambios de estado.
        """
        try:
            # Importar cliente MercadoLibre
            from modules.meli_client import get_recent_orders
            
            # Obtener órdenes recientes de MercadoLibre
            recent_meli_orders = get_recent_orders(limit=20)
            
            changes = []
            
            for db_order in orders:
                # Buscar la orden en MercadoLibre
                meli_order = None
                for meli in recent_meli_orders:
                    if str(meli.get('id')) == str(db_order['order_id']):
                        meli_order = meli
                        break
                
                if meli_order:
                    meli_subestado = meli_order.get('subestado', '')
                    db_subestado = db_order['subestado']
                    
                    # Detectar cambio de estado
                    if meli_subestado != db_subestado:
                        changes.append({
                            'db_id': db_order['id'],
                            'order_id': db_order['order_id'],
                            'sku': db_order['sku'],
                            'old_status': db_subestado,
                            'new_status': meli_subestado,
                            'deposito': db_order['deposito_asignado']
                        })
                        
                        logger.info(f"Cambio detectado: {db_order['order_id']} {db_subestado} → {meli_subestado}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error consultando MercadoLibre: {e}")
            return []
    
    def update_status_changes(self, changes: List[Dict]) -> int:
        """
        Actualiza los cambios de estado en la base de datos.
        """
        updated = 0
        
        with pyodbc.connect(self.conn_str) as conn:
            cursor = conn.cursor()
            
            for change in changes:
                try:
                    cursor.execute("BEGIN TRANSACTION")
                    
                    # Actualizar subestado con auditoría
                    cursor.execute("""
                        UPDATE orders_meli 
                        SET subestado = ?,
                            fecha_actualizacion = GETDATE(),
                            observacion_movimiento = CONCAT(
                                ISNULL(observacion_movimiento, ''), 
                                '; Estado cambiado: ', ?, ' → ', ?, ' (', FORMAT(GETDATE(), 'yyyy-MM-dd HH:mm'), ')'
                            )
                        WHERE id = ?
                    """, (
                        change['new_status'],
                        change['old_status'], 
                        change['new_status'],
                        change['db_id']
                    ))
                    
                    cursor.execute("COMMIT TRANSACTION")
                    updated += 1
                    
                    logger.info(f"Actualizado: {change['order_id']} → {change['new_status']}")
                    
                except Exception as e:
                    cursor.execute("ROLLBACK TRANSACTION")
                    logger.error(f"Error actualizando {change['order_id']}: {e}")
        
        return updated
    
    def run_polling_cycle(self) -> Dict:
        """
        Ejecuta un ciclo completo de monitoreo por polling.
        """
        logger.info("Iniciando ciclo de monitoreo de estados...")
        
        try:
            # 1. Obtener órdenes a monitorear
            orders = self.get_orders_to_monitor()
            logger.info(f"Monitoreando {len(orders)} órdenes")
            
            if not orders:
                return {'status': 'success', 'monitored': 0, 'changes': 0}
            
            # 2. Verificar cambios en MercadoLibre
            changes = self.check_meli_status_changes(orders)
            logger.info(f"Cambios detectados: {len(changes)}")
            
            # 3. Actualizar cambios en base de datos
            updated = self.update_status_changes(changes)
            logger.info(f"Órdenes actualizadas: {updated}")
            
            self.last_check = datetime.now()
            
            return {
                'status': 'success',
                'monitored': len(orders),
                'changes': len(changes),
                'updated': updated,
                'timestamp': self.last_check.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en ciclo de monitoreo: {e}")
            return {'status': 'error', 'error': str(e)}

# Función principal para usar en loop
def monitor_status_changes():
    """
    Función principal para monitorear cambios de estado.
    """
    monitor = StatusMonitor()
    return monitor.run_polling_cycle()

if __name__ == "__main__":
    # Test del monitor
    result = monitor_status_changes()
    print(f"Resultado del monitoreo: {result}")
