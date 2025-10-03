"""
PASO 11: API Robusta para Picking - PIPELINE 4
==============================================

API Flask con WebSockets para múltiples programas de picking conectados.
Diseñada para IP pública y múltiples clientes simultáneos.
"""

import json
import logging
import pyodbc
from datetime import datetime
from typing import Set
from flask import Flask, request, jsonify
from flask_sock import Sock

# Configurar logging JSON
logging.basicConfig(format='%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear app Flask con WebSockets
app = Flask(__name__)
sock = Sock(app)

# Set global de clientes WebSocket conectados
clients: Set = set()

# Connection string para BD
CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'

def log_json(event_type: str, data: dict):
    """Log estructurado en formato JSON."""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event': event_type,
        'data': data
    }
    logger.info(json.dumps(log_entry))

def broadcast(msg: dict):
    """
    Broadcast mensaje a todos los clientes WebSocket conectados.
    Limpia conexiones muertas automáticamente.
    """
    dead = []
    for c in clients:
        try:
            c.send(json.dumps(msg))
        except:
            dead.append(c)
    
    # Limpiar conexiones muertas
    for d in dead:
        clients.discard(d)
    
    log_json('websocket_broadcast', {
        'message': msg,
        'clients_sent': len(clients) - len(dead),
        'dead_connections': len(dead)
    })

# ===== ENDPOINTS API =====

