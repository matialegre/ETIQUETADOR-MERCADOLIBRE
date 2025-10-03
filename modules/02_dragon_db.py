"""Servicio de Búsqueda de Códigos de Barra
========================================

Responsabilidades:
1. Buscar código de barra por SKU en base SQL
2. Obtener datos del artículo para Dragonfish
3. Mapear seller_custom_field a código de barra real

Basado en la lógica del picker_service original.
"""

import os
import sys
import pyodbc
from typing import Optional

# Import config con manejo de errores
try:
    from .config import SQLSERVER_CONN_STR
except ImportError:
    # Fallback para cuando se ejecuta directamente
    sys.path.append(os.path.dirname(__file__))
    from config import SQLSERVER_CONN_STR

def get_barcode_for_sku(sku: str) -> Optional[str]:
    """
    Obtiene el código de barra real desde un SKU.
    
    Args:
        sku: SKU del seller_custom_field de MercadoLibre
        
    Returns:
        str: Código de barra encontrado
        None: Si no se encuentra el SKU o hay error
    """
    return get_barcode_with_fallback(sku, None)

def get_barcode_with_fallback(seller_custom_field: Optional[str], seller_sku: Optional[str]) -> Optional[str]:
    """
    Obtiene el código de barra con lógica de fallback.
    
    Args:
        seller_custom_field: SKU principal de seller_custom_field
        seller_sku: SKU alternativo de SELLER_SKU
        
    Returns:
        str: Código de barra encontrado
        None: Si no se encuentra ningún SKU o hay error
    """
    print(f"🔍 Buscando barcode - seller_custom_field: {seller_custom_field}, seller_sku: {seller_sku}")

    # Hardcodes solicitados: mapear SKUs a códigos de barra específicos
    try:
        def _norm(s: Optional[str]) -> Optional[str]:
            if s is None:
                return None
            parts = [p for p in str(s).strip().split('-') if p != '']
            return '-'.join(parts) if parts else s

        scf_n = _norm(seller_custom_field)
        sku_n = _norm(seller_sku)

        hardcoded = {
            '466-I': '466-I-',       # cuando el SKU viene como 466-I-- lo normalizamos a 466-I
            '466-I-': '466-I-',      # por si ya trae el guión final
            'TDRK20-15': 'TDRK20-15',
        }
        for key in (seller_custom_field, scf_n, seller_sku, sku_n):
            if key and key in hardcoded:
                bc = hardcoded[key]
                print(f"   🔧 Hardcode de barcode aplicado para {key}: {bc}")
                return bc
    except Exception as _e:
        print(f"⚠️ No se pudo aplicar hardcode de barcode: {_e}")
    
    # Intento 1: Usar seller_custom_field si existe
    if seller_custom_field and seller_custom_field.strip():
        print(f"   🎯 Intentando con seller_custom_field: {seller_custom_field}")
        barcode = _search_barcode_in_db(seller_custom_field.strip())
        if barcode:
            print(f"   ✅ Barcode encontrado con seller_custom_field: {barcode}")
            return barcode
        else:
            print(f"   ❌ No encontrado con seller_custom_field")
    
    # Intento 2: Usar seller_sku como fallback
    if seller_sku and seller_sku.strip():
        print(f"   🔄 Intentando con seller_sku (fallback): {seller_sku}")
        barcode = _search_barcode_in_db(seller_sku.strip())
        if barcode:
            print(f"   ✅ Barcode encontrado con seller_sku: {barcode}")
            return barcode
        else:
            print(f"   ❌ No encontrado con seller_sku")
    
    print(f"   ❌ Barcode no encontrado con ningún SKU")
    return None

def _search_barcode_in_db(sku: str) -> Optional[str]:
    if not sku or not sku.strip():
        return None
    
    conn_str = SQLSERVER_CONN_STR
    database_name = os.environ.get('DATABASE_NAME', 'DRAGONFISH_DEPOSITO')
    
    if not conn_str:
        print("❌ Error: SQLSERVER_CONN_STR no configurado")
        return None
    
    connection = None
    try:
        # Conectar a SQL Server
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        
        # Determinar tipo de búsqueda
        if '-' in sku and len(sku.split('-')) >= 3:
            # Búsqueda por artículo, color y talle separados
            art, col, tal = sku.split('-', 2)
            query = (
                "SELECT RTRIM(equi.CCOLOR) AS CODIGO_COLOR, RTRIM(equi.CTALLE) AS CODIGO_TALLE, "
                "RTRIM(equi.CARTICUL) AS CODIGO_ARTICULO, RTRIM(equi.CCODIGO) AS CODIGO_BARRA, "
                "RTRIM(c_art.ARTDES) AS ARTDES "
                f"FROM {database_name}.ZooLogic.EQUI AS equi "
                f"LEFT JOIN {database_name}.ZooLogic.ART AS c_art ON equi.CARTICUL = c_art.ARTCOD "
                "WHERE RTRIM(equi.CARTICUL) = ? AND RTRIM(equi.CCOLOR) = ? AND RTRIM(equi.CTALLE) = ?"
            )
            cursor.execute(query, (art, col, tal))
        else:
            # Búsqueda por código de barra directo
            query = (
                "SELECT RTRIM(equi.CCOLOR) AS CODIGO_COLOR, RTRIM(equi.CTALLE) AS CODIGO_TALLE, "
                "RTRIM(equi.CARTICUL) AS CODIGO_ARTICULO, RTRIM(equi.CCODIGO) AS CODIGO_BARRA, "
                "RTRIM(c_art.ARTDES) AS ARTDES "
                f"FROM {database_name}.ZooLogic.EQUI AS equi "
                f"LEFT JOIN {database_name}.ZooLogic.ART AS c_art ON equi.CARTICUL = c_art.ARTCOD "
                "WHERE RTRIM(equi.CCODIGO) = ?"
            )
            cursor.execute(query, (sku.strip(),))
        
        row = cursor.fetchone()
        if row and row[3]:  # CODIGO_BARRA está en la posición 3
            barcode = str(row[3]).strip()
            print(f"✅ SKU encontrado: {sku} → {barcode}")
            return barcode
        else:
            print(f"⚠️ SKU no encontrado: {sku}")
            return None
            
    except pyodbc.Error as e:
        print(f"❌ Error de base de datos para SKU {sku}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado para SKU {sku}: {e}")
        return None
    finally:
        if connection:
            connection.close()


