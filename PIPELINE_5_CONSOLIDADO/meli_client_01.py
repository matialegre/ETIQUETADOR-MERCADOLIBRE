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
import os
import time

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
        # Preferir TOKEN_PATH; luego intentar token.json del proyecto; luego path legacy
        env_token_path = os.getenv('TOKEN_PATH')
        project_token_path = r'C:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline\config\token.json'
        self.config_path = config_path or env_token_path or project_token_path or r'C:\Users\Mundo Outdoor\Desktop\Develop_Mati\Escritor Meli\token.json'
        self.api_base = "https://api.mercadolibre.com"
        self.token_url = "https://api.mercadolibre.com/oauth/token"
        
        # Cargar configuración
        self._load_config()
        # Opción: forzar refresh explícito para pruebas
        try:
            if (os.getenv('ML_FORCE_REFRESH') or '0') == '1':
                print("🔧 ML_FORCE_REFRESH=1 → forzando refresh de token...")
                ok = self._refresh_token()
                print(f"🔧 Refresh forzado: {'OK' if ok else 'FALLÓ'}")
        except Exception:
            pass
    
    def _load_config(self):
        """Cargar configuración desde archivo JSON."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Campos base
            self.access_token = (config.get('access_token', '') or '').replace('\n', '').replace('\r', '').strip()
            self.refresh_token = config.get('refresh_token', '')
            self.client_id = config.get('client_id', '') or os.getenv('ML_CLIENT_ID', '')
            self.client_secret = config.get('client_secret', '') or os.getenv('ML_CLIENT_SECRET', '')
            self.user_id = config.get('user_id', '') or os.getenv('ML_USER_ID', '')
            # Campos para expiración
            self.expires_in = int(config.get('expires_in', 0) or 0)
            self.created_at = int(config.get('created_at', 0) or 0)
            
            print(f"✅ Configuración cargada desde: {self.config_path}")
            # Debug: mostrar app_id y user_id inferidos desde access_token
            try:
                token_str = self.access_token or ""
                app_id = None
                user_id = str(self.user_id or '')
                if token_str.startswith('APP_USR-'):
                    parts = token_str.split('-')
                    if len(parts) >= 3:
                        app_id = parts[1]
                        # último segmento suele ser user_id, pero confiamos en config.user_id
                print(f"🔎 Token info: app_id={app_id} user_id={user_id} token_prefix={(token_str[:18] + '...') if token_str else 'N/A'}")
            except Exception:
                pass
            
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
                'user_id': self.user_id,
                'expires_in': self.expires_in,
                'created_at': self.created_at,
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
            # Refresh proactivo si está vencido o por vencer (skew 60s)
            self.ensure_valid_token()
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
                
                self.access_token = (token_data.get('access_token') or '').replace('\n', '').replace('\r', '').strip()
                new_token = self.access_token[:20] + "..."
                
                # Actualizar refresh token si viene en la respuesta
                if 'refresh_token' in token_data:
                    self.refresh_token = token_data.get('refresh_token')
                # Actualizar expiración/creación
                self.expires_in = int(token_data.get('expires_in', self.expires_in or 0) or 0)
                # Algunos providers no devuelven created_at; lo seteamos a ahora
                self.created_at = int(token_data.get('created_at', int(time.time())))
                
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
    
    def _is_token_expired(self, skew_seconds: int = 60) -> bool:
        """Determina si el token está vencido usando created_at + expires_in.
        Si no hay datos suficientes, devuelve False para no bloquear.
        """
        try:
            if not self.expires_in or not self.created_at:
                return False
            now = int(time.time())
            return (self.created_at + self.expires_in - skew_seconds) <= now
        except Exception:
            return False

    def ensure_valid_token(self):
        """Refresca proactivamente el token si está vencido o cercano a vencerse."""
        if self._is_token_expired():
            print("🔄 Token por expirar/expirado, refrescando proactivamente...")
            ok = self._refresh_token()
            if not ok:
                print("⚠️ No se pudo refrescar proactivamente el token; se intentará bajo demanda si hay 401.")
    
    def get_recent_orders(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Obtener órdenes recientes del seller.
        
        Args:
            limit: Número máximo de órdenes a obtener
            
        Returns:
            Lista de órdenes con información completa
        """
        try:
            # Verificar token antes de llamar
            self.ensure_valid_token()
            url = f"{self.api_base}/orders/search"

            remaining = max(0, int(limit or 0))
            current_offset = max(0, int(offset or 0))
            all_orders: List[Dict[str, Any]] = []

            while remaining > 0:
                per_page = max(1, min(51, remaining))
                params = {
                    'seller': self.user_id,
                    'sort': 'date_desc',
                    'limit': per_page,
                    'offset': current_offset,
                }
                response_data = self._make_request(url, params)
                page_orders = response_data.get('results', []) or []
                print(f"✅ {len(page_orders)} órdenes obtenidas (offset={params['offset']}, limit={params['limit']})")

                if not page_orders:
                    break  # no hay más páginas

                # Debug breve por página
                try:
                    debug_max = int(os.getenv("PIPE5_DEBUG_FIELDS_MAX", "3") or "3")
                    if debug_max > 0 and page_orders:
                        print("\n🧪 DEBUG /orders/search - Campos por orden (previo a enrichment):")
                        for i, o in enumerate(page_orders[:debug_max], 1):
                            oid = o.get('id')
                            status = o.get('status')
                            substatus = o.get('substatus')
                            pack_id = o.get('pack_id')
                            buyer_nick = (o.get('buyer') or {}).get('nickname')
                            payments_len = len(o.get('payments') or [])
                            items = o.get('order_items') or []
                            items_len = len(items)
                            first_sku = None
                            try:
                                if items:
                                    first_sku = (items[0].get('item') or {}).get('seller_sku') or (items[0].get('item') or {}).get('seller_custom_field')
                            except Exception:
                                pass
                            shipping_id = None
                            try:
                                shipping = o.get('shipping') or {}
                                shipping_id = shipping.get('id') or shipping.get('shipping_id')
                            except Exception:
                                pass
                            keys_list = sorted(list(o.keys()))
                            print(f"   {i}. id={oid} status={status}/{substatus} pack={pack_id} buyer={buyer_nick} ship={shipping_id} items={items_len} payments={payments_len} sku0={first_sku}")
                            print(f"      keys: {keys_list}")
                        print()
                except Exception:
                    pass

                # Enriquecer cada orden con notas
                for order in page_orders:
                    order_id = str(order.get('id', ''))
                    if order_id:
                        notes = self.get_order_notes(order_id)
                        order['notes_data'] = notes
                        if notes:
                            note_texts = [note.get('text', '') for note in notes if note.get('text')]
                            order['nota'] = ' | '.join(note_texts) if note_texts else None
                        else:
                            order['nota'] = None

                all_orders.extend(page_orders)
                remaining -= len(page_orders)
                current_offset += len(page_orders)

                if len(page_orders) < per_page:
                    break  # página incompleta: no hay más datos

            return all_orders

        except Exception as e:
            print(f"❌ Error obteniendo órdenes: {e}")
            return []

    def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """
        Obtiene los detalles de un item de MercadoLibre.
        Se usa para extraer atributos ARTICULO/COLOR/TALLE.
        """
        try:
            url = f"{self.api_base}/items/{item_id}"
            return self._make_request(url)
        except Exception as e:
            return {'error': str(e)}
    
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
    
    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Obtiene los detalles completos de una orden: GET /orders/{order_id}.
        """
        try:
            print(f"🧾 Consultando detalles de orden: {order_id}")
            url = f"{self.api_base}/orders/{order_id}"
            return self._make_request(url)
        except Exception as e:
            error_msg = f"Error consultando orden {order_id}: {e}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
    
    def get_shipping_details(self, shipping_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles reales de shipping desde /shipments/{id}.
        
        Args:
            shipping_id: ID del shipping
            
        Returns:
            Dict con detalles del shipping o error
        """
        try:
            print(f"🚚 Consultando detalles REALES de shipping: {shipping_id}")
            
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
                
                print(f"✅ 🔥 SHIPPING REAL OBTENIDO: {status}/{substatus}")
                
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

    def get_shipment(self, shipping_id: str) -> Dict[str, Any]:
        """
        Alias conveniente de get_shipping_details() para mantener API uniforme.
        """
        return self.get_shipping_details(shipping_id)

    def get_item(self, item_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles del ítem: GET /items/{item_id}
        Devuelve el JSON completo; el título está en 'title'.
        """
        try:
            import requests
            print(f"🧾 Consultando item: {item_id}")
            url = f"{self.api_base}/items/{item_id}"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 401:
                print("🔄 Token expirado, refrescando...")
                if self._refresh_token():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    resp = requests.get(url, headers=headers, timeout=30)
                else:
                    return {'error': 'No se pudo refrescar el token'}
            if resp.status_code == 200:
                return resp.json()
            else:
                return {'error': f"Error {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {'error': f"Error consultando item {item_id}: {e}"}
    
    def get_pack_details(self, pack_id: str) -> Dict[str, Any]:
        """
        Obtiene detalles completos de multiventa desde /marketplace/orders/pack/{id}.
        
        Args:
            pack_id: ID del pack de multiventa
            
        Returns:
            Dict con detalles del pack o error
        """
        try:
            print(f"📦 Consultando detalles REALES de pack: {pack_id}")
            
            # Endpoint para detalles de pack
            url = f"{self.api_base}/marketplace/orders/pack/{pack_id}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            # Incluir caller.id como recomienda la documentación oficial
            params = None
            if getattr(self, 'user_id', None):
                headers['X-Caller-Id'] = str(self.user_id)
                params = {'caller.id': str(self.user_id)}
            else:
                print("⚠️ 'user_id' no está configurado; la API de packs puede responder 403 Invalid caller.id")
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 401:
                print("🔄 Token expirado, refrescando...")
                if self._refresh_token():
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    # Reintentar incluyendo nuevamente caller.id si aplica
                    if getattr(self, 'user_id', None):
                        headers['X-Caller-Id'] = str(self.user_id)
                        params = {'caller.id': str(self.user_id)}
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                else:
                    return {'error': 'No se pudo refrescar el token'}
            
            if response.status_code == 200:
                pack_data = response.json()
                
                # Extraer información relevante
                orders = pack_data.get('orders', [])
                total_orders = len(orders)
                is_complete = pack_data.get('is_complete', False)
                
                print(f"✅ 🔥 PACK REAL OBTENIDO: {total_orders} órdenes, completo: {is_complete}")
                
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

if __name__ == "__main__":
    test_client()
