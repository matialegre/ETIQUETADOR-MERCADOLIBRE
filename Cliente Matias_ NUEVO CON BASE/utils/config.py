"""Carga de configuración desde variables de entorno usando python-dotenv"""
from pathlib import Path
from dotenv import load_dotenv
import os

# Carga .env en el directorio raíz del proyecto
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=False)

# Configuración ML1 (cuenta principal)
ML_CLIENT_ID = os.getenv('ML_CLIENT_ID')
ML_CLIENT_SECRET = os.getenv('ML_CLIENT_SECRET')
ML_REFRESH_TOKEN = os.getenv('ML_REFRESH_TOKEN')

# Configuración ML2 (segunda cuenta)
ML2_CLIENT_ID = os.getenv('ML2_CLIENT_ID', '8063857234740063')
ML2_CLIENT_SECRET = os.getenv('ML2_CLIENT_SECRET', 'sV4A7MufbYvL58rzg9W56Va8u36OlsIb')
ML2_REFRESH_TOKEN = os.getenv('ML2_REFRESH_TOKEN', 'TG-68836d43203257000167d6a2-756086955')
ML2_ACCESS_TOKEN = os.getenv('ML2_ACCESS_TOKEN', 'APP_USR-8063857234740063-072507-ab34665341fd56221fa2c0bcb8f97c98-756086955')
ML2_USER_ID = os.getenv('ML2_USER_ID', '756086955')

# Configuración común
DRAGONFISH_TOKEN = os.getenv('DRAGONFISH_TOKEN')
SQL_CONN_STR = os.getenv('SQL_CONN_STR')
PRINTER_NAME = os.getenv('PRINTER_NAME', 'Xprinter XP-410B')

if not ML_CLIENT_ID:
    print("⚠️  ML_CLIENT_ID no definido. Usa .env o variables de entorno.")
