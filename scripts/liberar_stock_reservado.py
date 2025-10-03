"""
Script para liberar stock_reservado de órdenes impresas
====================================================

Libera el stock_reservado de órdenes que ya están marcadas como printed=1
para evitar reservas permanentes que afecten futuras asignaciones.
"""

import logging
import pyodbc
from typing import Optional

logger = logging.getLogger(__name__)

def liberar_stock_reservado_printed(dry_run: bool = True, limit: Optional[int] = None) -> int:
    """
    Libera stock_reservado de órdenes con printed=1 que aún tienen stock_reservado > 0.
    
    Args:
        dry_run: Si True, solo muestra qué se haría sin ejecutar cambios
        limit: Límite de órdenes a procesar (None = todas)
        
    Returns:
        int: Número de órdenes actualizadas
    """
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;"
    )
    
    try:
        cur = conn.cursor()
        
        # Buscar órdenes impresas con stock_reservado > 0
        query = """
            SELECT order_id, sku, deposito_asignado, stock_reservado, qty
            FROM orders_meli 
            WHERE ISNULL(printed, 0) = 1 
              AND ISNULL(stock_reservado, 0) > 0
        """
        
        if limit:
            query = f"SELECT TOP ({limit}) " + query[6:]  # Reemplazar SELECT por SELECT TOP
            
        query += " ORDER BY fecha_actualizacion DESC"
        
        cur.execute(query)
        rows = cur.fetchall()
        
        if not rows:
            logger.info("No se encontraron órdenes impresas con stock_reservado > 0")
            return 0
            
        logger.info(f"Encontradas {len(rows)} órdenes impresas con stock reservado")
        
        if dry_run:
            logger.info("=== MODO DRY RUN - No se ejecutarán cambios ===")
            for row in rows:
                logger.info(f"  Order {row.order_id}: SKU={row.sku} Depo={row.deposito_asignado} "
                           f"Reservado={row.stock_reservado} Qty={row.qty}")
            return len(rows)
        
        # Ejecutar liberación
        updated = 0
        for row in rows:
            try:
                cur.execute("""
                    UPDATE orders_meli 
                    SET stock_reservado = 0, 
                        fecha_actualizacion = GETDATE()
                    WHERE order_id = ? AND ISNULL(printed, 0) = 1
                """, (row.order_id,))
                
                if cur.rowcount > 0:
                    updated += 1
                    logger.info(f"✅ Liberado stock_reservado para order {row.order_id} "
                               f"(SKU={row.sku}, era {row.stock_reservado})")
                    
            except Exception as e:
                logger.error(f"❌ Error liberando order {row.order_id}: {e}")
                continue
                
        conn.commit()
        logger.info(f"🎯 Liberadas {updated} órdenes impresas")
        return updated
        
    finally:
        conn.close()


def main():
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s"
    )
    
    parser = argparse.ArgumentParser(description="Liberar stock_reservado de órdenes impresas")
    parser.add_argument("--dry-run", action="store_true", default=True, 
                       help="Solo mostrar qué se haría (default: True)")
    parser.add_argument("--execute", action="store_true", 
                       help="Ejecutar cambios reales (deshabilita dry-run)")
    parser.add_argument("--limit", type=int, default=None,
                       help="Límite de órdenes a procesar")
    
    args = parser.parse_args()
    
    dry_run = not args.execute  # Si --execute está presente, dry_run=False
    
    try:
        updated = liberar_stock_reservado_printed(dry_run=dry_run, limit=args.limit)
        
        if dry_run:
            print(f"🔍 DRY RUN: Se liberarían {updated} órdenes")
            print("Para ejecutar cambios reales, usa: --execute")
        else:
            print(f"✅ Liberadas {updated} órdenes impresas")
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    exit(main())
