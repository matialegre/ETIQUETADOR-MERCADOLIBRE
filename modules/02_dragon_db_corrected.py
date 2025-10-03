"""
Servicio de Búsqueda de Códigos de Barra - CONFIGURACIÓN REAL
============================================================

Responsabilidades:
1. Buscar código de barra por SKU en base SQL real
2. Conectar a ranchoaspen\zoo2025, base dragonfish_deposito
3. Usar tabla dragonfish_deposito.ZooLogic.EQUI

CONFIGURACIÓN REAL DEL USUARIO:
- Servidor: ranchoaspen\zoo2025
- Base: dragonfish_deposito
- Tabla: dragonfish_deposito.ZooLogic.EQUI
- Campo SKU: CARTICUL
- Campo Barcode: CCODIGO

Autor: Cascade AI
Fecha: 2025-08-07
"""

import pyodbc
from typing import Optional, Dict, Any

class DragonDBService:
    """Servicio para búsqueda de códigos de barra en Dragon DB."""
    
    def __init__(self):
        # Configuración REAL del usuario
        self.server = "ranchoaspen\\zoo2025"
        self.database = "dragonfish_deposito"
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            f"Trusted_Connection=yes;"
        )
        
    def get_connection(self):
        """Obtiene conexión a la base SQL real."""
        try:
            return pyodbc.connect(self.connection_string)
        except Exception as e:
            print(f"❌ Error conectando a Dragon DB: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Prueba la conexión a la base SQL real."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                print(f"✅ Conexión exitosa a {self.server}\\{self.database}")
                return True
        except Exception as e:
            print(f"❌ Error en test de conexión: {e}")
            return False
    
    def get_barcode_for_sku(self, sku: str) -> Optional[str]:
        """
        Obtiene código de barra para un SKU desde la base real.
        Usa la consulta EXACTA proporcionada por el usuario.
        
        IMPORTANTE: Los SKUs de MercadoLibre tienen formato ART-COLOR-TALLE (ej: NYSSB0EPSA-NN0-42)
        pero en Dragon DB solo está almacenado el ARTÍCULO base (ej: NYSSB0EPSA).
        Por eso parseamos el SKU para extraer solo la parte del artículo.
        
        Args:
            sku: SKU del artículo (CARTICUL)
            
        Returns:
            Código de barra (CCODIGO) o None si no se encuentra
        """
        try:
            if not sku or not sku.strip():
                return None
            
            # Parsear SKU: extraer solo la parte del ARTÍCULO
            # Formato MercadoLibre: ART-COLOR-TALLE → Solo necesitamos ART
            articulo = sku.split('-')[0] if '-' in sku else sku
            
            print(f"🔍 SKU original: {sku}")
            print(f"📋 Artículo extraído: {articulo}")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Consulta real usando tabla equi (igual que el pickeador)
                # Buscar por ARTÍCULO base, no por SKU completo
                cursor.execute("""
                    SELECT TOP 1 RTRIM(equi.CCODIGO) AS CODIGO_BARRA
                    FROM dragonfish_deposito.ZooLogic.EQUI AS equi 
                    WHERE RTRIM(equi.CARTICUL) = ?
                      AND equi.CCODIGO IS NOT NULL 
                      AND RTRIM(equi.CCODIGO) != ''
                """, (articulo,))
                
                result = cursor.fetchone()
                
                if result:
                    barcode = result[0]
                    print(f"✅ Código de barra encontrado: {barcode}")
                    return barcode
                else:
                    print(f"❌ No se encontró código de barra para artículo: {articulo}")
                    return None
                
        except Exception as e:
            print(f"❌ Error obteniendo código de barra para SKU {sku}: {e}")
            return None
    
    def get_all_sku_barcode_mapping(self) -> Dict[str, str]:
        """
        Obtiene mapeo completo SKU → código de barra.
        Útil para cache o validación masiva.
        
        Returns:
            Dict con mapeo SKU → código de barra
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Consulta real usando tabla equi
                cursor.execute("""
                    SELECT RTRIM(equi.CARTICUL) AS SKU, RTRIM(equi.CCODIGO) AS CODIGO_BARRA
                    FROM dragonfish_deposito.ZooLogic.EQUI AS equi 
                    WHERE equi.CCODIGO IS NOT NULL 
                      AND RTRIM(equi.CCODIGO) != ''
                      AND equi.CARTICUL IS NOT NULL
                      AND RTRIM(equi.CARTICUL) != ''
                """)
                
                mapping = {}
                for row in cursor.fetchall():
                    sku = row[0].strip()
                    barcode = row[1].strip()
                    mapping[sku] = barcode
                
                print(f"✅ Cargado mapeo de {len(mapping)} SKUs → códigos de barra")
                return mapping
                
        except Exception as e:
            print(f"❌ Error obteniendo mapeo SKU → código de barra: {e}")
            return {}
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la base de datos."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Contar registros en EQUI
                cursor.execute("SELECT COUNT(*) FROM dragonfish_deposito.ZooLogic.EQUI")
                total_equi = cursor.fetchone()[0]
                
                # Contar registros con código de barra
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM dragonfish_deposito.ZooLogic.EQUI 
                    WHERE CCODIGO IS NOT NULL AND RTRIM(CCODIGO) != ''
                """)
                with_barcode = cursor.fetchone()[0]
                
                # Contar SKUs únicos
                cursor.execute("""
                    SELECT COUNT(DISTINCT RTRIM(CARTICUL)) 
                    FROM dragonfish_deposito.ZooLogic.EQUI 
                    WHERE CARTICUL IS NOT NULL AND RTRIM(CARTICUL) != ''
                """)
                unique_skus = cursor.fetchone()[0]
                
                return {
                    'total_records': total_equi,
                    'records_with_barcode': with_barcode,
                    'unique_skus': unique_skus,
                    'barcode_coverage': round((with_barcode / total_equi * 100), 2) if total_equi > 0 else 0
                }
                
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
            return {'error': str(e)}

