"""
Módulo 07: Asignador de depósitos
================================

Lógica para elegir el mejor depósito basado en prioridades y stock disponible.
Implementa el sistema de PUNTOS + MULTIPLICADORES del código de referencia.
"""

import logging
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Configuración de prioridades (basada en prioridades_depositos.txt)
PUNTOS: Dict[str, float] = {
    'DEP': 10000000,
    'MDQ': 0,
    'MONBAHIA': 6000000,
    'MTGBBPS': 4000000,
    'MTGCBA': 0,
    'MTGCOM': 0,
    'MTGJBJ': 0,
    'MTGROCA': 3000000,
    'MUNDOAL': 8000000,
    'MUNDOCAB': 20000000,
    'MUNDOROC': 2000000,
    'NQNALB': 1000000,
    'NQNSHOP': 0,
}

MULTIPLICADORES: Dict[str, float] = {
    'DEP': 1.0,
    'MDQ': 0.5,
    'MONBAHIA': 0.8,
    'MTGBBPS': 0.8,
    'MTGCBA': 1.0,
    'MTGCOM': 1.0,
    'MTGJBJ': 1.0,
    'MTGROCA': 0.5,
    'MUNDOAL': 0.8,
    'MUNDOCAB': 5.0,
    'MUNDOROC': 0.2,
    'NQNALB': 0.2,
    'NQNSHOP': 0.3,
}

# Orden de prioridad simple (fallback)
DEPOSIT_PRIORITY = [
    'MUNDOCAB',    # 20M puntos, 5.0 mult
    'DEP',         # 10M puntos, 1.0 mult
    'MUNDOAL',     # 8M puntos, 0.8 mult
    'MONBAHIA',    # 6M puntos, 0.8 mult
    'MTGBBPS',     # 4M puntos, 0.8 mult
    'MTGROCA',     # 3M puntos, 0.5 mult
    'MUNDOROC',    # 2M puntos, 0.2 mult
    'NQNALB',      # 1M puntos, 0.2 mult
    'NQNSHOP',     # 0 puntos, 0.3 mult
    'MDQ',         # 0 puntos, 0.5 mult
    'MTGCBA',      # 0 puntos, 1.0 mult
    'MTGCOM',      # 0 puntos, 1.0 mult
    'MTGJBJ',      # 0 puntos, 1.0 mult
]


def calculate_depot_score(depot: str, available: int, qty: int) -> float:
    """
    Calcula el score de un depósito basado en prioridades y stock.
    
    Args:
        depot: Nombre del depósito
        available: Stock disponible
        qty: Cantidad requerida
        
    Returns:
        Score del depósito (mayor = mejor)
    """
    if available < qty:
        return 0.0  # No puede satisfacer la demanda
    
    puntos = PUNTOS.get(depot, 0.0)
    mult = MULTIPLICADORES.get(depot, 1.0)
    
    # Score = puntos base + (cantidad * multiplicador)
    score = puntos + (qty * mult)
    
    logger.debug(f"Depot {depot}: available={available}, qty={qty}, puntos={puntos}, mult={mult}, score={score}")
    
    return score


def choose_winner(stock: Dict[str, Dict[str, int]], qty: int) -> Optional[Tuple[str, int, int]]:
    """
    Elige el mejor depósito basado en stock disponible y prioridades.
    
    Args:
        stock: Dict con formato {'DEP1': {'total': 10, 'reserved': 2}, ...}
        qty: Cantidad requerida
        
    Returns:
        Tuple (depot, total, reserved) del ganador, o None si no hay stock suficiente
    """
    best_depot = None
    best_score = 0.0
    best_data = None
    
    logger.debug(f"Evaluando depósitos para qty={qty}")
    
    for depot, data in stock.items():
        if not data:
            continue
            
        total = data.get('total', 0)
        reserved = data.get('reserved', 0)
        available = total - reserved
        
        if available < qty:
            logger.debug(f"Depot {depot}: insuficiente stock (disponible={available}, necesario={qty})")
            continue
        
        score = calculate_depot_score(depot, available, qty)
        
        if score > best_score:
            best_score = score
            best_depot = depot
            best_data = (depot, total, reserved)
            logger.debug(f"Nuevo mejor: {depot} con score {score}")
    
    if best_data:
        logger.info(f"Ganador: {best_data[0]} (total={best_data[1]}, reserved={best_data[2]}, score={best_score})")
    else:
        logger.warning(f"No se encontró depósito con stock suficiente para qty={qty}")
    
    return best_data


def choose_winner_simple(stock: Dict[str, Dict[str, int]], qty: int) -> Optional[Tuple[str, int, int]]:
    """
    Versión simple que usa solo el orden de prioridad (fallback).
    
    Args:
        stock: Dict con formato {'DEP1': {'total': 10, 'reserved': 2}, ...}
        qty: Cantidad requerida
        
    Returns:
        Tuple (depot, total, reserved) del ganador, o None si no hay stock suficiente
    """
    logger.debug(f"Usando asignación simple para qty={qty}")
    
    for depot in DEPOSIT_PRIORITY:
        data = stock.get(depot)
        if not data:
            continue
            
        total = data.get('total', 0)
        reserved = data.get('reserved', 0)
        available = total - reserved
        
        if available >= qty:
            logger.info(f"Ganador simple: {depot} (total={total}, reserved={reserved}, available={available})")
            return (depot, total, reserved)
    
    logger.warning(f"No se encontró depósito con stock suficiente para qty={qty}")
    return None


