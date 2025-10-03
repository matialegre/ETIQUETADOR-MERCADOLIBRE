"""
PASO 03: Integración Avanzada Dragonfish/Stock
==============================================

Módulo para sincronización avanzada de stock con Dragonfish API:
1. Consultar stock disponible por depósito
2. Actualizar inventarios y movimientos automáticamente
3. Manejar asignación de órdenes por prioridad y stock
4. Integración completa con MercadoLibre pipeline

Funciones principales:
- get_stock_by_sku(sku: str, deposito: str = None) -> dict
- update_stock_movement(sku: str, qty: int, tipo: str, motivo: str) -> bool
- assign_orders_by_stock_priority() -> dict
- sync_ml_orders_with_stock() -> dict

Autor: Sistema meli_dragon_pipeline
Fecha: 2025-01-07
"""

import pyodbc
import requests
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Configuración
MELI_STOCK_CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
DRAGON_CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=ranchoaspen\\zoo2025;DATABASE=dragonfish_deposito;Trusted_Connection=yes;'

class DragonfishStockManager:
    """Gestor avanzado de stock con Dragonfish API."""
    
    def __init__(self):
        self.meli_conn_str = MELI_STOCK_CONN_STR
        self.dragon_conn_str = DRAGON_CONN_STR
        
        # Cargar configuración de Dragonfish API
        self.config = self._load_dragonfish_config()
        self.api_base_url = self.config.get('base_url', 'http://localhost:3000/api/ConsultaStockYPreciosEntreLocales/')
        self.client_id = self.config.get('client_id', 'TU_CLIENT_ID')
        self.token = self.config.get('token', 'TU_TOKEN')
        self.timeout = self.config.get('timeout', 120)  # Aumentar a 2 minutos por intento
    
    def _load_dragonfish_config(self) -> Dict:
        """Cargar configuración de Dragonfish API desde archivo JSON."""
        try:
            config_path = Path('dragonfish_config.json')
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                return config_data.get('dragonfish_api', {})
            else:
                print("⚠️ Archivo dragonfish_config.json no encontrado, usando valores por defecto")
                return {}
        except Exception as e:
            print(f"❌ Error cargando configuración Dragonfish: {e}")
            return {}
        
    def get_stock_by_sku(self, sku: str, deposito: str = None) -> Dict:
        """
        Obtener stock disponible por SKU desde Dragonfish API.
        
        Args:
            sku: SKU del producto (formato ART-COLOR-TALLE)
            deposito: Depósito específico (opcional)
            
        Returns:
            dict: Información completa de stock
        """
        try:
            # Validar formato SKU
            if '-' not in sku or len(sku.split('-')) < 3:
                return {"error": f"SKU inválido: {sku}"}
            
            # Extraer solo el artículo para la consulta API
            art, *_ = sku.split("-", 2)
            
            # Headers para la API Dragonfish
            headers = {
                "accept": "application/json",
                "IdCliente": self.client_id,
                "Authorization": self.token
            }
            
            # Llamar API Dragonfish con reintentos
            max_retries = 3
            retry_delay = 60  # 1 minuto entre reintentos
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 Intento {attempt + 1}/{max_retries} - Consultando API Dragonfish...")
                    
                    response = requests.get(
                        self.api_base_url,
                        params={"query": art},
                        headers=headers,
                        timeout=self.timeout
                    )
                    
                    # Si llegamos aquí, la llamada fue exitosa
                    break
                    
                except requests.exceptions.Timeout as e:
                    print(f"⏰ Timeout en intento {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        print(f"⏳ Esperando {retry_delay} segundos antes del siguiente intento...")
                        import time
                        time.sleep(retry_delay)
                    else:
                        print(f"❌ Todos los intentos fallaron por timeout")
                        return {
                            "sku": sku,
                            "found": False,
                            "error": f"Timeout después de {max_retries} intentos",
                            "stock_total": 0,
                            "depositos": []
                        }
                        
                except requests.exceptions.RequestException as e:
                    print(f"❌ Error de conexión en intento {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        print(f"⏳ Esperando {retry_delay} segundos antes del siguiente intento...")
                        import time
                        time.sleep(retry_delay)
                    else:
                        print(f"❌ Todos los intentos fallaron por error de conexión")
                        return {
                            "sku": sku,
                            "found": False,
                            "error": f"Error de conexión después de {max_retries} intentos: {str(e)}",
                            "stock_total": 0,
                            "depositos": []
                        }
            
            if response.status_code != 200:
                return {
                    "sku": sku,
                    "found": False,
                    "error": f"API Error: {response.status_code}",
                    "stock_total": 0,
                    "depositos": []
                }
            
            data = response.json()
            depositos = []
            stock_total = 0
            
            print(f"🔍 API Response para {sku}: {len(data.get('Resultados', []))} resultados")
            
            # Procesar resultados filtrando por SKU exacto
            for fila in data.get("Resultados", []):
                # Construir SKU completo para comparación exacta
                sku_completo = f"{fila['Articulo']}-{fila['Color']}-{fila['Talle']}"
                
                if sku_completo != sku:
                    continue  # Solo procesar el SKU exacto
                
                print(f"✅ SKU COINCIDE: {sku_completo}")
                
                # Procesar stock por depósito
                for st in fila.get("Stock", []):
                    depot = st["BaseDeDatos"].strip().upper()
                    stock_qty = int(st["Stock"])
                    
                    # Filtrar por depósito específico si se solicita
                    if deposito and depot != deposito.upper():
                        continue
                    
                    if stock_qty > 0:  # Solo incluir depósitos con stock
                        deposito_info = {
                            "deposito": depot,
                            "stock_actual": stock_qty,
                            "stock_reservado": 0,  # API no proporciona reservado
                            "stock_disponible": stock_qty,
                            "precio": 0.0,  # Agregar si API lo proporciona
                            "fecha_actualizacion": None
                        }
                        
                        depositos.append(deposito_info)
                        stock_total += stock_qty
                        
                        print(f"✅ AGREGADO: {depot} con {stock_qty} unidades")
            
            if not depositos:
                return {
                    "sku": sku,
                    "found": False,
                    "stock_total": 0,
                    "depositos": []
                }
            
            return {
                "sku": sku,
                "articulo": art,
                "found": True,
                "stock_total": stock_total,
                "depositos": depositos,
                "depositos_count": len(depositos)
            }
            
        except Exception as e:
            print(f"❌ Error consultando stock API: {e}")
            return {
                "sku": sku,
                "found": False,
                "error": str(e),
                "stock_total": 0,
                "depositos": []
            }
    
    def update_stock_movement(self, sku: str, qty: int, tipo: str, motivo: str, deposito: str = None) -> bool:
        """
        Registrar movimiento de stock en Dragonfish.
        
        Args:
            sku: SKU del producto
            qty: Cantidad (positiva para entrada, negativa para salida)
            tipo: Tipo de movimiento (VENTA, AJUSTE, DEVOLUCION, etc.)
            motivo: Motivo del movimiento
            deposito: Depósito específico
            
        Returns:
            bool: True si el movimiento fue exitoso
        """
        try:
            if '-' in sku and len(sku.split('-')) >= 3:
                art, col, tal = sku.split('-', 2)
            else:
                print(f"❌ SKU inválido para movimiento: {sku}")
                return False
            
            connection = pyodbc.connect(self.dragon_conn_str)
            cursor = connection.cursor()
            
            # Obtener depósito por defecto si no se especifica
            if not deposito:
                cursor.execute("""
                    SELECT TOP 1 RTRIM(CDEPOSIT) 
                    FROM dragonfish_deposito.ZooLogic.STOCKS 
                    WHERE RTRIM(CARTICUL) = ? AND RTRIM(CCOLOR) = ? AND RTRIM(CTALLE) = ?
                    AND NSTOCK > 0
                    ORDER BY NSTOCK DESC
                """, (art, col, tal))
                
                deposito_row = cursor.fetchone()
                if deposito_row:
                    deposito = deposito_row[0]
                else:
                    print(f"❌ No se encontró depósito para SKU: {sku}")
                    connection.close()
                    return False
            
            # Registrar movimiento en tabla de movimientos (si existe)
            try:
                cursor.execute("""
                    INSERT INTO dragonfish_deposito.ZooLogic.MOVIMIENTOS (
                        CARTICUL, CCOLOR, CTALLE, CDEPOSIT, CANTIDAD, 
                        TIPO_MOV, MOTIVO, FECHA_MOV, USUARIO
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE(), 'MELI_PIPELINE')
                """, (art, col, tal, deposito, qty, tipo, motivo))
                
                print(f"✅ Movimiento registrado: {sku} ({qty}) - {tipo}")
                
            except Exception as mov_error:
                print(f"⚠️ No se pudo registrar en tabla movimientos: {mov_error}")
            
            # Actualizar stock actual
            if qty < 0:  # Salida de stock
                cursor.execute("""
                    UPDATE dragonfish_deposito.ZooLogic.STOCKS 
                    SET NRESERVA = NRESERVA + ?,
                        DFECHA = GETDATE()
                    WHERE RTRIM(CARTICUL) = ? AND RTRIM(CCOLOR) = ? 
                    AND RTRIM(CTALLE) = ? AND RTRIM(CDEPOSIT) = ?
                """, (abs(qty), art, col, tal, deposito))
                
            else:  # Entrada de stock
                cursor.execute("""
                    UPDATE dragonfish_deposito.ZooLogic.STOCKS 
                    SET NSTOCK = NSTOCK + ?,
                        DFECHA = GETDATE()
                    WHERE RTRIM(CARTICUL) = ? AND RTRIM(CCOLOR) = ? 
                    AND RTRIM(CTALLE) = ? AND RTRIM(CDEPOSIT) = ?
                """, (qty, art, col, tal, deposito))
            
            affected_rows = cursor.rowcount
            
            if affected_rows > 0:
                connection.commit()
                connection.close()
                print(f"✅ Stock actualizado: {sku} en {deposito}")
                return True
            else:
                print(f"❌ No se encontró registro para actualizar: {sku}")
                connection.close()
                return False
                
        except Exception as e:
            print(f"❌ Error en movimiento de stock: {e}")
            return False
    
    def get_orders_pending_stock_assignment(self) -> List[Dict]:
        """Obtener órdenes pendientes de asignación de stock."""
        try:
            connection = pyodbc.connect(self.meli_conn_str)
            cursor = connection.cursor()
            
            query = """
            SELECT order_id, sku, qty, shipping_estado, deposito_asignado,
                   stock_real, stock_reservado, asignado_flag, fecha_orden
            FROM orders_meli 
            WHERE asignado_flag = 0 
            AND shipping_estado IN ('nuevo', 'ready_to_print', 'printed')
            AND sku IS NOT NULL
            ORDER BY fecha_orden ASC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            connection.close()
            
            orders = []
            for row in rows:
                orders.append({
                    'order_id': row[0],
                    'sku': row[1],
                    'qty': row[2] or 1,
                    'shipping_estado': row[3],
                    'deposito_asignado': row[4],
                    'stock_real': row[5] or 0,
                    'stock_reservado': row[6] or 0,
                    'asignado_flag': bool(row[7]),
                    'fecha_orden': row[8]
                })
            
            return orders
            
        except Exception as e:
            print(f"❌ Error obteniendo órdenes pendientes: {e}")
            return []
    
    def assign_orders_by_stock_priority(self) -> Dict:
        """
        Asignar órdenes por prioridad de stock disponible.
        
        Returns:
            dict: Resultado de la asignación
        """
        print("🎯 INICIANDO ASIGNACIÓN POR PRIORIDAD DE STOCK")
        print("=" * 50)
        
        # Obtener órdenes pendientes
        pending_orders = self.get_orders_pending_stock_assignment()
        
        if not pending_orders:
            print("✅ No hay órdenes pendientes de asignación")
            return {"orders_processed": 0, "assignments": []}
        
        print(f"📋 Órdenes pendientes: {len(pending_orders)}")
        
        assignments = []
        orders_processed = 0
        
        for order in pending_orders:
            order_id = order['order_id']
            sku = order['sku']
            qty_needed = order['qty']
            
            print(f"\n🔍 Procesando orden: {order_id}")
            print(f"   📦 SKU: {sku}")
            print(f"   🔢 Cantidad: {qty_needed}")
            
            # Obtener stock disponible
            stock_info = self.get_stock_by_sku(sku)
            
            if not stock_info['found']:
                print(f"   ❌ SKU no encontrado en stock")
                assignments.append({
                    'order_id': order_id,
                    'sku': sku,
                    'status': 'sku_not_found',
                    'deposito': None,
                    'stock_available': 0
                })
                continue
            
            # Buscar depósito con stock suficiente
            best_deposito = None
            for deposito_info in stock_info['depositos']:
                if deposito_info['stock_disponible'] >= qty_needed:
                    best_deposito = deposito_info
                    break
            
            if not best_deposito:
                print(f"   ⚠️ Stock insuficiente (disponible: {stock_info['stock_total']})")
                assignments.append({
                    'order_id': order_id,
                    'sku': sku,
                    'status': 'insufficient_stock',
                    'deposito': None,
                    'stock_available': stock_info['stock_total']
                })
                continue
            
            # Asignar orden al depósito
            deposito_asignado = best_deposito['deposito']
            
            success = self._assign_order_to_deposito(
                order_id, sku, qty_needed, deposito_asignado
            )
            
            if success:
                # Registrar movimiento de stock
                self.update_stock_movement(
                    sku, -qty_needed, "VENTA", 
                    f"Orden MercadoLibre {order_id}", deposito_asignado
                )
                
                print(f"   ✅ Asignado a depósito: {deposito_asignado}")
                assignments.append({
                    'order_id': order_id,
                    'sku': sku,
                    'status': 'assigned',
                    'deposito': deposito_asignado,
                    'stock_available': best_deposito['stock_disponible']
                })
                orders_processed += 1
            else:
                print(f"   ❌ Error en asignación")
                assignments.append({
                    'order_id': order_id,
                    'sku': sku,
                    'status': 'assignment_error',
                    'deposito': deposito_asignado,
                    'stock_available': best_deposito['stock_disponible']
                })
        
        print(f"\n📊 RESUMEN DE ASIGNACIÓN:")
        print(f"   📋 Órdenes procesadas: {orders_processed}")
        print(f"   ✅ Asignaciones exitosas: {len([a for a in assignments if a['status'] == 'assigned'])}")
        print(f"   ❌ Errores: {len([a for a in assignments if a['status'] != 'assigned'])}")
        
        return {
            "orders_processed": orders_processed,
            "assignments": assignments,
            "summary": {
                "total": len(pending_orders),
                "assigned": len([a for a in assignments if a['status'] == 'assigned']),
                "errors": len([a for a in assignments if a['status'] != 'assigned'])
            }
        }
    
    def _assign_order_to_deposito(self, order_id: str, sku: str, qty: int, deposito: str) -> bool:
        """Asignar orden específica a un depósito."""
        try:
            connection = pyodbc.connect(self.meli_conn_str)
            cursor = connection.cursor()
            
            cursor.execute("""
                UPDATE orders_meli 
                SET deposito_asignado = ?,
                    stock_reservado = ?,
                    asignado_flag = 1,
                    last_update = GETDATE()
                WHERE order_id = ?
            """, (deposito, qty, order_id))
            
            affected = cursor.rowcount
            connection.commit()
            connection.close()
            
            return affected > 0
            
        except Exception as e:
            print(f"❌ Error asignando orden {order_id}: {e}")
            return False
    
    def sync_ml_orders_with_stock(self) -> Dict:
        """
        Sincronización completa de órdenes ML con stock Dragonfish.
        
        Returns:
            dict: Resultado de la sincronización
        """
        print("🔄 SINCRONIZACIÓN COMPLETA ML ↔ DRAGONFISH")
        print("=" * 50)
        
        # 1. Asignar órdenes por prioridad de stock
        assignment_result = self.assign_orders_by_stock_priority()
        
        # 2. Verificar stock de órdenes ya asignadas
        verification_result = self._verify_assigned_orders_stock()
        
        # 3. Generar reporte de stock crítico
        critical_stock_report = self._generate_critical_stock_report()
        
        return {
            "assignment": assignment_result,
            "verification": verification_result,
            "critical_stock": critical_stock_report,
            "sync_timestamp": datetime.now().isoformat()
        }
    
    def _verify_assigned_orders_stock(self) -> Dict:
        """Verificar stock de órdenes ya asignadas."""
        try:
            connection = pyodbc.connect(self.meli_conn_str)
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT order_id, sku, qty, deposito_asignado, stock_reservado
                FROM orders_meli 
                WHERE asignado_flag = 1 
                AND shipping_estado IN ('ready_to_print', 'printed', 'ready_to_ship')
            """)
            
            assigned_orders = cursor.fetchall()
            connection.close()
            
            verification_results = []
            
            for order in assigned_orders:
                order_id, sku, qty, deposito, stock_reservado = order
                
                # Verificar stock actual
                stock_info = self.get_stock_by_sku(sku, deposito)
                
                if stock_info['found'] and stock_info['depositos']:
                    current_stock = stock_info['depositos'][0]['stock_disponible']
                    
                    verification_results.append({
                        'order_id': order_id,
                        'sku': sku,
                        'deposito': deposito,
                        'qty_needed': qty,
                        'stock_reserved': stock_reservado,
                        'stock_current': current_stock,
                        'status': 'ok' if current_stock >= qty else 'insufficient'
                    })
                else:
                    verification_results.append({
                        'order_id': order_id,
                        'sku': sku,
                        'deposito': deposito,
                        'qty_needed': qty,
                        'stock_reserved': stock_reservado,
                        'stock_current': 0,
                        'status': 'not_found'
                    })
            
            return {
                "orders_verified": len(verification_results),
                "results": verification_results
            }
            
        except Exception as e:
            print(f"❌ Error verificando órdenes asignadas: {e}")
            return {"orders_verified": 0, "results": []}
    
    def _generate_critical_stock_report(self) -> Dict:
        """Generar reporte de stock crítico."""
        try:
            # Obtener SKUs únicos de órdenes activas
            connection = pyodbc.connect(self.meli_conn_str)
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT DISTINCT sku, COUNT(*) as orden_count
                FROM orders_meli 
                WHERE shipping_estado IN ('nuevo', 'ready_to_print', 'printed', 'ready_to_ship')
                AND sku IS NOT NULL
                GROUP BY sku
                ORDER BY orden_count DESC
            """)
            
            active_skus = cursor.fetchall()
            connection.close()
            
            critical_items = []
            
            for sku_row in active_skus:
                sku, order_count = sku_row
                
                stock_info = self.get_stock_by_sku(sku)
                
                if stock_info['found']:
                    total_stock = stock_info['stock_total']
                    
                    # Considerar crítico si stock < órdenes pendientes * 2
                    is_critical = total_stock < (order_count * 2)
                    
                    if is_critical or total_stock <= 5:
                        critical_items.append({
                            'sku': sku,
                            'descripcion': stock_info.get('descripcion', 'N/A'),
                            'orders_pending': order_count,
                            'stock_total': total_stock,
                            'criticality': 'high' if total_stock < order_count else 'medium'
                        })
            
            return {
                "critical_items_count": len(critical_items),
                "critical_items": critical_items
            }
            
        except Exception as e:
            print(f"❌ Error generando reporte crítico: {e}")
            return {"critical_items_count": 0, "critical_items": []}

def main():
    """Función principal para testing del módulo."""
    print("🚀 TESTING DRAGONFISH STOCK MANAGER")
    print("=" * 50)
    
    manager = DragonfishStockManager()
    
    # Test 1: Consultar stock de un SKU
    print("\n🔍 TEST 1: Consultar stock por SKU")
    test_sku = "NYS8BESPANNH0-42"  # SKU de ejemplo
    stock_result = manager.get_stock_by_sku(test_sku)
    
    print(f"📋 Resultado de consulta: {stock_result}")
    
    if stock_result.get('found', False):
        print(f"✅ SKU encontrado: {test_sku}")
        print(f"   📦 Descripción: {stock_result.get('descripcion', 'N/A')}")
        print(f"   📊 Stock total: {stock_result.get('stock_total', 0)}")
        print(f"   🏪 Depósitos: {stock_result.get('depositos_count', 0)}")
    elif 'error' in stock_result:
        print(f"❌ Error en consulta: {stock_result['error']}")
    else:
        print(f"❌ SKU no encontrado: {test_sku}")
    
    # Test 2: Asignación por prioridad
    print("\n🎯 TEST 2: Asignación por prioridad de stock")
    assignment_result = manager.assign_orders_by_stock_priority()
    
    # Test 3: Sincronización completa
    print("\n🔄 TEST 3: Sincronización completa")
    sync_result = manager.sync_ml_orders_with_stock()
    
    print(f"\n🎉 Testing completado!")

if __name__ == "__main__":
    main()