@app.route('/health', methods=['GET'])
def health_check():
    """Health check para monitoreo."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'connected_clients': len(clients)
    })

@app.route('/api/orders/ready_for_picking', methods=['GET'])
def get_orders_ready_for_picking():
    """
    Obtiene órdenes listas para picking.
    Para que los programas de picking consulten qué hay disponible.
    """
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT order_id, sku, qty, deposito_asignado, barcode,
                       fecha_asignacion, producto_titulo
                FROM orders_meli 
                WHERE asignado_flag = 1 
                AND subestado = 'ready_to_print'
                AND deposito_asignado IS NOT NULL
                ORDER BY fecha_asignacion ASC
            """)
            
            orders = []
            for row in cursor.fetchall():
                orders.append({
                    'order_id': row[0],
                    'sku': row[1],
                    'qty': row[2],
                    'deposito': row[3],
                    'barcode': row[4],
                    'fecha_asignacion': row[5].isoformat() if row[5] else None,
                    'producto': row[6]
                })
        
        log_json('api_orders_ready', {
            'count': len(orders),
            'orders': [o['order_id'] for o in orders]
        })
        
        return jsonify({
            'status': 'success',
            'orders': orders,
            'count': len(orders)
        })
        
    except Exception as e:
        log_json('api_error', {
            'endpoint': '/api/orders/ready_for_picking',
            'error': str(e)
        })
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/orders/<order_id>/details', methods=['GET'])
def get_order_details(order_id: str):
    """
    Obtiene detalles completos de una orden específica.
    """
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT order_id, sku, qty, deposito_asignado, barcode,
                       producto_titulo, precio, estado, subestado,
                       shipping_estado, shipping_subestado, nota,
                       fecha_asignacion, observacion_movimiento
                FROM orders_meli 
                WHERE order_id = ?
            """, (order_id,))
            
            row = cursor.fetchone()
            
            if not row:
                return jsonify({'status': 'error', 'message': 'Orden no encontrada'}), 404
            
            order_details = {
                'order_id': row[0],
                'sku': row[1],
                'qty': row[2],
                'deposito': row[3],
                'barcode': row[4],
                'producto': row[5],
                'precio': float(row[6]) if row[6] else 0,
                'estado': row[7],
                'subestado': row[8],
                'shipping_estado': row[9],
                'shipping_subestado': row[10],
                'nota': row[11],
                'fecha_asignacion': row[12].isoformat() if row[12] else None,
                'observaciones': row[13]
            }
        
        log_json('api_order_details', {
            'order_id': order_id,
            'found': True
        })
        
        return jsonify({
            'status': 'success',
            'order': order_details
        })
        
    except Exception as e:
        log_json('api_error', {
            'endpoint': f'/api/orders/{order_id}/details',
            'error': str(e)
        })
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/pick/confirm', methods=['POST'])
def pick_confirm():
    """
    Confirma que se completó el picking de una orden.
    Cambia el subestado a 'printed' y notifica a todos los clientes.
    """
    try:
        data = request.get_json(force=True)
        order_id = data.get("order_id")
        picker_user = data.get("picker_user", "unknown")
        notes = data.get("notes", "")
        
        if not order_id:
            return jsonify({'status': 'error', 'message': 'order_id requerido'}), 400
        
        log_json('pick_confirm_request', {
            'order_id': order_id,
            'picker_user': picker_user,
            'notes': notes
        })
        
        # Actualizar en base de datos con transacción
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            try:
                # Verificar que la orden existe y está asignada
                cursor.execute("""
                    SELECT id, sku, deposito_asignado, subestado
                    FROM orders_meli 
                    WHERE order_id = ? AND asignado_flag = 1
                """, (order_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    cursor.execute("ROLLBACK TRANSACTION")
                    return jsonify({
                        'status': 'error', 
                        'message': f'Orden {order_id} no encontrada o no asignada'
                    }), 404
                
                db_id, sku, deposito, current_subestado = row
                
                if current_subestado == 'printed':
                    cursor.execute("ROLLBACK TRANSACTION")
                    return jsonify({
                        'status': 'warning',
                        'message': f'Orden {order_id} ya fue procesada'
                    }), 200
                
                # Actualizar a 'printed'
                pick_observation = f"Picking completado por {picker_user} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
                if notes:
                    pick_observation += f" - Notas: {notes}"
                
                cursor.execute("""
                    UPDATE orders_meli 
                    SET subestado = 'printed',
                        fecha_actualizacion = GETDATE(),
                        observacion_movimiento = CONCAT(
                            ISNULL(observacion_movimiento, ''), 
                            '; ', ?
                        )
                    WHERE id = ?
                """, (pick_observation, db_id))
                
                cursor.execute("COMMIT TRANSACTION")
                
                # Broadcast a todos los clientes WebSocket
                broadcast({
                    "type": "orders.printed",
                    "order_id": order_id,
                    "sku": sku,
                    "deposito": deposito,
                    "picker_user": picker_user,
                    "timestamp": datetime.now().isoformat()
                })
                
                log_json('pick_confirm_success', {
                    'order_id': order_id,
                    'sku': sku,
                    'deposito': deposito,
                    'picker_user': picker_user
                })
                
                return jsonify({
                    'status': 'success',
                    'message': f'Orden {order_id} marcada como printed',
                    'order_id': order_id,
                    'sku': sku,
                    'deposito': deposito
                })
                
            except Exception as e:
                cursor.execute("ROLLBACK TRANSACTION")
                raise e
        
    except Exception as e:
        log_json('pick_confirm_error', {
            'order_id': data.get("order_id") if 'data' in locals() else 'unknown',
            'error': str(e)
        })
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/pick/bulk_confirm', methods=['POST'])
def bulk_pick_confirm():
    """
    Confirma múltiples órdenes de picking en una sola llamada.
    Para eficiencia cuando se procesan muchas órdenes juntas.
    """
    try:
        data = request.get_json(force=True)
        order_ids = data.get("order_ids", [])
        picker_user = data.get("picker_user", "unknown")
        
        if not order_ids or not isinstance(order_ids, list):
            return jsonify({'status': 'error', 'message': 'order_ids (array) requerido'}), 400
        
        log_json('bulk_pick_confirm_request', {
            'order_ids': order_ids,
            'picker_user': picker_user,
            'count': len(order_ids)
        })
        
        processed = []
        errors = []
        
        for order_id in order_ids:
            try:
                # Reutilizar lógica de pick_confirm individual
                result = process_single_pick_confirm(order_id, picker_user)
                if result['success']:
                    processed.append(order_id)
                else:
                    errors.append({'order_id': order_id, 'error': result['error']})
            except Exception as e:
                errors.append({'order_id': order_id, 'error': str(e)})
        
        log_json('bulk_pick_confirm_result', {
            'processed': len(processed),
            'errors': len(errors),
            'processed_orders': processed
        })
        
        return jsonify({
            'status': 'success',
            'processed': processed,
            'errors': errors,
            'total_processed': len(processed),
            'total_errors': len(errors)
        })
        
    except Exception as e:
        log_json('bulk_pick_confirm_error', {
            'error': str(e)
        })
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_single_pick_confirm(order_id: str, picker_user: str) -> dict:
    """Procesa una confirmación de picking individual (para bulk)."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            try:
                cursor.execute("""
                    SELECT id FROM orders_meli 
                    WHERE order_id = ? AND asignado_flag = 1 AND subestado = 'ready_to_print'
                """, (order_id,))
                
                row = cursor.fetchone()
                
                if not row:
                    cursor.execute("ROLLBACK TRANSACTION")
                    return {'success': False, 'error': 'Orden no encontrada o ya procesada'}
                
                db_id = row[0]
                
                cursor.execute("""
                    UPDATE orders_meli 
                    SET subestado = 'printed',
                        fecha_actualizacion = GETDATE()
                    WHERE id = ?
                """, (db_id,))
                
                cursor.execute("COMMIT TRANSACTION")
                
                return {'success': True}
                
            except Exception as e:
                cursor.execute("ROLLBACK TRANSACTION")
                return {'success': False, 'error': str(e)}
                
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ===== WEBSOCKET =====

