# config_override_caba.py
"""
Configuración override para CABA - Solo cambia las credenciales y filtros necesarios.
Se importa al inicio para sobrescribir las configuraciones originales.
"""

import os

# ===== CONFIGURACIONES CABA =====
# API Dragonfish remota en Bahía Blanca
DRAGONFISH_BASE_URL_CABA = 'http://190.211.201.217:8888/api.Dragonfish'

# SQL Server CABA - Configuración con IP y puerto
SQL_SERVER_CABA = '192.168.1.14,1433'
DATABASE_NAME_CABA = 'DRAGONFISH_MUNDOCAB'

# Credenciales SQL Authentication
SQL_USER_CABA = 'cliente_app'
SQL_PASSWORD_CABA = 'ContraseñaFuerte123!'

# Depósito para movimientos SQL
DEPOSITO_NAME_CABA = 'MUNDOCAB'

# Keywords específicos para CABA
KEYWORDS_NOTE_CABA = ['CAB', 'CABA', 'MUNDOCAB']

# String de conexión SQL específico para CABA
# SQL Authentication con usuario dedicado
SQL_CONN_STR_CABA = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={SQL_SERVER_CABA};"
    f"DATABASE={DATABASE_NAME_CABA};"
    f"UID={SQL_USER_CABA};"
    f"PWD={SQL_PASSWORD_CABA};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

# Aplicar configuraciones a variables de entorno
os.environ['DRAGONFISH_BASE_URL'] = DRAGONFISH_BASE_URL_CABA
os.environ['SQL_SERVER'] = SQL_SERVER_CABA
os.environ['DATABASE_NAME'] = DATABASE_NAME_CABA
os.environ['DEPOSITO_NAME'] = DEPOSITO_NAME_CABA
# ¡CRÍTICO! Establecer el string de conexión SQL que usa utils/db.py
os.environ['SQL_CONN_STR'] = SQL_CONN_STR_CABA

# Mostrar configuración aplicada
print("🏢 CONFIGURACIÓN CABA APLICADA:")
print(f"📡 API Dragonfish: {DRAGONFISH_BASE_URL_CABA}")
print(f"🗄️ SQL Server: {SQL_SERVER_CABA}")
print(f"📊 Base de datos: {DATABASE_NAME_CABA}")
print(f"🏦 Depósito: {DEPOSITO_NAME_CABA}")
print(f"🏷️ Filtros: {KEYWORDS_NOTE_CABA}")
print(f"🔗 SQL Connection String: {SQL_CONN_STR_CABA}")

# Función para obtener configuraciones CABA
def get_caba_config():
    """Retorna las configuraciones específicas de CABA."""
    return {
        'dragonfish_url': DRAGONFISH_BASE_URL_CABA,
        'sql_server': SQL_SERVER_CABA,
        'database_name': DATABASE_NAME_CABA,
        'deposito_name': DEPOSITO_NAME_CABA,
        'keywords_note': KEYWORDS_NOTE_CABA,
        'sql_conn_str': SQL_CONN_STR_CABA
    }

# Función para verificar configuración SQL
def test_sql_connection():
    """Prueba la conexión SQL con la configuración CABA."""
    try:
        import pyodbc
        conn = pyodbc.connect(SQL_CONN_STR_CABA)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        print("✅ Conexión SQL CABA exitosa")
        return True
    except Exception as e:
        print(f"❌ Error conexión SQL CABA: {e}")
        return False
