"""
UTILIDADES DE BASE DE DATOS PARA ÓRDENES REALES
===============================================

Manejo de base de datos para órdenes reales de MercadoLibre.
"""

import os
import pyodbc
from typing import Dict, Optional, List
from datetime import datetime

# Connection string para SQL Server Express
CONNECTION_STRING = (
    os.getenv(
        "CONNECTION_STRING_MELI_STOCK",
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;",
    )
)

# Soporte de segunda base para la segunda cuenta ML (acc2)
# Habilitar vía ML_ACC2_ENABLED=true y opcionalmente configurar CONNECTION_STRING_MELI_STOCK_ACC2
ACC2_ENABLED: bool = os.getenv("ML_ACC2_ENABLED", "false").lower() in ("1", "true", "yes", "on")
ACC2_USER_ID: int = int(os.getenv("ML_ACC2_USER_ID", "756086955"))
CONNECTION_STRING_ACC2 = os.getenv(
    "CONNECTION_STRING_MELI_STOCK_ACC2",
    CONNECTION_STRING.replace("DATABASE=meli_stock", "DATABASE=meli_stock_acc2"),
)

def get_connection() -> pyodbc.Connection:
    """Obtiene conexión a la base por defecto (meli_stock)."""
    return pyodbc.connect(CONNECTION_STRING)

def get_connection_for_meli(meli_user_id: Optional[int]) -> pyodbc.Connection:
    """
    Devuelve una conexión según el seller (MELI). Si está habilitado acc2 y el user coincide,
    usa la base meli_stock_acc2; si no, usa la base por defecto meli_stock.
    """
    try:
        if ACC2_ENABLED and meli_user_id is not None and int(meli_user_id) == int(ACC2_USER_ID):
            return pyodbc.connect(CONNECTION_STRING_ACC2)
    except Exception:
        # fallback seguro
        pass
    return pyodbc.connect(CONNECTION_STRING)