@sock.route("/events/ws")
def websocket_events(ws):
    """
    WebSocket endpoint para eventos en tiempo real.
    Los clientes se conectan aquí para recibir notificaciones.
    """
    clients.add(ws)
    
    log_json('websocket_connect', {
        'total_clients': len(clients)
    })
    
    try:
        # Enviar mensaje de bienvenida
        ws.send(json.dumps({
            'type': 'connection.established',
            'timestamp': datetime.now().isoformat(),
            'message': 'Conectado al sistema de picking'
        }))
        
        # Mantener conexión viva
        while True:
            message = ws.receive()
            
            # Echo de mensajes de ping/pong para keep-alive
            if message:
                try:
                    data = json.loads(message)
                    if data.get('type') == 'ping':
                        ws.send(json.dumps({
                            'type': 'pong',
                            'timestamp': datetime.now().isoformat()
                        }))
                except:
                    pass
                    
    except Exception as e:
        log_json('websocket_error', {
            'error': str(e)
        })
    finally:
        clients.discard(ws)
        log_json('websocket_disconnect', {
            'total_clients': len(clients)
        })

# ===== ESTADÍSTICAS =====

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Estadísticas del sistema para monitoreo."""
    try:
        with pyodbc.connect(CONN_STR) as conn:
            cursor = conn.cursor()
            
            # Órdenes por estado
            cursor.execute("""
                SELECT subestado, COUNT(*) as count
                FROM orders_meli 
                WHERE asignado_flag = 1
                GROUP BY subestado
            """)
            
            status_counts = {}
            for row in cursor.fetchall():
                status_counts[row[0]] = row[1]
            
            # Órdenes por depósito
            cursor.execute("""
                SELECT deposito_asignado, COUNT(*) as count
                FROM orders_meli 
                WHERE asignado_flag = 1
                GROUP BY deposito_asignado
            """)
            
            deposit_counts = {}
            for row in cursor.fetchall():
                deposit_counts[row[0] or 'sin_asignar'] = row[1]
        
        return jsonify({
            'status': 'success',
            'connected_clients': len(clients),
            'orders_by_status': status_counts,
            'orders_by_deposit': deposit_counts,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    print("🔥 INICIANDO API ROBUSTA PARA PICKING - PIPELINE 4")
    print("=" * 60)
    print("Endpoints disponibles:")
    print("  GET  /health")
    print("  GET  /api/orders/ready_for_picking")
    print("  GET  /api/orders/<order_id>/details")
    print("  POST /api/pick/confirm")
    print("  POST /api/pick/bulk_confirm")
    print("  GET  /api/stats")
    print("  WS   /events/ws")
    print("=" * 60)
    
    # Ejecutar en todas las interfaces para IP pública
    app.run(host='0.0.0.0', port=5000, debug=False)
