"""
Módulo 06: Filtrar órdenes ready_to_print
==========================================

Filtra órdenes que están listas para asignar depósito.
"""

import logging
from typing import List

from modules import local_db
from modules import models

SessionLocal = local_db.SessionLocal
OrderItem = models.OrderItem

logger = logging.getLogger(__name__)


def get_pending_ready() -> List[OrderItem]:
    """
    Obtiene órdenes pendientes de asignación que están ready_to_print.
    
    Returns:
        List[OrderItem]: Lista de órdenes listas para asignar
    """
    with SessionLocal() as s:
        result = (
            s.query(OrderItem)
            .filter(
                OrderItem.subestado == 'ready_to_print',
                OrderItem.asignado_flag.is_(False)
            )
            .order_by(OrderItem.fecha_orden.asc())
            .all()
        )
    
    logger.debug("Pendientes: %s", len(result))
    return result


if __name__ == "__main__":
    # Test básico
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        pending = get_pending_ready()
        print(f"✅ Órdenes pendientes encontradas: {len(pending)}")
        
        for order in pending[:3]:  # Mostrar solo las primeras 3
            print(f"   📋 Order: {order.order_id}, SKU: {order.sku}, Fecha: {order.fecha_orden}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