def get_article_info_by_barcode(barcode: str) -> Optional[dict]:
    """
    Devuelve información del artículo a partir del código de barras.

    Retorna un dict con claves:
      - CODIGO_COLOR
      - CODIGO_TALLE
      - CODIGO_ARTICULO
      - CODIGO_BARRA
      - ARTDES

    None si no se encuentra o hay error.
    """
    if not barcode or not str(barcode).strip():
        return None

    conn_str = SQLSERVER_CONN_STR
    database_name = os.environ.get('DATABASE_NAME', 'DRAGONFISH_DEPOSITO')

    if not conn_str:
        print("❌ Error: SQLSERVER_CONN_STR no configurado")
        return None

    connection = None
    try:
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()

        query = (
            "SELECT RTRIM(equi.CCOLOR) AS CODIGO_COLOR, RTRIM(equi.CTALLE) AS CODIGO_TALLE, "
            "RTRIM(equi.CARTICUL) AS CODIGO_ARTICULO, RTRIM(equi.CCODIGO) AS CODIGO_BARRA, "
            "RTRIM(c_art.ARTDES) AS ARTDES "
            f"FROM {database_name}.ZooLogic.EQUI AS equi "
            f"LEFT JOIN {database_name}.ZooLogic.ART AS c_art ON equi.CARTICUL = c_art.ARTCOD "
            "WHERE RTRIM(equi.CCODIGO) = ?"
        )
        cursor.execute(query, (str(barcode).strip(),))

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "CODIGO_COLOR": (row[0].strip() if row[0] is not None else ""),
            "CODIGO_TALLE": (row[1].strip() if row[1] is not None else ""),
            "CODIGO_ARTICULO": (row[2].strip() if row[2] is not None else ""),
            "CODIGO_BARRA": (row[3].strip() if row[3] is not None else ""),
            "ARTDES": (row[4].strip() if row[4] is not None else ""),
        }
    except pyodbc.Error as e:
        print(f"❌ Error de base de datos buscando info por barcode {barcode}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado buscando info por barcode {barcode}: {e}")
        return None
    finally:
        if connection:
            connection.close()

def test_connection() -> bool:
    """
    Prueba la conexión a la base de datos Dragon.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    conn_str = SQLSERVER_CONN_STR
    
    if not conn_str:
        print("❌ Error: SQLSERVER_CONN_STR no configurado")
        return False
    
    try:
        connection = pyodbc.connect(conn_str)
        cursor = connection.cursor()
        
        # Probar consulta simple
        database_name = os.environ.get('DATABASE_NAME', 'DRAGONFISH_DEPOSITO')
        cursor.execute(f"SELECT COUNT(*) FROM {database_name}.ZooLogic.EQUI")
        count = cursor.fetchone()[0]
        
        connection.close()
        print(f"✅ Conexión exitosa a Dragon DB. Registros en EQUI: {count}")
        return True
        
    except pyodbc.Error as e:
        print(f"❌ Error de conexión a Dragon DB: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado probando conexión: {e}")
        return False

def main():
    """
    Función principal para probar el módulo desde línea de comandos.
    
    Uso: python -m modules.02_dragon_db test_SKU
    """
    if len(sys.argv) < 2:
        print("❌ Uso: python -m modules.02_dragon_db <SKU>")
        print("   Ejemplo: python -m modules.02_dragon_db TEST001")
        sys.exit(1)
    
    sku = sys.argv[1]
    
    print(f"🔍 Buscando código de barra para SKU: {sku}")
    print("=" * 50)
    
    # Probar conexión primero
    print("🔌 Probando conexión a Dragon DB...")
    if not test_connection():
        print("❌ No se pudo conectar a la base de datos")
        sys.exit(1)
    
    # Buscar código de barra
    print(f"\n🔎 Buscando SKU: {sku}")
    barcode = get_barcode_for_sku(sku)
    
    print("\n📊 RESULTADO:")
    if barcode:
        print(f"   ✅ Código de barra: {barcode}")
    else:
        print(f"   ❌ SKU no encontrado: {sku}")

if __name__ == "__main__":
    main()
