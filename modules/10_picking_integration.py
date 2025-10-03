"""
Módulo 10: Integración con Sistema de Picking
=============================================

Integra con sistema de picking para:
1. Notificar cuando una orden está lista para picking
2. Recibir confirmación de picking completado
3. Descargar etiqueta automáticamente
4. Actualizar estado a 'printed'
"""

import pyodbc
import requests
import logging
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

class PickingIntegration:
    def __init__(self):
        self.conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        self.picking_api_base = "http://localhost:8080/api/picking"  # URL del sistema de picking
        
    def get_orders_ready_for_picking(self) -> List[Dict]:
        """
        Obtiene órdenes asignadas listas para picking.
        """
        with pyodbc.connect(self.conn_str) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, order_id, sku, qty, deposito_asignado, 
                       fecha_asignacion, barcode
                FROM orders_meli 
                WHERE asignado_flag = 1 
                AND subestado = 'ready_to_print'
                AND deposito_asignado IS NOT NULL
                ORDER BY fecha_asignacion ASC
            """)
            
            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'db_id': row[0],
                    'order_id': row[1],
                    'sku': row[2], 
                    'qty': row[3],
                    'deposito': row[4],
                    'fecha_asignacion': row[5],
                    'barcode': row[6]
                })
                
            return orders
    
    def notify_picking_system(self, order: Dict) -> bool:
        """
        Notifica al sistema de picking que hay una orden lista.
        """
        try:
            payload = {
                'order_id': order['order_id'],
                'sku': order['sku'],
                'qty': order['qty'],
                'deposito': order['deposito'],
                'barcode': order['barcode'],
                'fecha_asignacion': order['fecha_asignacion'].isoformat() if order['fecha_asignacion'] else None
            }
            
            response = requests.post(
                f"{self.picking_api_base}/new_order",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Orden {order['order_id']} notificada al sistema de picking")
                return True
            else:
                logger.error(f"Error notificando picking: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error en notificación picking: {e}")
            return False
    
    def handle_picking_completed(self, order_id: str, picker_user: str) -> Dict:
        """
        Maneja la confirmación de picking completado.
        
        FLUJO:
        1. Picking system llama esta función cuando completan el picking
        2. Descarga etiqueta automáticamente 
        3. Actualiza estado a 'printed'
        4. Registra movimiento ML
        """
        try:
            # 1. Verificar que la orden existe y está asignada
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, sku, deposito_asignado, subestado
                    FROM orders_meli 
                    WHERE order_id = ? AND asignado_flag = 1
                """, (order_id,))
                
                order_row = cursor.fetchone()
                
                if not order_row:
                    return {'status': 'error', 'message': f'Orden {order_id} no encontrada o no asignada'}
                
                db_id, sku, deposito, current_status = order_row
                
                if current_status != 'ready_to_print':
                    return {'status': 'warning', 'message': f'Orden {order_id} ya procesada (estado: {current_status})'}
            
            # 2. Descargar etiqueta automáticamente
            label_result = self.download_shipping_label(order_id)
            
            # 3. Actualizar estado con transacción
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION")
                
                try:
                    # Actualizar a 'printed' con información de picking
                    cursor.execute("""
                        UPDATE orders_meli 
                        SET subestado = 'printed',
                            fecha_actualizacion = GETDATE(),
                            observacion_movimiento = CONCAT(
                                ISNULL(observacion_movimiento, ''), 
                                '; Picking completado por: ', ?, ' (', FORMAT(GETDATE(), 'yyyy-MM-dd HH:mm'), ')',
                                CASE WHEN ? = 1 THEN '; Etiqueta descargada' ELSE '; Error descargando etiqueta' END
                            )
                        WHERE id = ?
                    """, (picker_user, 1 if label_result['success'] else 0, db_id))
                    
                    cursor.execute("COMMIT TRANSACTION")
                    
                    logger.info(f"Picking completado para orden {order_id} por {picker_user}")
                    
                    return {
                        'status': 'success',
                        'message': f'Picking completado y estado actualizado a printed',
                        'label_downloaded': label_result['success'],
                        'label_path': label_result.get('file_path')
                    }
                    
                except Exception as e:
                    cursor.execute("ROLLBACK TRANSACTION")
                    raise e
                    
        except Exception as e:
            logger.error(f"Error procesando picking completado: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def download_shipping_label(self, order_id: str) -> Dict:
        """
        Descarga la etiqueta de envío de MercadoLibre automáticamente.
        """
        try:
            # Importar cliente MercadoLibre
            from modules.meli_client import MeliClient
            
            client = MeliClient()
            
            # Obtener información del shipment
            order_data = client.get_order_details(order_id)
            
            if not order_data or 'shipping' not in order_data:
                return {'success': False, 'error': 'No se encontró información de shipping'}
            
            shipping_id = order_data['shipping'].get('id')
            
            if not shipping_id:
                return {'success': False, 'error': 'No se encontró shipping_id'}
            
            # Descargar etiqueta
            label_url = f"https://api.mercadolibre.com/shipments/{shipping_id}/labels"
            
            response = requests.get(
                label_url,
                headers={'Authorization': f'Bearer {client.access_token}'},
                timeout=30
            )
            
            if response.status_code == 200:
                # Guardar etiqueta en archivo
                file_path = f"labels/label_{order_id}_{shipping_id}.pdf"
                
                import os
                os.makedirs('labels', exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Etiqueta descargada: {file_path}")
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'shipping_id': shipping_id
                }
            else:
                return {
                    'success': False,
                    'error': f'Error HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            logger.error(f"Error descargando etiqueta: {e}")
            return {'success': False, 'error': str(e)}

# API endpoints para integración con sistema de picking
def create_picking_api():
    """
    Crea endpoints API para integración con sistema de picking.
    """
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    picking = PickingIntegration()
    
    @app.route('/api/orders/ready_for_picking', methods=['GET'])
    def get_ready_orders():
        """Endpoint para que el sistema de picking obtenga órdenes listas."""
        orders = picking.get_orders_ready_for_picking()
        return jsonify({'orders': orders})
    
    @app.route('/api/picking/completed', methods=['POST'])
    def picking_completed():
        """Endpoint para confirmar picking completado."""
        data = request.json
        order_id = data.get('order_id')
        picker_user = data.get('picker_user', 'unknown')
        
        if not order_id:
            return jsonify({'error': 'order_id requerido'}), 400
        
        result = picking.handle_picking_completed(order_id, picker_user)
        
        if result['status'] == 'success':
            return jsonify(result), 200
        elif result['status'] == 'warning':
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    
    return app

if __name__ == "__main__":
    # Test de integración picking
    picking = PickingIntegration()
    orders = picking.get_orders_ready_for_picking()
    print(f"Órdenes listas para picking: {len(orders)}")
    for order in orders:
        print(f"  {order['order_id']} - {order['sku']} - {order['deposito']}")