# Instancia global del servicio
dragon_service = DragonDBService()

def get_barcode_for_sku(sku: str) -> Optional[str]:
    """
    Función principal para obtener código de barra por SKU.
    Compatible con la interfaz existente del pipeline.
    
    Args:
        sku: SKU del artículo
        
    Returns:
        Código de barra o None si no se encuentra
    """
    return dragon_service.get_barcode_for_sku(sku)

def test_connection() -> bool:
    """
    Función para probar la conexión a Dragon DB.
    Compatible con la interfaz existente del pipeline.
    
    Returns:
        True si la conexión es exitosa
    """
    return dragon_service.test_connection()

def test_known_sku(sku: str = "NYSSB0EPSA-NN0-42") -> bool:
    """
    Prueba con SKU conocido para validar funcionamiento.
    
    Args:
        sku: SKU conocido para probar
        
    Returns:
        True si encuentra el SKU
    """
    print(f"🧪 Probando SKU conocido: {sku}")
    
    # Probar conexión
    if not test_connection():
        return False
    
    # Buscar barcode
    barcode = get_barcode_for_sku(sku)
    
    if barcode:
        print(f"✅ SKU conocido encontrado: {sku} → {barcode}")
        return True
    else:
        print(f"❌ SKU conocido NO encontrado: {sku}")
        return False

if __name__ == "__main__":
    print("🧪 PRUEBA MÓDULO DRAGON DB - CONFIGURACIÓN REAL")
    print("=" * 60)
    
    # Probar conexión
    print("\n📡 PASO 1: Probar conexión")
    if test_connection():
        print("✅ Conexión exitosa")
    else:
        print("❌ Conexión falló")
        exit(1)
    
    # Obtener estadísticas
    print("\n📊 PASO 2: Estadísticas de base")
    stats = dragon_service.get_database_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Probar SKU conocido
    print("\n🧪 PASO 3: Probar SKU conocido")
    success = test_known_sku("NYSSB0EPSA-NN0-42")
    
    if success:
        print("\n🎉 ¡MÓDULO DRAGON DB FUNCIONANDO CORRECTAMENTE!")
    else:
        print("\n❌ MÓDULO DRAGON DB TIENE PROBLEMAS")
