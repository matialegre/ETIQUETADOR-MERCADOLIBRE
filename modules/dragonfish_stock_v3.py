"""
Modulo Dragonfish Stock V3 - Version simplificada para asignador
"""

import requests
import time

def get_stock_simple(sku, max_retries=3, retry_delay=60):
    """
    Consulta stock simplificada para el asignador.
    Retorna formato compatible: {'DEPOT': {'total': X, 'reserved': 0}}
    """
    api_base_url = 'http://deposito_2:8009/api/ConsultaStockYPreciosEntreLocales/'
    timeout = 120
    
    for attempt in range(max_retries):
        try:
            print(f"Intento {attempt + 1}/{max_retries} - Consultando API Dragonfish...")
            
            response = requests.get(
                api_base_url,
                params={'sku': sku},
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"API Response para {sku}: {len(data)} resultados")
                
                # Procesar respuesta para formato del asignador
                stock_for_assigner = {}
                
                for item in data:
                    if item.get('sku') == sku:
                        deposit = item.get('deposito', 'UNKNOWN')
                        stock = item.get('stock', 0)
                        
                        if stock > 0:
                            stock_for_assigner[deposit] = {
                                'total': stock,
                                'reserved': 0  # Por ahora sin reservas
                            }
                            print(f"AGREGADO: {deposit} con {stock} unidades")
                
                if stock_for_assigner:
                    total_stock = sum(info['total'] for info in stock_for_assigner.values())
                    print(f"Stock encontrado para SKU: {sku}")
                    print(f"Stock total: {total_stock}")
                    for depot, info in stock_for_assigner.items():
                        print(f"   {depot}: {info['total']}")
                    
                    return stock_for_assigner
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