def assign_depot_to_orders(orders: list) -> dict:
    """
    Asigna depósitos a una lista de órdenes ready_to_print.
    
    Para cada orden:
    1. Consulta stock en Dragonfish API usando el barcode
    2. Aplica lógica de prioridades para elegir depósito ganador
    3. Actualiza la orden en la base de datos con la asignación
    
    Args:
        orders: Lista de órdenes (dict) con campos order_id, sku, barcode, quantity
        
    Returns:
        dict: Resultados de la asignación con estadísticas y detalles
    """
    
    import sys
    import os
    
    # Agregar path para módulos
    sys.path.append(r'C:\Users\Mundo Outdoor\Desktop\meli_dragon_pipeline\modules')
    
    try:
        from dragonfish_api import get_stock_by_sku
    except ImportError as e:
        # Sin simulaciones: fallar explícitamente si no se puede usar la API real
        raise RuntimeError("No se pudo importar dragonfish_api (API real obligatoria)") from e
    
    results = {
        'total_processed': 0,
        'assigned': 0,
        'no_stock': 0,
        'errors': [],
        'assignments': [],
        'no_stock_orders': []
    }
    
    print(f"🎯 Procesando asignación para {len(orders)} órdenes...")
    
    for i, order in enumerate(orders, 1):
        try:
            order_id = order.get('order_id', 'unknown')
            sku = order.get('sku', 'unknown')
            barcode = order.get('barcode')
            quantity = order.get('quantity')
            try:
                quantity = int(quantity) if quantity is not None else 1
            except Exception:
                quantity = 1
            if quantity <= 0:
                quantity = 1
            
            print(f"\n📦 [{i}/{len(orders)}] Procesando {order_id}...")
            print(f"   SKU: {sku}")
            print(f"   Barcode: {barcode}")
            print(f"   Cantidad (qty): {quantity}")
            
            results['total_processed'] += 1
            
            # Consultar stock en Dragonfish API por SKU
            print(f"   🔍 Consultando stock por SKU {sku}...")
            stock_data = get_stock_by_sku(sku)
            
            if not stock_data:
                print(f"   ❌ No se encontró stock para SKU {sku}")
                # Marcar agotamiento en DB
                try:
                    update_order_no_stock(order_id)
                except Exception as _:
                    pass
                results['errors'].append(f"Sin stock: {order_id}")
                results['no_stock_orders'].append(order)
                continue
            
            # Mostrar stock disponible
            print(f"   📊 Stock encontrado:")
            for depot, data in stock_data.items():
                available = data.get('total', 0) - data.get('reserved', 0)
                print(f"      {depot}: total={data.get('total', 0)}, reserved={data.get('reserved', 0)}, available={available}")
            
            # Elegir depósito ganador
            winner = choose_winner(stock_data, quantity)
            
            if not winner:
                print(f"   ❌ No hay depósito con stock suficiente (qty={quantity})")
                # Marcar agotamiento en DB
                try:
                    update_order_no_stock(order_id)
                except Exception as _:
                    pass
                results['no_stock'] += 1
                results['no_stock_orders'].append(order)
                continue
            
            depot_assigned, total_stock, reserved_stock = winner
            available_stock = total_stock - reserved_stock
            
            print(f"   ✅ Depósito ganador: {depot_assigned} (disponible: {available_stock})")
            
            # Actualizar orden en base de datos (incluye stock por depósito y métricas de stock)
            success = update_order_assignment(order_id, depot_assigned, quantity, total_stock, available_stock, stock_data)
            
            if success:
                print(f"   💾 Orden actualizada en base de datos")
                results['assigned'] += 1
                results['assignments'].append({
                    'order_id': order_id,
                    'sku': sku,
                    'depot_assigned': depot_assigned,
                    'stock_found': available_stock
                })
            else:
                error_msg = f"Error actualizando orden {order_id} en base de datos"
                print(f"   ❌ {error_msg}")
                results['errors'].append(error_msg)
                
        except Exception as e:
            error_msg = f"Error procesando orden {order.get('order_id', 'unknown')}: {e}"
            print(f"   ❌ {error_msg}")
            results['errors'].append(error_msg)
    
    return results


