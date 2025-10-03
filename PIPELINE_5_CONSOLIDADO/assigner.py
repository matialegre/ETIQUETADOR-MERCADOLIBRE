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
    # Filtrar solo depósitos oficiales definidos en PUNTOS
    allowed = set(PUNTOS.keys())
    original_keys = set(stock.keys())
    stock = {k: v for k, v in stock.items() if k in allowed}
    ignored = original_keys - set(stock.keys())
    if ignored:
        logger.debug(f"Ignorando depósitos no oficiales: {sorted(ignored)}")
    
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
