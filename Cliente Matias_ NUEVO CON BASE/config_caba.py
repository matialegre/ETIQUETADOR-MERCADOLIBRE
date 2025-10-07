# config_caba.py
"""
Configuración específica para la versión CABA del sistema de picking.
Esta versión apunta al servidor remoto de Bahía Blanca y usa la base de datos de CABA.
"""

# ===== CONFIGURACIÓN DRAGONFISH API =====
# API remota en Bahía Blanca
DRAGONFISH_BASE_URL = "http://190.211.201.217:8888/api.Dragonfish"
DRAGONFISH_DOCS_URL = "http://190.211.201.217:8888/api.Dragonfish/docs/"

# ===== CONFIGURACIÓN SQL SERVER =====
# Base de datos en CABA
SQL_SERVER = 'DESKTOP-CK25NCF\\ZOOLOGIC'
DATABASE_NAME = 'DRAGONFISH_MUNDOCAB'
SQL_USERNAME = None  # Se usará autenticación Windows por defecto
SQL_PASSWORD = None

# String de conexión para SQL Server
SQL_CONNECTION_STRING = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SQL_SERVER};DATABASE={DATABASE_NAME};Trusted_Connection=yes;"

# ===== FILTROS DE NOTAS ESPECÍFICOS PARA CABA =====
# Keywords para filtrar pedidos de CABA
KEYWORDS_NOTE_CABA = ['CAB', 'CABA', 'MUNDOCAB']

# ===== CONFIGURACIÓN DE DEPÓSITO =====
DEPOSITO_NAME = "CABA"
DEPOSITO_DISPLAY_NAME = "MUNDO CABA"

# ===== CONFIGURACIÓN DE IMPRESIÓN =====
# Filtros específicos para impresión de PDFs en CABA
PDF_FILTER_KEYWORDS = KEYWORDS_NOTE_CABA

# ===== CONFIGURACIÓN DE GUI =====
# Título de la aplicación para CABA
APP_TITLE = "Cliente Matías - MUNDO CABA"
APP_VERSION = "CABA v1.0"

# ===== CONFIGURACIÓN DE LOGS =====
LOG_PREFIX = "CABA"

# ===== MERCADOLIBRE (mantener igual) =====
# Las credenciales de ML se mantienen iguales
ML_APP_ID = None  # Se cargará desde variables de entorno o config principal
ML_CLIENT_SECRET = None
ML_REFRESH_TOKEN = None

# ===== CONFIGURACIÓN DE IMPRESORA =====
# Se puede configurar una impresora específica para CABA si es necesario
PRINTER_NAME = None  # Se usará la predeterminada del sistema

print(f"🏢 Configuración CABA cargada:")
print(f"   📡 API Dragonfish: {DRAGONFISH_BASE_URL}")
print(f"   🗄️  SQL Server: {SQL_SERVER}")
print(f"   📊 Base de datos: {DATABASE_NAME}")
print(f"   🏷️  Keywords: {KEYWORDS_NOTE_CABA}")
