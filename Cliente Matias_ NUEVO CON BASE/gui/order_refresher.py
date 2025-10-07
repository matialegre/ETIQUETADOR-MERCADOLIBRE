# gui/order_refresher.py
"""
Servicio de actualización automática de pedidos.
Refresca los pedidos periódicamente y notifica cambios.
"""

import threading
import time
from typing import Callable, Optional, List
from datetime import datetime, timedelta
from utils.logger import get_logger
from models.order import Order

log = get_logger(__name__)

class OrderRefresher:
    """Servicio que refresca pedidos automáticamente en segundo plano."""
    
    def __init__(self, picker_service, gui_state, notification_callback: Optional[Callable] = None):
        self.picker_service = picker_service
        self.gui_state = gui_state
        self.notification_callback = notification_callback
        self.running = False
        self.thread = None
        self.refresh_interval = 120  # 2 minutos
        self.last_order_ids = set()
        
    def start(self):
        """Inicia el servicio de actualización automática."""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self.thread.start()
        log.info("🔄 OrderRefresher iniciado")
        
    def stop(self):
        """Detiene el servicio de actualización automática."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        log.info("⏹️ OrderRefresher detenido")
        
    def _refresh_loop(self):
        """Loop principal de actualización."""
        while self.running:
            try:
                self._check_for_updates()
                time.sleep(self.refresh_interval)
            except Exception as e:
                log.error(f"❌ Error en refresh loop: {e}")
                time.sleep(30)  # Esperar menos tiempo si hay error
                
    def _check_for_updates(self):
        """Verifica si hay nuevos pedidos."""
        try:
            # Solo refrescar si hay fechas configuradas
            if not hasattr(self.picker_service, '_last_from') or not self.picker_service._last_from:
                return
                
            # Cargar pedidos actuales
            current_orders = self.picker_service.load_orders(
                self.picker_service._last_from,
                self.picker_service._last_to or datetime.now()
            )
            
            # Obtener IDs actuales
            current_ids = {str(order.pack_id or order.id) for order in current_orders}
            
            # Detectar nuevos pedidos
            new_ids = current_ids - self.last_order_ids
            
            if new_ids:
                log.info(f"🆕 Detectados {len(new_ids)} nuevos pedidos")
                
                # Encontrar los pedidos nuevos
                new_orders = [order for order in current_orders 
                            if str(order.pack_id or order.id) in new_ids]
                
                # Notificar si hay callback
                if self.notification_callback and new_orders:
                    try:
                        self.notification_callback(new_orders)
                    except Exception as e:
                        log.error(f"❌ Error en callback de notificación: {e}")
                
                # Actualizar estado
                self.gui_state.set_orders(current_orders)
                
            # Actualizar IDs conocidos
            self.last_order_ids = current_ids
            
        except Exception as e:
            log.error(f"❌ Error verificando actualizaciones: {e}")
            
    def force_refresh(self):
        """Fuerza una actualización inmediata."""
        try:
            self._check_for_updates()
            log.info("🔄 Actualización forzada completada")
        except Exception as e:
            log.error(f"❌ Error en actualización forzada: {e}")
            
    def set_refresh_interval(self, seconds: int):
        """Cambia el intervalo de actualización."""
        self.refresh_interval = max(30, seconds)  # Mínimo 30 segundos
        log.info(f"⏱️ Intervalo de actualización cambiado a {self.refresh_interval}s")
        
    def get_status(self) -> dict:
        """Obtiene el estado del refresher."""
        return {
            'running': self.running,
            'refresh_interval': self.refresh_interval,
            'last_order_count': len(self.last_order_ids),
            'thread_alive': self.thread.is_alive() if self.thread else False
        }