def ensure_schema(cursor) -> None:
    """Asegura columnas requeridas en orders_meli."""
    # CAMBIO_ESTADO: INT NULL, indicador de cambio ready_to_print -> printed;
    # 0 por defecto (sin cambio), 1 cuando se detecta el cambio.
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'CAMBIO_ESTADO'
        )
        BEGIN
            ALTER TABLE orders_meli ADD CAMBIO_ESTADO INT NULL DEFAULT 0;
        END
        """
    )
    # Normalizar valores nulos a 0 para dejar default consistente
    cursor.execute(
        """
        UPDATE orders_meli SET CAMBIO_ESTADO = 0
        WHERE CAMBIO_ESTADO IS NULL
        """
    )
    # Campos para multiventa/pack
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'multiventa_grupo'
        )
        BEGIN
            ALTER TABLE orders_meli ADD multiventa_grupo NVARCHAR(100) NULL;
        END
        """
    )
    # Asegurar tipo correcto
    cursor.execute(
        """
        IF EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'multiventa_grupo' AND DATA_TYPE <> 'nvarchar'
        )
        BEGIN
            ALTER TABLE orders_meli ALTER COLUMN multiventa_grupo NVARCHAR(100) NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'is_pack_complete'
        )
        BEGIN
            ALTER TABLE orders_meli ADD is_pack_complete BIT NULL;
        END
        """
    )
    cursor.execute(
        """
        IF EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'is_pack_complete' AND DATA_TYPE <> 'bit'
        )
        BEGIN
            ALTER TABLE orders_meli ALTER COLUMN is_pack_complete BIT NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'venta_tipo'
        )
        BEGIN
            ALTER TABLE orders_meli ADD venta_tipo NVARCHAR(20) NULL;
        END
        """
    )
    cursor.execute(
        """
        IF EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'venta_tipo' AND DATA_TYPE <> 'nvarchar'
        )
        BEGIN
            ALTER TABLE orders_meli ALTER COLUMN venta_tipo NVARCHAR(20) NULL;
        END
        """
    )

    # Columnas para asignación de depósito y stock
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'deposito_asignado'
        )
        BEGIN
            ALTER TABLE orders_meli ADD deposito_asignado NVARCHAR(50) NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'stock_real'
        )
        BEGIN
            ALTER TABLE orders_meli ADD stock_real INT NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'stock_reservado'
        )
        BEGIN
            ALTER TABLE orders_meli ADD stock_reservado INT NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'resultante'
        )
        BEGIN
            ALTER TABLE orders_meli ADD resultante INT NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'agotamiento_flag'
        )
        BEGIN
            ALTER TABLE orders_meli ADD agotamiento_flag BIT NULL;
        END
        """
    )

    # Columna para relacionar órdenes de la misma multiventa (concatenación de order_id por pack o marcador por qty>1)
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'multiventa_relacion'
        )
        BEGIN
            ALTER TABLE orders_meli ADD multiventa_relacion NVARCHAR(MAX) NULL;
        END
        """
    )

    # Nuevas columnas solicitadas: nombre (título ML) y campos para movimiento de depósito
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'nombre'
        )
        BEGIN
            ALTER TABLE orders_meli ADD nombre NVARCHAR(255) NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'mov_depo_hecho'
        )
        BEGIN
            ALTER TABLE orders_meli ADD mov_depo_hecho BIT NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'mov_depo_obs'
        )
        BEGIN
            ALTER TABLE orders_meli ADD mov_depo_obs NVARCHAR(255) NULL;
        END
        """
    )
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'mov_depo_numero'
        )
        BEGIN
            ALTER TABLE orders_meli ADD mov_depo_numero NVARCHAR(50) NULL;
        END
        """
    )

    # Columna de control: stock del depósito MELI (no se usa en la lógica de asignación)
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'depo_meli'
        )
        BEGIN
            ALTER TABLE orders_meli ADD depo_meli INT NULL;
        END
        """
    )

    # Columna MELI: identifica la cuenta/seller (user_id de MercadoLibre) que originó la orden
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'MELI'
        )
        BEGIN
            ALTER TABLE orders_meli ADD MELI BIGINT NULL;
        END
        """
    )

    # Columna de control: stock del depósito WOO (no se usa en la lógica de asignación)
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'depo_woo'
        )
        BEGIN
            ALTER TABLE orders_meli ADD depo_woo INT NULL;
        END
        """
    )

    # Detalle estructurado de asignación (JSON): cluster/split y distribución por depósito
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'asignacion_detalle'
        )
        BEGIN
            ALTER TABLE orders_meli ADD asignacion_detalle NVARCHAR(MAX) NULL;
        END
        """
    )

    # Columna para fecha estimada de entrega (ISO8601 con zona)
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'estimated_delivery_final'
        )
        BEGIN
            ALTER TABLE orders_meli ADD estimated_delivery_final NVARCHAR(50) NULL;
        END
        """
    )

    # Flag de control: indicar que el pack debe partirse
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = 'DEBE_PARTIRSE'
        )
        BEGIN
            ALTER TABLE orders_meli ADD DEBE_PARTIRSE BIT NULL;
        END
        """
    )

    cursor.execute(
        """
        -- Columnas de stock por depósito oficiales (crear si faltan)
        DECLARE @cols TABLE(name NVARCHAR(100));
        INSERT INTO @cols(name) VALUES
            ('stock_dep'),
            ('stock_mdq'),
            ('stock_monbahia'),
            ('stock_mtgbbps'),
            ('stock_mtgcba'),
            ('stock_mtgcom'),
            ('stock_mtgjbj'),
            ('stock_mtgroca'),
            ('stock_mundoal'),
            ('stock_mundoroc'),
            ('stock_mundocab'),
            ('stock_nqnalb'),
            ('stock_nqnshop');

        DECLARE @name NVARCHAR(100);
        WHILE EXISTS (SELECT 1 FROM @cols)
        BEGIN
            SELECT TOP 1 @name = name FROM @cols;
            IF NOT EXISTS (
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'orders_meli' AND COLUMN_NAME = @name
            )
            BEGIN
                DECLARE @sql NVARCHAR(MAX) = N'ALTER TABLE orders_meli ADD ' + QUOTENAME(@name) + N' INT NULL;';
                EXEC (@sql);
            END
            DELETE FROM @cols WHERE name = @name;
        END
        """
    )

    # Tabla de movimientos para auditoría granular
    cursor.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'movimientos'
        )
        BEGIN
            CREATE TABLE movimientos (
                id INT IDENTITY(1,1) PRIMARY KEY,
                order_id NVARCHAR(50) NOT NULL,
                sku NVARCHAR(100) NOT NULL,
                qty INT NOT NULL,
                accion NVARCHAR(50) NOT NULL, -- ASIGNACION / AGOTADO
                deposito NVARCHAR(50) NULL,
                disponible INT NULL,
                resultante INT NULL,
                nota NVARCHAR(400) NULL,
                fecha_registro DATETIME NOT NULL DEFAULT(GETDATE())
            );
        END
        """
    )

def insert_or_update_order(order_data: Dict) -> str:
    """
    Inserta o actualiza una orden en la base de datos.
    
    Args:
        order_data: Datos de la orden procesada
        
    Returns:
        'inserted' o 'updated'
    """
    
    try:
        # Elegir base en función del seller (MELI)
        meli_user_id = order_data.get('meli_user_id')
        with get_connection_for_meli(meli_user_id) as conn:
            cursor = conn.cursor()
            ensure_schema(cursor)
            
            # Verificar si la orden existe
            cursor.execute(
                "SELECT COUNT(*) FROM orders_meli WHERE order_id = ?",
                (order_data['order_id'],)
            )
            exists = cursor.fetchone()[0] > 0

            if exists:
                # Chequear si ya está asignada alguna fila de esa orden
                cursor.execute(
                    """
                    SELECT CASE WHEN MAX(CASE WHEN asignado_flag = 1 THEN 1 ELSE 0 END) = 1 THEN 1 ELSE 0 END
                    FROM orders_meli WHERE order_id = ?
                    """,
                    (order_data['order_id'],)
                )
                already_assigned = cursor.fetchone()[0] == 1

                # Leer shipping_subestado actual para detectar transición a 'printed'
                cursor.execute(
                    "SELECT TOP 1 shipping_subestado FROM orders_meli WHERE order_id = ?",
                    (order_data['order_id'],)
                )
                current_sub = cursor.fetchone()[0]
                becomes_printed = (
                    (current_sub == 'ready_to_print') and (order_data.get('shipping_subestado') == 'printed')
                ) or (order_data.get('shipping_subestado') == 'printed' and current_sub not in ('printed', None))

                if already_assigned:
                    # Actualización incremental explícita: SOLO campos de estado/shipping/fecha/color
                    update_status_sql = """
                    UPDATE orders_meli SET
                        estado = ?,
                        subestado = ?,
                        shipping_id = ?,
                        shipping_estado = ?,
                        shipping_subestado = ?,
                        -- Si pasa a printed, liberar la reserva (stock_reservado = 0)
                        stock_reservado = CASE WHEN ? = 'printed' THEN 0 ELSE stock_reservado END,
                        -- Recalcular resultante si hay stock_real conocido
                        resultante = CASE WHEN ? = 'printed' AND stock_real IS NOT NULL THEN stock_real ELSE resultante END,
                        -- Marcar CAMBIO_ESTADO = 1 cuando se detecta transición ready_to_print -> printed
                        CAMBIO_ESTADO = CASE WHEN ? = 1 THEN 1 ELSE CAMBIO_ESTADO END,
                        date_created = ?,
                        date_closed = ?,
                        display_color = ?,
                        nombre = COALESCE(?, nombre),
                        fecha_actualizacion = ?,
                        MELI = COALESCE(MELI, ?)
                    WHERE order_id = ?
                    """
                    cursor.execute(update_status_sql, (
                        order_data['status'],
                        order_data['substatus'],
                        order_data['shipping_id'],
                        order_data['shipping_estado'],
                        order_data['shipping_subestado'],
                        order_data['shipping_subestado'],  # para CASE printed (stock_reservado)
                        order_data['shipping_subestado'],  # para CASE printed (resultante)
                        1 if becomes_printed else 0,      # CAMBIO_ESTADO a 1 solo si hubo transición
                        order_data['date_created'],
                        order_data['date_closed'],
                        order_data['display_color'],
                        order_data.get('nombre'),
                        order_data['fecha_actualizacion'],
                        order_data.get('meli_user_id'),
                        order_data['order_id']
                    ))
                else:
                    # Actualización completa (antes de asignar): permitir cambios en datos base
                    update_full_sql = """
                    UPDATE orders_meli SET
                        sku = ?,
                        seller_sku = ?,
                        barcode = ?,
                        item_id = ?,
                        pack_id = ?,
                        multiventa_grupo = ?,
                        is_pack_complete = ?,
                        venta_tipo = ?,
                        qty = ?,
                        total_amount = ?,
                        estado = ?,
                        subestado = ?,
                        shipping_id = ?,
                        shipping_estado = ?,
                        shipping_subestado = ?,
                        date_created = ?,
                        date_closed = ?,
                        display_color = ?,
                        nombre = ?,
                        ARTICULO = ?,
                        COLOR = ?,
                        TALLE = ?,
                        fecha_actualizacion = ?,
                        MELI = COALESCE(?, MELI)
                    WHERE order_id = ?
                    """
                    # Ajuste horario: sumar +1 hora a date_created si es parseable
                    try:
                        from datetime import datetime, timedelta
                        dc_val = order_data.get('date_created')
                        if isinstance(dc_val, str):
                            dc_dt = datetime.fromisoformat(dc_val)
                        else:
                            dc_dt = dc_val  # puede venir ya como datetime
                        if dc_dt is not None:
                            dc_adj = dc_dt + timedelta(hours=1)
                        else:
                            dc_adj = dc_val
                    except Exception:
                        dc_adj = order_data.get('date_created')

                    cursor.execute(update_full_sql, (
                        order_data['sku'],
                        order_data['seller_sku'],
                        order_data['barcode'],
                        order_data['item_id'],
                        order_data['pack_id'],
                        order_data.get('multiventa_grupo'),
                        1 if order_data.get('is_pack_complete') else 0,
                        order_data.get('venta_tipo'),
                        order_data['quantity'],
                        order_data['total_amount'],
                        order_data['status'],
                        order_data['substatus'],
                        order_data['shipping_id'],
                        order_data['shipping_estado'],
                        order_data['shipping_subestado'],
                        dc_adj,
                        order_data['date_closed'],
                        order_data['display_color'],
                        order_data.get('nombre'),
                        order_data.get('articulo'),
                        order_data.get('color'),
                        order_data.get('talle'),
                        order_data['fecha_actualizacion'],
                        order_data.get('meli_user_id'),
                        order_data['order_id']
                    ))

                conn.commit()
                return 'updated'
                
            else:
                # Insertar nueva orden
                insert_sql = """
                INSERT INTO orders_meli (
                    order_id, MELI, sku, seller_sku, barcode, item_id, pack_id, qty, total_amount,
                    multiventa_grupo, is_pack_complete, venta_tipo,
                    estado, subestado, shipping_id, shipping_estado, shipping_subestado,
                    date_created, date_closed, display_color, nombre, ARTICULO, COLOR, TALLE, asignado_flag,
                    movimiento_realizado, fecha_actualizacion, CAMBIO_ESTADO,
                    mov_depo_hecho, mov_depo_obs, mov_depo_numero
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                # Ajuste horario: sumar +1 hora a date_created si es parseable
                try:
                    from datetime import datetime, timedelta
                    dc_val = order_data.get('date_created')
                    if isinstance(dc_val, str):
                        dc_dt = datetime.fromisoformat(dc_val)
                    else:
                        dc_dt = dc_val
                    if dc_dt is not None:
                        dc_adj = dc_dt + timedelta(hours=1)
                    else:
                        dc_adj = dc_val
                except Exception:
                    dc_adj = order_data.get('date_created')

                cursor.execute(insert_sql, (
                    order_data['order_id'],
                    order_data.get('meli_user_id'),
                    order_data['sku'],
                    order_data['seller_sku'],
                    order_data['barcode'],  # NUEVO: Campo barcode
                    order_data['item_id'],
                    order_data['pack_id'],
                    order_data['quantity'],
                    order_data['total_amount'],
                    order_data.get('multiventa_grupo'),
                    1 if order_data.get('is_pack_complete') else 0,
                    order_data.get('venta_tipo'),
                    order_data['status'],
                    order_data['substatus'],
                    order_data['shipping_id'],
                    order_data['shipping_estado'],
                    order_data['shipping_subestado'],
                    dc_adj,
                    order_data['date_closed'],
                    order_data['display_color'],
                    order_data.get('nombre'),
                    order_data.get('articulo'),
                    order_data.get('color'),
                    order_data.get('talle'),
                    order_data['asignado_flag'],
                    order_data['movimiento_realizado'],
                    order_data['fecha_actualizacion'],
                    0,
                    None,
                    None,
                    None
                ))
                
                conn.commit()
                return 'inserted'
                
    except Exception as e:
        print(f"❌ Error insert/update: {e}")
        return 'error'

def log_movement(order_id: str, sku: str, qty: int, accion: str, deposito: str = None,
                 disponible: int = None, resultante: int = None, nota: str = None) -> None:
    """Inserta un registro en tabla movimientos."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            ensure_schema(cur)
            cur.execute(
                """
                INSERT INTO movimientos(order_id, sku, qty, accion, deposito, disponible, resultante, nota)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    str(order_id), str(sku), int(qty or 0), str(accion),
                    deposito, disponible, resultante, nota
                )
            )
            conn.commit()
    except Exception as e:
        print(f"❌ Error registrando movimiento: {e}")

