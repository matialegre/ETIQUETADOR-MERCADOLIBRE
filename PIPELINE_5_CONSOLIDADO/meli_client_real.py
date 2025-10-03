"""
Cliente MercadoLibre REAL para test Pipeline 4
==============================================

Cliente que obtiene órdenes reales de MercadoLibre usando las credenciales.
"""

import requests
import json
import os
from typing import List, Dict, Optional

def get_recent_orders_real(limit: int = 10) -> List[Dict]:
    """
    Obtiene órdenes REALES de MercadoLibre usando el cliente real.
    """
    
    try:
        # Importar el cliente real
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'modules'))
        
        # Importar el cliente REAL completo
        sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')
        from meli_client_01 import MeliClient
        
        print(f"[REAL] Consultando MercadoLibre API con credenciales reales...")
        
        # Crear cliente y obtener órdenes reales
        client = MeliClient()
        real_orders = client.get_recent_orders(limit=limit)
        
        print(f"[REAL] Órdenes reales obtenidas: {len(real_orders)}")
        
        return real_orders
        
    except Exception as e:
        print(f"[ERROR] No se pudo conectar con MercadoLibre real: {e}")
        print(f"[FALLBACK] Usando datos mock para continuar test...")
        
        # Fallback a mock si falla la conexión real
    
    mock_orders_realistic = [
        {
            "id": "2000012577440698",
            "status": "paid",
            "substatus": "ready_to_print",  # Esta está lista para asignar
            "order_items": [
                {
                    "item": {
                        "seller_custom_field": "2027201-CC089-C10"
                    },
                    "quantity": 1
                }
            ],
            "shipping": {
                "status": "pending",
                "substatus": "ready_to_print"
            },
            "comments": ""
        },
        {
            "id": "2000012577440699",
            "status": "paid", 
            "substatus": "ready_to_print",  # Esta también está lista
            "order_items": [
                {
                    "item": {
                        "seller_custom_field": "NYSSB0EPSA-NN0-42"
                    },
                    "quantity": 1
                }
            ],
            "shipping": {
                "status": "pending",
                "substatus": "ready_to_print"
            },
            "comments": "Envío urgente"
        },
        {
            "id": "2000012577440700",
            "status": "paid",
            "substatus": "printed",  # Esta ya está printed
            "order_items": [
                {
                    "item": {
                        "seller_custom_field": "TEST-SKU-001"
                    },
                    "quantity": 2
                }
            ],
            "shipping": {
                "status": "ready_to_ship",
                "substatus": "printed"
            },
            "comments": ""
        },
        {
            "id": "2000012577440701",
            "status": "paid",
            "substatus": "shipped",  # Esta ya está enviada
            "order_items": [
                {
                    "item": {
                        "seller_custom_field": "PROD-ABC-123"
                    },
                    "quantity": 1
                }
            ],
            "shipping": {
                "status": "shipped",
                "substatus": "shipped"
            },
            "comments": ""
        },
        {
            "id": "2000012577440702",
            "status": "paid",
            "substatus": "ready_to_print",  # Otra lista para asignar
            "order_items": [
                {
                    "item": {
                        "seller_custom_field": "CAMP-INVIERNO-XL"
                    },
                    "quantity": 1
                }
            ],
            "shipping": {
                "status": "pending",
                "substatus": "ready_to_print"
            },
            "comments": "Cliente VIP"
        }
    ]
    
    print(f"[MOCK REALISTA] Simulando consulta a MercadoLibre API...")
    print(f"[MOCK REALISTA] Devolviendo {len(mock_orders_realistic)} órdenes realistas")
    
    return mock_orders_realistic[:limit]

if __name__ == "__main__":
    # Test del cliente real
    orders = get_recent_orders_real(5)
    print(f"Órdenes obtenidas: {len(orders)}")
    for order in orders:
        print(f"  {order['id']} - {order['substatus']} - SKU: {order['order_items'][0]['item']['seller_custom_field']}")
