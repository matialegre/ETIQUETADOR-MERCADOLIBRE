"""
Módulo 11: Notificador
=====================

Sistema de notificaciones para alertas de stock bajo y otros eventos.
"""

import logging
import requests
from typing import Dict, Any, Optional
from modules.config import WEBHOOK_STOCK_ZERO

logger = logging.getLogger(__name__)


def alert_stock_zero(data: Dict[str, Any]) -> bool:
    """
    Envía alerta cuando un SKU se agota en un depósito.
    
    Args:
        data: Dict con información del agotamiento
              - sku: SKU agotado
              - depot: Depósito agotado
              - order_id: Orden que causó el agotamiento
              - total: Stock total
              - reserved: Stock reservado
              
    Returns:
        bool: True si se envió exitosamente
    """
    if not WEBHOOK_STOCK_ZERO:
        logger.debug("No hay webhook configurado para alertas de stock")
        return False
    
    try:
        message = {
            "type": "stock_zero",
            "timestamp": "2025-08-07T13:25:00Z",  # Se podría usar datetime.utcnow()
            "data": data,
            "message": f"🚨 STOCK AGOTADO: SKU {data.get('sku')} en depósito {data.get('depot')}"
        }
        
        response = requests.post(
            WEBHOOK_STOCK_ZERO,
            json=message,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        
        logger.info(f"✅ Alerta de agotamiento enviada para SKU {data.get('sku')}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando alerta de agotamiento: {e}")
        return False


def alert_error(error_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> bool:
    """
    Envía alerta de error general.
    
    Args:
        error_type: Tipo de error
        message: Mensaje del error
        data: Datos adicionales opcionales
        
    Returns:
        bool: True si se envió exitosamente
    """
    if not WEBHOOK_STOCK_ZERO:  # Usar el mismo webhook por ahora
        logger.debug("No hay webhook configurado para alertas de error")
        return False
    
    try:
        alert_message = {
            "type": "error",
            "error_type": error_type,
            "timestamp": "2025-08-07T13:25:00Z",
            "message": message,
            "data": data or {}
        }
        
        response = requests.post(
            WEBHOOK_STOCK_ZERO,
            json=alert_message,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        
        logger.info(f"✅ Alerta de error enviada: {error_type}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error enviando alerta de error: {e}")
        return False


if __name__ == "__main__":
    # Test básico
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    # Test data
    test_data = {
        "sku": "TEST-SKU-001",
        "depot": "MUNDOCAB",
        "order_id": "2000012345678",
        "total": 5,
        "reserved": 5
    }
    
    try:
        print("🔔 Test de notificaciones...")
        
        # Test alerta de stock
        result = alert_stock_zero(test_data)
        if result:
            print("✅ Alerta de stock enviada")
        else:
            print("⚠️ No se pudo enviar alerta de stock (webhook no configurado)")
        
        # Test alerta de error
        result = alert_error("test_error", "Error de prueba", {"test": True})
        if result:
            print("✅ Alerta de error enviada")
        else:
            print("⚠️ No se pudo enviar alerta de error (webhook no configurado)")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