def clear_movimientos() -> bool:
    """Limpia la tabla movimientos."""
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            ensure_schema(cur)
            cur.execute("DELETE FROM movimientos")
            conn.commit()
            return True
    except Exception as e:
        print(f"❌ Error limpiando movimientos: {e}")
        return False

def get_database_summary() -> Dict:
    """
    Obtiene resumen del estado de la base de datos.
    
    Returns:
        Dict con estadísticas de la base
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Contar por subestado
            cursor.execute("""
                SELECT shipping_subestado, COUNT(*) 
                FROM orders_meli 
                GROUP BY shipping_subestado
            """)
            
            by_substatus = {}
            for row in cursor.fetchall():
                substatus = row[0] or 'sin_subestado'
                count = row[1]
                by_substatus[substatus] = count
            
            # Contar asignadas vs pendientes
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN asignado_flag = 1 THEN 1 ELSE 0 END) as assigned,
                    SUM(CASE WHEN asignado_flag = 0 THEN 1 ELSE 0 END) as pending
                FROM orders_meli
            """)
            
            assignment_row = cursor.fetchone()
            assigned = assignment_row[0] or 0
            pending = assignment_row[1] or 0
            
            # Últimas órdenes
            cursor.execute("""
                SELECT TOP 10 order_id, shipping_subestado, asignado_flag, fecha_actualizacion
                FROM orders_meli 
                ORDER BY fecha_actualizacion DESC
            """)
            
            recent_orders = []
            for row in cursor.fetchall():
                recent_orders.append({
                    'order_id': row[0],
                    'shipping_subestado': row[1],
                    'asignado_flag': bool(row[2]),
                    'fecha_actualizacion': row[3]
                })
            
            return {
                'by_substatus': by_substatus,
                'assigned': assigned,
                'pending': pending,
                'recent_orders': recent_orders
            }
            
    except Exception as e:
        print(f"❌ Error obteniendo resumen: {e}")
        return {
            'by_substatus': {},
            'assigned': 0,
            'pending': 0,
            'recent_orders': []
        }

