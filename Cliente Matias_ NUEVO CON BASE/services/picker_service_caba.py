# services/picker_service_caba.py
"""
Servicio de picking específico para CABA.
Versión simplificada basada en picker_service.py original (solo ML1, sin ML2).
"""

import time
import re
from datetime import datetime
from typing import List, Dict, Any, Tuple
import requests

from api import ml_api
from models.order import Order
from services.sku_resolver import SKUResolver
from utils.logger import get_logger
from utils import config

log = get_logger(__name__)

class PickerServiceCaba:
    """Servicio de picking específico para CABA (solo ML1, sin ML2)."""
    
    def __init__(self):
        self.access_token: str | None = None
        self.seller_id: str | None = None
        self.sku_resolver: SKUResolver | None = None
        self.orders: List[Order] = []
        self._cache_expiry: float = 0
        self._already_printed: set[str] = set()  # Track printed items to avoid restock discount
        self._last_reprint_time: dict[str, float] = {}  # Anti-spam para reimpresiones
        self._last_from: datetime | None = None
        self._last_to: datetime | None = None
        
        log.info("🏢 PickerService CABA inicializado (solo ML1)")
    
    def _ensure_token(self) -> None:
        if self.access_token is None:
            self.access_token, self.seller_id = ml_api.refresh_access_token()
            self.sku_resolver = SKUResolver(self.access_token)
            log.info("Access token refrescado; seller_id=%s", self.seller_id)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @staticmethod
    def _barcode_from_sku(sku: str | None) -> str | None:
        """Genera código de barras para patrones Sunset/Ombak.
        SKU esperado: "01/1602" (o con guiones). Devuelve 13 dígitos o None.
        Lógica: 0 + color(2) + modelo(4) + 100 + última cifra de modelo + 00
        Ej: 01/1602 -> 0 01 1602 100 2 00 -> 0011602100200
        """
        if not sku:
            return None
        digits = re.sub(r"\D", "", sku)
        if len(digits) != 6:
            return None
        color = digits[:2]
        modelo = digits[2:]
        return f"0{color}{modelo}100{modelo[-1]}00"

    # ------------------------------------------------------------------
    def load_orders(self, date_from: datetime, date_to: datetime) -> List[Order]:
        """Carga órdenes de ML1 (cuenta principal) para CABA."""
        log.info(f"📅 Cargando pedidos CABA desde {date_from} hasta {date_to}")
        
        # Cargar pedidos usando el método padre
        all_orders = super().load_orders(date_from, date_to)
        
        # Filtrar por keywords de CABA
        filtered_orders = []
        for order in all_orders:
            note = (order.notes or "").upper()
            if any(keyword in note for keyword in self.keywords_note):
                filtered_orders.append(order)
                log.debug(f"✅ Pedido {order.id} incluido (nota: {note[:50]}...)")
            else:
                log.debug(f"❌ Pedido {order.id} excluido (nota: {note[:50]}...)")
        
        log.info(f"🎯 Filtrado CABA: {len(filtered_orders)}/{len(all_orders)} pedidos")
        return filtered_orders
    
    def update_stock_remote(self, sku: str, quantity: int) -> bool:
        """
        Actualiza stock en el servidor remoto de Bahía Blanca.
        """
        try:
            log.info(f"📦 Actualizando stock remoto CABA: {sku} (-{quantity})")
            success = self.dragonfish_api.update_stock(sku, quantity, "subtract")
            
            if success:
                log.info(f"✅ Stock actualizado exitosamente en servidor remoto: {sku}")
            else:
                log.error(f"❌ Error actualizando stock remoto: {sku}")
            
            return success
            
        except Exception as e:
            log.error(f"❌ Error inesperado actualizando stock remoto: {e}")
            return False
    
    def get_barcode_from_db_caba(self, sku: str) -> str | None:
        """
        Busca código de barras en la base de datos de CABA.
        """
        try:
            barcode = self.db_caba.get_barcode_by_sku(sku)
            if barcode:
                log.debug(f"🔍 Código de barras CABA encontrado para {sku}: {barcode}")
            else:
                log.debug(f"🔍 No se encontró código de barras CABA para: {sku}")
            return barcode
        except Exception as e:
            log.error(f"❌ Error buscando código de barras CABA: {e}")
            return None
    
    def get_sku_from_barcode_caba(self, barcode: str) -> str | None:
        """
        Busca SKU por código de barras en la base de datos de CABA.
        """
        try:
            sku = self.db_caba.get_sku_by_barcode(barcode)
            if sku:
                log.debug(f"🔍 SKU CABA encontrado para {barcode}: {sku}")
            else:
                log.debug(f"🔍 No se encontró SKU CABA para: {barcode}")
            return sku
        except Exception as e:
            log.error(f"❌ Error buscando SKU CABA: {e}")
            return None
    
    def process_pick_caba(self, barcode: str, order_id: str = None) -> dict:
        """
        Procesa un picking específico para CABA con validaciones remotas.
        
        Returns:
            dict: Resultado del picking con status y mensaje
        """
        try:
            log.info(f"🎯 Procesando pick CABA: {barcode}")
            
            # 1. Buscar SKU por código de barras
            sku = self.get_sku_from_barcode_caba(barcode)
            if not sku:
                return {
                    "status": "error",
                    "message": f"❌ Código de barras no encontrado en BD CABA: {barcode}"
                }
            
            # 2. Buscar en pedidos cargados
            target_order = None
            target_item = None
            
            for order in self.orders:
                # Verificar que sea un pedido CABA
                note = (order.notes or "").upper()
                if not any(keyword in note for keyword in self.keywords_note):
                    continue
                
                # Buscar el artículo
                for item in order.items:
                    if item.sku == sku or item.barcode == barcode:
                        target_order = order
                        target_item = item
                        break
                
                if target_order:
                    break
            
            if not target_order or not target_item:
                return {
                    "status": "error",
                    "message": f"❌ Artículo no encontrado en pedidos CABA: {sku}"
                }
            
            # 3. Validar estado del pedido
            if target_order.shipping_substatus == 'printed':
                return {
                    "status": "warning",
                    "message": f"⚠️ Pedido ya impreso: {target_order.id}"
                }
            
            # 4. Actualizar stock remoto
            stock_updated = self.update_stock_remote(sku, 1)
            if not stock_updated:
                log.warning(f"⚠️ No se pudo actualizar stock remoto para: {sku}")
            
            # 5. Registrar picking
            self.dragonfish_api.log_picking_activity(
                str(target_order.id), 
                sku, 
                1, 
                "caba_user"
            )
            
            return {
                "status": "success",
                "message": f"✅ Pick CABA exitoso: {target_item.title}",
                "order": target_order,
                "item": target_item,
                "sku": sku,
                "stock_updated": stock_updated
            }
            
        except Exception as e:
            log.error(f"❌ Error procesando pick CABA: {e}")
            return {
                "status": "error",
                "message": f"❌ Error inesperado: {str(e)}"
            }
    
    def validate_caba_order(self, order: Order) -> bool:
        """
        Valida si un pedido pertenece a CABA según sus notas.
        """
        note = (order.notes or "").upper()
        is_caba = any(keyword in note for keyword in self.keywords_note)
        
        if is_caba:
            log.debug(f"✅ Pedido {order.id} es de CABA (nota: {note[:30]}...)")
        else:
            log.debug(f"❌ Pedido {order.id} NO es de CABA (nota: {note[:30]}...)")
        
        return is_caba
    
    def get_caba_orders_summary(self) -> dict:
        """
        Obtiene resumen de pedidos CABA cargados.
        """
        if not self.orders:
            return {
                "total": 0,
                "caba": 0,
                "ready_to_print": 0,
                "printed": 0
            }
        
        caba_orders = [order for order in self.orders if self.validate_caba_order(order)]
        ready_orders = [order for order in caba_orders if order.shipping_substatus == 'ready_to_print']
        printed_orders = [order for order in caba_orders if order.shipping_substatus == 'printed']
        
        summary = {
            "total": len(self.orders),
            "caba": len(caba_orders),
            "ready_to_print": len(ready_orders),
            "printed": len(printed_orders)
        }
        
        log.info(f"📊 Resumen CABA: {summary}")
        return summary
    
    def test_caba_connections(self) -> dict:
        """
        Prueba todas las conexiones específicas de CABA.
        """
        results = {
            "dragonfish_api": False,
            "database": False,
            "overall": False
        }
        
        try:
            # Test API Dragonfish
            results["dragonfish_api"] = self.dragonfish_api.test_connection()
            
            # Test Base de datos
            results["database"] = self.db_caba.test_connection()
            
            # Test general
            results["overall"] = results["dragonfish_api"] and results["database"]
            
            log.info(f"🔧 Test conexiones CABA: {results}")
            return results
            
        except Exception as e:
            log.error(f"❌ Error en test de conexiones CABA: {e}")
            return results
