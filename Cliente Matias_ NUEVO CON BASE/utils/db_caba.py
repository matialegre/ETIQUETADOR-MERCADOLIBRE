# utils/db_caba.py
"""
Utilidades de base de datos específicas para CABA.
Conecta a la base de datos remota DRAGONFISH_MUNDOCAB.
"""

import pyodbc
from typing import Optional, List, Tuple, Any
from utils.logger import get_logger
import config_caba

log = get_logger(__name__)

class DatabaseCaba:
    """Manejador de base de datos para CABA."""
    
    def __init__(self):
        self.connection_string = config_caba.SQL_CONNECTION_STRING
        self.connection = None
        log.info(f"🗄️ Configurando conexión DB CABA: {config_caba.SQL_SERVER}")
    
    def connect(self) -> bool:
        """Establece conexión con la base de datos de CABA."""
        try:
            self.connection = pyodbc.connect(self.connection_string)
            log.info("✅ Conexión exitosa con base de datos CABA")
            return True
        except pyodbc.Error as e:
            log.error(f"❌ Error conectando a DB CABA: {e}")
            return False
        except Exception as e:
            log.error(f"❌ Error inesperado conectando a DB CABA: {e}")
            return False
    
    def disconnect(self):
        """Cierra la conexión con la base de datos."""
        if self.connection:
            self.connection.close()
            self.connection = None
            log.debug("🔌 Conexión DB CABA cerrada")
    
    def execute_query(self, query: str, params: Optional[List] = None) -> Optional[List[Tuple]]:
        """
        Ejecuta una consulta SELECT y retorna los resultados.
        
        Args:
            query: Consulta SQL
            params: Parámetros para la consulta
            
        Returns:
            List[Tuple]: Resultados de la consulta, o None si hay error
        """
        if not self.connection:
            if not self.connect():
                return None
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            results = cursor.fetchall()
            cursor.close()
            
            log.debug(f"📊 Consulta ejecutada: {len(results)} resultados")
            return results
            
        except pyodbc.Error as e:
            log.error(f"❌ Error ejecutando consulta: {e}")
            return None
        except Exception as e:
            log.error(f"❌ Error inesperado en consulta: {e}")
            return None
    
    def execute_non_query(self, query: str, params: Optional[List] = None) -> bool:
        """
        Ejecuta una consulta INSERT/UPDATE/DELETE.
        
        Args:
            query: Consulta SQL
            params: Parámetros para la consulta
            
        Returns:
            bool: True si la ejecución fue exitosa
        """
        if not self.connection:
            if not self.connect():
                return False
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            self.connection.commit()
            cursor.close()
            
            log.debug("✅ Consulta de modificación ejecutada exitosamente")
            return True
            
        except pyodbc.Error as e:
            log.error(f"❌ Error ejecutando consulta de modificación: {e}")
            if self.connection:
                self.connection.rollback()
            return False
        except Exception as e:
            log.error(f"❌ Error inesperado en consulta de modificación: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def get_barcode_by_sku(self, sku: str) -> Optional[str]:
        """
        Busca el código de barras asociado a un SKU en la base de CABA.
        
        Args:
            sku: SKU a buscar
            
        Returns:
            str: Código de barras, o None si no se encuentra
        """
        query = """
        SELECT CodigoBarra 
        FROM Articulos 
        WHERE CodigoML = ? OR SKU = ?
        """
        
        results = self.execute_query(query, [sku, sku])
        
        if results and len(results) > 0:
            barcode = results[0][0]
            log.debug(f"🔍 Código de barras encontrado para {sku}: {barcode}")
            return barcode
        else:
            log.debug(f"🔍 No se encontró código de barras para SKU: {sku}")
            return None
    
    def get_sku_by_barcode(self, barcode: str) -> Optional[str]:
        """
        Busca el SKU asociado a un código de barras en la base de CABA.
        
        Args:
            barcode: Código de barras a buscar
            
        Returns:
            str: SKU, o None si no se encuentra
        """
        query = """
        SELECT CodigoML, SKU 
        FROM Articulos 
        WHERE CodigoBarra = ?
        """
        
        results = self.execute_query(query, [barcode])
        
        if results and len(results) > 0:
            codigo_ml = results[0][0]
            sku = results[0][1]
            # Preferir CodigoML si existe, sino usar SKU
            result_sku = codigo_ml if codigo_ml else sku
            log.debug(f"🔍 SKU encontrado para código {barcode}: {result_sku}")
            return result_sku
        else:
            log.debug(f"🔍 No se encontró SKU para código de barras: {barcode}")
            return None
    
    def test_connection(self) -> bool:
        """Prueba la conexión con la base de datos."""
        try:
            if self.connect():
                # Hacer una consulta simple para verificar
                results = self.execute_query("SELECT 1")
                if results:
                    log.info("✅ Test de conexión DB CABA exitoso")
                    return True
            return False
        except Exception as e:
            log.error(f"❌ Test de conexión DB CABA falló: {e}")
            return False

# Instancia global para usar en toda la aplicación CABA
db_caba = DatabaseCaba()

# Funciones de compatibilidad con la API original
def fetchone_caba(query: str, params: Optional[List] = None) -> Optional[Tuple]:
    """Función de compatibilidad para obtener un solo resultado."""
    results = db_caba.execute_query(query, params)
    return results[0] if results and len(results) > 0 else None

def fetchall_caba(query: str, params: Optional[List] = None) -> Optional[List[Tuple]]:
    """Función de compatibilidad para obtener todos los resultados."""
    return db_caba.execute_query(query, params)

def execute_caba(query: str, params: Optional[List] = None) -> bool:
    """Función de compatibilidad para ejecutar consultas de modificación."""
    return db_caba.execute_non_query(query, params)