def clear_all_orders() -> bool:
    """
    Limpia todas las órdenes de la base de datos.
    
    Returns:
        True si se limpió exitosamente, False si hubo error
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Contar órdenes antes de limpiar
            cursor.execute("SELECT COUNT(*) FROM orders_meli")
            count_before = cursor.fetchone()[0]
            
            print(f"📄 Órdenes en base antes de limpiar: {count_before}")
            
            # Limpiar todas las órdenes
            cursor.execute("DELETE FROM orders_meli")
            conn.commit()
            
            # Verificar que se limpió
            cursor.execute("SELECT COUNT(*) FROM orders_meli")
            count_after = cursor.fetchone()[0]
            
            print(f"🧹 Órdenes en base después de limpiar: {count_after}")
            
            if count_after == 0:
                print(f"✅ Base de datos limpiada exitosamente ({count_before} órdenes eliminadas)")
                return True
            else:
                print(f"⚠️ Advertencia: Aún quedan {count_after} órdenes en la base")
                return False
    except Exception as e:
        print(f"❌ Error limpiando base de datos: {e}")
        return False

def get_latest_order_for_meli(meli_user_id: int) -> Optional[Dict]:
    """
    Devuelve la última orden (por fecha_actualizacion y luego date_created) para un seller (MELI=user_id).
    """
    try:
        # Elegir base en función del seller solicitado
        with get_connection_for_meli(meli_user_id) as conn:
            cur = conn.cursor()
            ensure_schema(cur)
            cur.execute(
                """
                SELECT TOP 1 order_id, MELI, date_created, fecha_actualizacion
                FROM orders_meli
                WHERE MELI = ?
                ORDER BY ISNULL(fecha_actualizacion, '1900-01-01') DESC, ISNULL(date_created, '1900-01-01') DESC
                """,
                (int(meli_user_id),)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                'order_id': str(row[0]),
                'meli': int(row[1]) if row[1] is not None else None,
                'date_created': row[2],
                'fecha_actualizacion': row[3],
            }
    except Exception as e:
        print(f"❌ Error buscando última orden para MELI={meli_user_id}: {e}")
        return None

def get_order_row(order_id: str) -> Optional[Dict]:
    """
    Devuelve una fila de orders_meli por order_id (campos clave para verificación).
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            ensure_schema(cur)
            cur.execute(
                """
                SELECT TOP 1 order_id, MELI, pack_id, shipping_id, estado, subestado, shipping_estado, shipping_subestado, date_created, fecha_actualizacion
                FROM orders_meli
                WHERE order_id = ?
                """,
                (str(order_id),)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                'order_id': str(row[0]),
                'meli': int(row[1]) if row[1] is not None else None,
                'pack_id': row[2],
                'shipping_id': row[3],
                'estado': row[4],
                'subestado': row[5],
                'shipping_estado': row[6],
                'shipping_subestado': row[7],
                'date_created': row[8],
                'fecha_actualizacion': row[9],
            }
    except Exception as e:
        print(f"❌ Error obteniendo order_id={order_id}: {e}")
        return None

