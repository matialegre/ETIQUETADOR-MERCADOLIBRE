"""
Módulo 06: Filtrar órdenes ready_to_print
==========================================

Filtra órdenes que están listas para asignar depósito.
"""

import logging
from typing import List
from sqlalchemy import or_

from modules import local_db
from modules import models

SessionLocal = local_db.SessionLocal
OrderItem = models.OrderItem

logger = logging.getLogger(__name__)


def get_pending_ready() -> List[OrderItem]:
    """
    Obtiene órdenes pendientes de asignación que están ready_to_print.
    Excluye órdenes ya asignadas con agotamiento_flag=1 para evitar reasignaciones.
    
    Returns:
        List[OrderItem]: Lista de órdenes listas para asignar
    """
    with SessionLocal() as s:
        result = (
            s.query(OrderItem)
            .filter(
                OrderItem.shipping_subestado == 'ready_to_print',
                or_(OrderItem.asignado_flag == False, OrderItem.asignado_flag.is_(None)),
                # Evitar reasignar órdenes ya agotadas (problema de doble asignación)
                or_(OrderItem.agotamiento_flag == False, OrderItem.agotamiento_flag.is_(None))
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
