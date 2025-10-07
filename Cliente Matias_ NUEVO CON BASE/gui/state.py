# gui/state.py
"""
Estado compartido de la GUI.
Mantiene el estado de los pedidos visibles y otras variables de estado.
"""

from typing import List, Optional
from models.order import Order

class GuiState:
    """Estado compartido entre componentes de la GUI."""
    
    def __init__(self):
        self.visibles: List[Order] = []
        self.selected_order: Optional[Order] = None
        self.filter_printed: bool = False
        self.filter_until_13h: bool = False
        self.last_update: Optional[float] = None
        self.is_loading: bool = False
        
    def clear(self):
        """Limpia el estado."""
        self.visibles.clear()
        self.selected_order = None
        self.last_update = None
        self.is_loading = False
        
    def set_orders(self, orders: List[Order]):
        """Establece la lista de pedidos visibles."""
        self.visibles = orders.copy() if orders else []
        
    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """Busca un pedido por ID."""
        for order in self.visibles:
            if str(order.pack_id or order.id) == str(order_id):
                return order
        return None
        
    def count_ready_orders(self) -> int:
        """Cuenta pedidos listos para imprimir."""
        return sum(1 for order in self.visibles 
                  if order.shipping_substatus == 'ready_to_print')
    
    def count_printed_orders(self) -> int:
        """Cuenta pedidos ya impresos."""
        return sum(1 for order in self.visibles 
                  if order.shipping_substatus == 'printed')
    
    def count_total_items(self) -> int:
        """Cuenta total de artículos."""
        return sum(len(order.items) for order in self.visibles)
    
    def count_pending_items(self) -> int:
        """Cuenta artículos pendientes (no impresos)."""
        return sum(len(order.items) for order in self.visibles 
                  if order.shipping_substatus != 'printed')