def normalize_multiventa_and_relacion() -> dict:
    """
    Normaliza venta_tipo y multiventa_grupo/multiventa_relacion en orders_meli.
    Reglas:
    - Si un pack_id aparece en >1 filas: venta_tipo='multiventa', multiventa_grupo='PACK_{pack_id}',
      multiventa_relacion=order_id concatenados con '+' por pack.
    - Si qty>1: venta_tipo='multiventa', multiventa_grupo='ORDER_{order_id}_QTY',
      multiventa_relacion='ORDER_{order_id}_QTY{qty}'.
    - En packs singleton (pack_id no nulo con COUNT=1) y qty<=1, multiventa_relacion=NULL.
    Devuelve resumen con contadores.
    """
    summary = {
        'set_multiventa_pack': 0,
        'set_multiventa_qty': 0,
        'set_rel_pack': 0,
        'cleared_singleton_rel': 0,
        'set_rel_qty': 0,
    }
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # multiventa por pack (>1)
            cursor.execute(
                """
                UPDATE o
                SET o.venta_tipo = 'multiventa',
                    o.multiventa_grupo = 'PACK_' + o.pack_id
                FROM orders_meli o
                JOIN (
                  SELECT pack_id
                  FROM orders_meli
                  WHERE pack_id IS NOT NULL
                  GROUP BY pack_id
                  HAVING COUNT(*) > 1
                ) p ON p.pack_id = o.pack_id;
                """
            )
            summary['set_multiventa_pack'] = cursor.rowcount or 0

            # multiventa por qty>1
            cursor.execute(
                """
                UPDATE orders_meli
                SET venta_tipo = 'multiventa',
                    multiventa_grupo = 'ORDER_' + CAST(order_id AS NVARCHAR(50)) + '_QTY'
                WHERE TRY_CAST(qty AS INT) > 1;
                """
            )
            summary['set_multiventa_qty'] = cursor.rowcount or 0

            # relación por pack concatenada
            cursor.execute(
                """
                WITH agg AS (
                  SELECT pack_id,
                         STRING_AGG(CAST(order_id AS NVARCHAR(50)),'+') WITHIN GROUP (ORDER BY order_id) AS ids
                  FROM orders_meli
                  WHERE pack_id IS NOT NULL
                  GROUP BY pack_id
                  HAVING COUNT(*) > 1
                )
                UPDATE o
                SET o.multiventa_relacion = a.ids
                FROM orders_meli o
                JOIN agg a ON a.pack_id = o.pack_id;
                """
            )
            summary['set_rel_pack'] = cursor.rowcount or 0

            # limpiar relacion en singletons
            cursor.execute(
                """
                UPDATE o
                SET o.multiventa_relacion = NULL
                FROM orders_meli o
                LEFT JOIN (
                  SELECT pack_id
                  FROM orders_meli
                  WHERE pack_id IS NOT NULL
                  GROUP BY pack_id
                  HAVING COUNT(*) > 1
                ) multi ON multi.pack_id = o.pack_id
                WHERE o.pack_id IS NOT NULL
                  AND multi.pack_id IS NULL
                  AND (TRY_CAST(o.qty AS INT) IS NULL OR TRY_CAST(o.qty AS INT) <= 1);
                """
            )
            summary['cleared_singleton_rel'] = cursor.rowcount or 0

            # relación por qty>1
            cursor.execute(
                """
                UPDATE orders_meli
                SET multiventa_relacion = 'ORDER_' + CAST(order_id AS NVARCHAR(50)) + '_QTY' + CAST(qty AS NVARCHAR(10))
                WHERE TRY_CAST(qty AS INT) > 1;
                """
            )
            summary['set_rel_qty'] = cursor.rowcount or 0

            conn.commit()

    except Exception as e:
        print(f"❌ Error en normalización multiventa: {e}")
    return summary