def update_order_assignment(order_id: str, depot: str, qty: int, total_stock: int, stock_available: int, stock_map: dict) -> bool:
    """
    Actualiza una orden con la asignación de depósito.
    
    Args:
        order_id: ID de la orden
        depot: Depósito asignado
        stock_available: Stock disponible en el depósito
        
    Returns:
        bool: True si se actualizó correctamente
    """
    
    import pyodbc
    from datetime import datetime
    
    # Connection string para SQL Server Express
    CONNECTION_STRING = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=.\\SQLEXPRESS;"
        "DATABASE=meli_stock;"
        "Trusted_Connection=yes;"
    )
    
    try:
        with pyodbc.connect(CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            
            # Calcular disponibles por depósito (total - reserved)
            def avail(name: str) -> int:
                d = stock_map.get(name, {})
                return int(d.get('total', 0)) - int(d.get('reserved', 0))

            v_dep = avail('DEP')
            v_mdq = avail('MDQ')
            v_monbahia = avail('MONBAHIA')
            v_mundocab = avail('MUNDOCAB')
            v_mundoal = avail('MUNDOAL')
            v_mundoroc = avail('MUNDOROC')
            v_mtgcba = avail('MTGCBA')
            v_mtgcom = avail('MTGCOM')
            v_mtgjbj = avail('MTGJBJ')
            v_mtgroca = avail('MTGROCA')
            v_mtgbbps = avail('MTGBBPS')
            v_nqnalb = avail('NQNALB')
            v_nqnshop = avail('NQNSHOP')

            # Actualizar orden con asignación + stock por depósito
            # Calcular métricas de stock del depósito ganador
            stock_real = int(total_stock)
            stock_reservado = int(qty)
            stock_resultante = max(stock_real - stock_reservado, 0)
            agotamiento_flag = 1 if stock_resultante == 0 else 0

            update_query = """
            UPDATE orders_meli 
            SET 
                deposito_asignado = ?,
                stock_disponible = ?,
                asignado_flag = 1,
                fecha_asignacion = ?,
                stock_real = ?,
                stock_reservado = ?,
                resultante = ?,
                agotamiento_flag = ?,
                stock_dep = ?,
                stock_mdq = ?,
                stock_monbahia = ?,
                stock_mundocab = ?,
                stock_mundoal = ?,
                stock_mundoroc = ?,
                stock_mtgcba = ?,
                stock_mtgcom = ?,
                stock_mtgjbj = ?,
                stock_mtgroca = ?,
                stock_mtgbbps = ?,
                stock_nqnalb = ?,
                stock_nqnshop = ?
            WHERE order_id = ?
            """

            cursor.execute(update_query, (
                depot,
                stock_available,
                datetime.now(),
                stock_real,
                stock_reservado,
                stock_resultante,
                agotamiento_flag,
                v_dep,
                v_mdq,
                v_monbahia,
                v_mundocab,
                v_mundoal,
                v_mundoroc,
                v_mtgcba,
                v_mtgcom,
                v_mtgjbj,
                v_mtgroca,
                v_mtgbbps,
                v_nqnalb,
                v_nqnshop,
                order_id
            ))
            
            conn.commit()
            
            if cursor.rowcount > 0:
                return True
            else:
                print(f"❌ No se encontró orden {order_id} para actualizar")
                return False
        
    except Exception as e:
        print(f"❌ Error actualizando orden {order_id}: {e}")
        return False


def update_order_no_stock(order_id: str) -> bool:
    """
    Marca una orden como sin stock (agotamiento_flag=1) y resetea métricas básicas.
    """
    import pyodbc
    from datetime import datetime
    CONNECTION_STRING = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=.\\SQLEXPRESS;"
        "DATABASE=meli_stock;"
        "Trusted_Connection=yes;"
    )
    try:
        with pyodbc.connect(CONNECTION_STRING) as conn:
            cursor = conn.cursor()
            update_query = """
            UPDATE orders_meli
            SET 
                deposito_asignado = 'NO HAY',
                asignado_flag = 0,
                stock_disponible = 0,
                stock_real = 0,
                stock_reservado = 0,
                resultante = 0,
                agotamiento_flag = 1,
                fecha_asignacion = ?
            WHERE order_id = ?
            """
            cursor.execute(update_query, (datetime.now(), order_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"❌ Error marcando sin stock {order_id}: {e}")
        return False
                
    except Exception as e:
        print(f"❌ Error actualizando orden {order_id}: {e}")
        return False


if __name__ == "__main__":
    # Test básico
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    # Mock stock data para prueba
    test_stock = {
        'DEP': {'total': 5, 'reserved': 1},
        'MUNDOCAB': {'total': 3, 'reserved': 0},
        'MUNDOAL': {'total': 10, 'reserved': 2},
        'MONBAHIA': {'total': 2, 'reserved': 0},
    }
    
    test_qty = 3
    
    try:
        print(f"🎯 Test con qty={test_qty}")
        print("📊 Stock disponible:")
        for depot, data in test_stock.items():
            available = data['total'] - data['reserved']
            print(f"   {depot}: total={data['total']}, reserved={data['reserved']}, available={available}")
        
        winner = choose_winner(test_stock, test_qty)
        if winner:
            depot, total, reserved = winner
            available = total - reserved
            print(f"✅ Ganador: {depot} (disponible: {available})")
        else:
            print("❌ No hay ganador")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
