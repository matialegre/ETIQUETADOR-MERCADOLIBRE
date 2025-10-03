"""
🛒 CLIENTE MERCADOLIBRE COMPLETO Y CORREGIDO
===========================================

Cliente para interactuar con la API de MercadoLibre con:
- Refresh automático de tokens
- Manejo correcto de notas
- Guardado automático de configuración
- Manejo robusto de errores

Autor: Cascade AI
Fecha: 2025-08-07
"""

import requests
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

class MeliClientError(Exception):
    """Excepción personalizada para errores del cliente MercadoLibre."""
    pass

class MeliClient:
    """Cliente para interactuar con la API de MercadoLibre."""
    
    def __init__(self, config_path: str = None):
        """
        Inicializar cliente MercadoLibre.
        
        Args:
            config_path: Ruta al archivo de configuración de tokens
        """
        self.config_path = config_path or r'C:\Users\Mundo Outdoor\Desktop\Develop_Mati\Escritor Meli\token.json'
        self.api_base = "https://api.mercadolibre.com"
        self.token_url = "https://api.mercadolibre.com/oauth/token"
        
        # Cargar configuración
        self._load_config()
    
    def _load_config(self):
        """Cargar configuración desde archivo JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.access_token = config.get('access_token', '')
            self.refresh_token = config.get('refresh_token', '')
            self.client_id = config.get('client_id', '')
            self.client_secret = config.get('client_secret', '')
            self.user_id = config.get('user_id', '')
            
            print(f"✅ Configuración cargada desde: {self.config_path}")
            
        except Exception as e:
            print(f"❌ Error cargando configuración: {e}")
            raise MeliClientError(f"No se pudo cargar la configuración: {e}")
    
    def _save_config(self):
        """Guardar configuración actualizada en archivo JSON."""
        try:
            config = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'user_id': self.user_id
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Configuración guardada en: {self.config_path}")
            
        except Exception as e:
            print(f"❌ Error guardando configuración: {e}")
    
    def _make_request(self, url: str, params: dict = None) -> dict:
        """Realizar petición HTTP con manejo de errores y refresh automático."""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 401:
                # Token expirado, intentar refresh
                print(f"🔄 Token expirado, refrescando automáticamente...")
                if self._refresh_token():
                    # Actualizar headers con nuevo token
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = requests.get(url, headers=headers, params=params, timeout=15)
                    print(f"✅ Token refrescado y petición reintentada")
                else:
                    raise Exception("No se pudo refrescar el token")
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Error {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error de conexión: {e}")
    
    def _refresh_token(self) -> bool:
        """Refrescar el access token usando refresh token y guardar automáticamente."""
        if not self.refresh_token or not self.client_id or not self.client_secret:
            print(f"❌ Faltan credenciales para refresh:")
            print(f"   client_id: {bool(self.client_id)}")
            print(f"   client_secret: {bool(self.client_secret)}")
            print(f"   refresh_token: {bool(self.refresh_token)}")
            return False
        
        try:
            data = {
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token
            }
            
            response = requests.post(self.token_url, data=data, timeout=15)
            
            if response.status_code == 200:
                token_data = response.json()
                old_token = self.access_token[:20] + "..."
                
                self.access_token = token_data.get('access_token')
                new_token = self.access_token[:20] + "..."
                
                # Actualizar refresh token si viene en la respuesta
                if 'refresh_token' in token_data:
                    self.refresh_token = token_data.get('refresh_token')
                
                # Guardar automáticamente la configuración actualizada
                self._save_config()
                
                print(f"✅ Token refrescado exitosamente")
                print(f"🔄 Anterior: {old_token}")
                print(f"🆕 Nuevo: {new_token}")
                
                return True
            else:
                print(f"❌ Error refrescando token: {response.status_code} - {response.text[:100]}")
                return False
                
        except Exception as e:
            print(f"❌ Excepción refrescando token: {e}")
            return False
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtener órdenes recientes del seller.
        
        Args:
            limit: Número máximo de órdenes a obtener
            
        Returns:
            Lista de órdenes con información completa
        """
        try:
            url = f"{self.api_base}/orders/search"
            params = {
                'seller': self.user_id,
                'sort': 'date_desc',
                'limit': limit
            }
            
            response_data = self._make_request(url, params)
            orders = response_data.get('results', [])
            
            print(f"✅ {len(orders)} órdenes obtenidas")
            
            # Enriquecer cada orden con notas
            enriched_orders = []
            for order in orders:
                order_id = str(order.get('id', ''))
                if order_id:
                    # Obtener notas para esta orden
                    notes = self.get_order_notes(order_id)
                    order['notes_data'] = notes
                    
                    # Extraer texto de notas para campo 'nota'
                    if notes:
                        note_texts = [note.get('text', '') for note in notes if note.get('text')]
                        order['nota'] = ' | '.join(note_texts) if note_texts else None
                    else:
                        order['nota'] = None
                
                enriched_orders.append(order)
            
            return enriched_orders
            
        except Exception as e:
            print(f"❌ Error obteniendo órdenes: {e}")
            return []
    
    def get_order_notes(self, order_id: str) -> List[Dict[str, Any]]:
        """Obtener notas de una orden específica con manejo correcto de estructura."""
        try:
            url = f"{self.api_base}/orders/{order_id}/notes"
            params = {"role": "seller"}
            
            response_data = self._make_request(url, params)
            
            # La respuesta puede ser una lista directa o un dict con 'results'
            if isinstance(response_data, list):
                notes = response_data
            elif isinstance(response_data, dict) and 'results' in response_data:
                notes = response_data['results']
            else:
                notes = []
            
            # Extraer el texto real de cada nota
            processed_notes = []
            for note in notes:
                if isinstance(note, dict):
                    note_text = note.get('note', note.get('text', ''))
                    if note_text:
                        processed_notes.append({
                            'id': note.get('id', ''),
                            'text': note_text,
                            'date_created': note.get('date_created', ''),
                            'date_last_updated': note.get('date_last_updated', ''),
                            'from': note.get('from', {}),
                            'to': note.get('to', {})
                        })
            
            return processed_notes
                
        except Exception as e:
            print(f"❌ Error obteniendo notas para orden {order_id}: {e}")
            return []
    
    def get_shipping_details(self, shipping_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles reales de shipping desde /shipments/{id}.
        
        Args:
            shipping_id: ID del shipping
            
        Returns:
            Dict con detalles del shipping o error
        """
        try:
            print(f"🚚 Consultando detalles de shipping: {shipping_id}")
            
            # Endpoint para detalles de shipping
            url = f"{self.api_base}/shipments/{shipping_id}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 401:
                print("🔄 Token expirado, refrescando...")
                if self._refresh_token():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = requests.get(url, headers=headers, timeout=30)
                else:
                    return {'error': 'No se pudo refrescar el token'}
            
            if response.status_code == 200:
                shipping_data = response.json()
                
                # Extraer información relevante
                status = shipping_data.get('status', 'unknown')
                substatus = shipping_data.get('substatus', 'unknown')
                
                print(f"✅ Shipping obtenido: {status}/{substatus}")
                
                return {
                    'status': status,
                    'substatus': substatus,
                    'raw_data': shipping_data
                }
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                print(f"❌ {error_msg}")
                return {'error': error_msg}
                
        except Exception as e:
            error_msg = f"Error consultando shipping {shipping_id}: {e}"
            print(f"❌ {error_msg}")
            return {'error': error_msg}

    def get_pack_details(self, pack_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles completos de multiventa desde /marketplace/orders/pack/{id}.
        
        Args:
            pack_id: ID del pack de multiventa
            
        Returns:
            Dict con detalles del pack o error
        """
        try:
            print(f"📦 Consultando detalles de pack: {pack_id}")
            
            url = f"{self.api_base}/marketplace/orders/pack/{pack_id}"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 401:
                print("🔄 Token expirado, refrescando...")
                if self._refresh_token():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    response = requests.get(url, headers=headers, timeout=30)
                else:
                    return {'error': 'No se pudo refrescar el token'}
            
            if response.status_code == 200:
                pack_data = response.json()
                orders = pack_data.get('orders', [])
                total_orders = len(orders)
                is_complete = pack_data.get('is_complete', False)
                
                print(f"✅ Pack obtenido: {total_orders} órdenes, completo: {is_complete}")
                
                return {
                    'total_orders': total_orders,
                    'is_complete': is_complete,
                    'orders': orders,
                    'raw_data': pack_data
                }
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                print(f"❌ {error_msg}")
                return {'error': error_msg}
                
        except Exception as e:
            error_msg = f"Error consultando pack {pack_id}: {e}"
            print(f"❌ {error_msg}")
            return {'error': error_msg}

    def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles de un ítem (y variaciones) desde /items/{id}.

        Args:
            item_id: ID del ítem de MercadoLibre (ej: MLA123456)

        Returns:
            Dict con datos del ítem o {'error': ...}
        """
        try:
            if not item_id:
                return {'error': 'item_id vacío'}
            url = f"{self.api_base}/items/{item_id}"
            data = self._make_request(url)
            return data if isinstance(data, dict) else {'error': 'respuesta inválida'}
        except Exception as e:
            return {'error': str(e)}

def get_recent_orders(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Función principal para obtener órdenes recientes.
    
    Args:
        limit: Número máximo de órdenes a obtener
        
    Returns:
        Lista de órdenes con información completa
    """
    try:
        client = MeliClient()
        return client.get_recent_orders(limit)
    except Exception as e:
        print(f"❌ Error en get_recent_orders: {e}")
        return []

# Función de prueba
def test_client():
    """Función de prueba del cliente."""
    print("🧪 PROBANDO CLIENTE MERCADOLIBRE")
    print("=" * 50)
    
    try:
        client = MeliClient()
        
        # Obtener última orden
        orders = client.get_recent_orders(1)
        
        if orders:
            order = orders[0]
            order_id = order.get('id', 'N/A')
            total = order.get('total_amount', 'N/A')
            status = order.get('status', 'N/A')
            notes_count = len(order.get('notes_data', []))
            
            print(f"✅ Última orden obtenida:")
            print(f"   ID: {order_id}")
            print(f"   Total: {total}")
            print(f"   Status: {status}")
            print(f"   Notas: {notes_count}")
            
            return True
        else:
            print("❌ No se obtuvieron órdenes")
            return False
            
    except Exception as e:
        print(f"❌ Error en prueba: {e}")
        return False

    def get_shipping_details(self, shipping_id: str) -> dict:
        """
        Obtiene los detalles reales de shipping usando el endpoint oficial /shipments/{id}.
        
        Args:
            shipping_id: ID del shipping de la orden
            
        Returns:
            dict: Detalles del shipping con status y substatus reales
        """
        if not shipping_id or shipping_id == 'unknown':
            return {
                'status': 'unknown',
                'substatus': 'unknown',
                'error': 'shipping_id no válido'
            }
        
        try:
            url = f"{self.api_base}/shipments/{shipping_id}"
            response = self._make_request('GET', url)
            
            if response:
                shipping_data = response
                return {
                    'status': shipping_data.get('status', 'unknown'),
                    'substatus': shipping_data.get('substatus', 'unknown'),
                    'tracking_number': shipping_data.get('tracking_number'),
                    'tracking_method': shipping_data.get('tracking_method'),
                    'date_created': shipping_data.get('date_created'),
                    'last_updated': shipping_data.get('last_updated')
                }
            else:
                return {
                    'status': 'unknown',
                    'substatus': 'unknown',
                    'error': 'No se pudo obtener información de shipping'
                }
                
        except Exception as e:
            print(f"⚠️ Error obteniendo detalles de shipping {shipping_id}: {e}")
            return {
                'status': 'unknown',
                'substatus': 'unknown',
                'error': str(e)
            }
    
    def get_pack_details(self, pack_id: str) -> dict:
        """
        Obtiene los detalles de un pack/multiventa usando el endpoint oficial.
        
        Args:
            pack_id: ID del pack de la multiventa
            
        Returns:
            dict: Detalles del pack con todas las órdenes asociadas
        """
        if not pack_id:
            return {
                'orders': [],
                'is_complete': False,
                'error': 'pack_id no válido'
            }
        
        try:
            url = f"{self.api_base}/marketplace/orders/pack/{pack_id}"
            response = self._make_request('GET', url)
            
            if response:
                pack_data = response
                orders = pack_data.get('orders', [])
                
                # Determinar si el pack está completo
                is_complete = len(orders) > 0 and all(
                    order.get('status') in ['paid', 'shipped', 'delivered'] 
                    for order in orders
                )
                
                return {
                    'orders': orders,
                    'is_complete': is_complete,
                    'total_orders': len(orders),
                    'pack_id': pack_id
                }
            else:
                return {
                    'orders': [],
                    'is_complete': False,
                    'error': 'No se pudo obtener información del pack'
                }
                
        except Exception as e:
            print(f"⚠️ Error obteniendo detalles del pack {pack_id}: {e}")
            return {
                'orders': [],
                'is_complete': False,
                'error': str(e)
            }

if __name__ == "__main__":
    test_client()
