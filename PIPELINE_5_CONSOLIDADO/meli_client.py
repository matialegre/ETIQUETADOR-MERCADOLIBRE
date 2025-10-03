"""
Módulo MercadoLibre Client - Versión Simplificada para Sync
==========================================================

Cliente simplificado para obtener órdenes recientes de MercadoLibre.
"""

import requests
import json
import os
from typing import List, Dict, Optional

def get_recent_orders(limit: int = 10) -> List[Dict]:
    """
    Obtiene órdenes recientes de MercadoLibre.
    Por ahora, devuelve datos mock para testing del sync.
    """
    
    # Mock data para testing - simula respuesta de MercadoLibre
    mock_orders = [
        {
            "id": "2000012577440698",
            "status": "paid",
            "substatus": "printed",  # Cambió de ready_to_print a printed
            "order_items": [
                {
                    "item": {
                        "seller_custom_field": "2027201-CC089-C10"
                    },
                    "quantity": 1
                }
            ],
            "shipping": {
                "status": "ready_to_ship",
                "substatus": "printed"
            },
            "comments": "Cliente pidió envío urgente"
        }
    ]
    
    print(f"[MOCK] Devolviendo {len(mock_orders)} órdenes mock para testing sync")
    return mock_orders[:limit]

def get_order_details(order_id: str) -> Optional[Dict]:
    """
    Obtiene detalles de una orden específica.
    """
    # Mock para testing
    if order_id == "2000012577440698":
        return {
            "id": "2000012577440698",
            "status": "paid",
            "substatus": "printed",
            "shipping": {
                "id": "43857017871",
                "status": "ready_to_ship",
                "substatus": "printed"
            }
        }
    
    return None

if __name__ == "__main__":
    # Test del cliente
    orders = get_recent_orders(5)
    print(f"Órdenes obtenidas: {len(orders)}")
    for order in orders:
        print(f"  {order['id']} - {order['substatus']}")
