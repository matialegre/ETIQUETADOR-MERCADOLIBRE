# api/dragonfish_api_caba.py
"""
API de Dragonfish específica para CABA que apunta al servidor remoto en Bahía Blanca.
"""

import requests
from typing import Optional, Dict, Any
from utils.logger import get_logger
import config_caba

log = get_logger(__name__)

class DragonfishAPICaba:
    """Cliente API para Dragonfish remoto en Bahía Blanca."""
    
    def __init__(self):
        self.base_url = config_caba.DRAGONFISH_BASE_URL
        self.session = requests.Session()
        # Configurar timeout para conexiones remotas
        self.session.timeout = 30
        log.info(f"🌐 Dragonfish API CABA inicializada: {self.base_url}")
    
    def test_connection(self) -> bool:
        """Prueba la conexión con el servidor remoto."""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                log.info("✅ Conexión exitosa con servidor Dragonfish remoto")
                return True
            else:
                log.warning(f"⚠️ Servidor responde pero con código: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Error conectando con servidor remoto: {e}")
            return False
    
    def update_stock(self, sku: str, quantity: int, operation: str = "subtract") -> bool:
        """
        Actualiza el stock de un SKU en el servidor remoto.
        
        Args:
            sku: SKU del producto
            quantity: Cantidad a actualizar
            operation: 'subtract' o 'add'
        
        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            endpoint = f"{self.base_url}/stock/update"
            payload = {
                "sku": sku,
                "quantity": quantity,
                "operation": operation,
                "source": "picking_caba",
                "location": config_caba.DEPOSITO_NAME
            }
            
            log.info(f"📦 Actualizando stock remoto: {sku} {operation} {quantity}")
            
            response = self.session.post(endpoint, json=payload, timeout=15)
            
            if response.status_code == 200:
                log.info(f"✅ Stock actualizado exitosamente: {sku}")
                return True
            else:
                log.error(f"❌ Error actualizando stock: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Error de conexión actualizando stock: {e}")
            return False
        except Exception as e:
            log.error(f"❌ Error inesperado actualizando stock: {e}")
            return False
    
    def get_stock(self, sku: str) -> Optional[int]:
        """
        Obtiene el stock actual de un SKU desde el servidor remoto.
        
        Args:
            sku: SKU del producto
            
        Returns:
            int: Cantidad en stock, o None si hay error
        """
        try:
            endpoint = f"{self.base_url}/stock/{sku}"
            
            response = self.session.get(endpoint, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                stock = data.get('quantity', 0)
                log.debug(f"📊 Stock de {sku}: {stock}")
                return stock
            else:
                log.warning(f"⚠️ No se pudo obtener stock de {sku}: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Error obteniendo stock: {e}")
            return None
        except Exception as e:
            log.error(f"❌ Error inesperado obteniendo stock: {e}")
            return None
    
    def log_picking_activity(self, order_id: str, sku: str, quantity: int, user: str = "caba_user") -> bool:
        """
        Registra actividad de picking en el servidor remoto.
        
        Args:
            order_id: ID de la orden
            sku: SKU del producto
            quantity: Cantidad pickeada
            user: Usuario que realizó el picking
            
        Returns:
            bool: True si el registro fue exitoso
        """
        try:
            endpoint = f"{self.base_url}/picking/log"
            payload = {
                "order_id": order_id,
                "sku": sku,
                "quantity": quantity,
                "user": user,
                "location": config_caba.DEPOSITO_NAME,
                "timestamp": None  # El servidor asignará timestamp
            }
            
            response = self.session.post(endpoint, json=payload, timeout=10)
            
            if response.status_code == 200:
                log.debug(f"📝 Actividad de picking registrada: {order_id} - {sku}")
                return True
            else:
                log.warning(f"⚠️ No se pudo registrar picking: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            log.error(f"❌ Error registrando picking: {e}")
            return False
        except Exception as e:
            log.error(f"❌ Error inesperado registrando picking: {e}")
            return False

# Instancia global para usar en toda la aplicación CABA
dragonfish_caba = DragonfishAPICaba()

# Funciones de compatibilidad con la API original
def update_stock_caba(sku: str, quantity: int) -> bool:
    """Función de compatibilidad para actualizar stock."""
    return dragonfish_caba.update_stock(sku, quantity, "subtract")

def get_stock_caba(sku: str) -> Optional[int]:
    """Función de compatibilidad para obtener stock."""
    return dragonfish_caba.get_stock(sku)

def test_connection_caba() -> bool:
    """Función de compatibilidad para probar conexión."""
    return dragonfish_caba.test_connection()
