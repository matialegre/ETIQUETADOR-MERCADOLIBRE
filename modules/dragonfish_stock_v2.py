"""
Modulo Dragonfish Stock V2 - VERSION QUE FUNCIONA
=================================================

Basado en el codigo de VERSION 2 que ya probamos y funciona.
"""

import requests
import time
import logging

logger = logging.getLogger(__name__)

# Mapeo de depósitos para normalizar nombres
DEPOSIT_MAP = {
    'DEPOSITO': 'DEP',
    'DEP': 'DEP',
    'MUNDOAL': 'MUNDOAL',
    'MUNDOCAB': 'MUNDOCAB', 
    'MUNDOROC': 'MUNDOROC',
    'MONBAHIA': 'MONBAHIA',
    'MTGBBPS': 'MTGBBPS',
    'MTGROCA': 'MTGROCA',
    'NQNSHOP': 'NQNSHOP',
    'MTGCOM': 'MTGCOM'
}

class DragonfishStockManager:
    def __init__(self):
        # Configuracion que sabemos que funciona (de VERSION 2)
        self.api_base_url = 'http://deposito_2:8009/api/ConsultaStockYPreciosEntreLocales/'
        self.timeout = 120  # 2 minutos
        
    def get_stock_by_sku(self, sku, max_retries=3, retry_delay=60):
        """
        Consulta stock con reintentos - VERSION QUE FUNCIONA.
        """
        for attempt in range(max_retries):
            try:
                print(f"Intento {attempt + 1}/{max_retries} - Consultando API Dragonfish...")
                
                # Hacer la consulta como en VERSION 2
                response = requests.get(
                    self.api_base_url,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"API Response para {sku}: {len(data)} resultados")
                    
                    # Procesar respuesta como en VERSION 2
                    stock_by_deposit = {}
                    
                    for item in data:
                        item_sku = item.get('sku', '')
                        
                        # Buscar coincidencia exacta del SKU
                        if item_sku == sku:
                            deposit = item.get('deposito', 'UNKNOWN')
                            stock = item.get('stock', 0)
                            
                            if stock > 0:
                                stock_by_deposit[deposit] = {'stock': stock}
                                print(f"AGREGADO: {deposit} con {stock} unidades")
                    
                    if stock_by_deposit:
                        total_stock = sum(info['stock'] for info in stock_by_deposit.values())
                        print(f"Stock encontrado para SKU: {sku}")
                        print(f"Stock total: {total_stock}")
                        for depot, info in stock_by_deposit.items():
                            print(f"   {depot}: {info['stock']}")
                        
                        return stock_by_deposit
                    else:
                        print(f"No se encontro stock para SKU: {sku}")
                        return None
                        
                else:
                    print(f"Error HTTP {response.status_code}: {response.text}")
                    
            except requests.Timeout:
                print(f"Timeout en intento {attempt + 1}")
                if attempt < max_retries - 1:
                    print(f"Esperando {retry_delay} segundos antes del siguiente intento...")
                    time.sleep(retry_delay)
                    
            except Exception as e:
                print(f"Error inesperado: {e}")
                break
        
        print(f"Fallo despues de {max_retries} intentos")
        return None

# Para compatibilidad, crear una instancia global
dragonfish_manager = DragonfishStockManager()

def get_stock_by_sku(sku):
    """Funcion de compatibilidad."""
    return dragonfish_manager.get_stock_by_sku(sku)
