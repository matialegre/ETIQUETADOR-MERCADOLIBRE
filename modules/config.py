"""
Configuración del pipeline MercadoLibre
======================================

Variables de entorno y configuración global del sistema.
"""

import os
from typing import Optional, Dict, List

# Cargar .env del proyecto explícitamente para ejecuciones por .bat / scripts
try:
    from dotenv import load_dotenv  # type: ignore
    _proj_root = os.path.dirname(os.path.dirname(__file__))
    _env_path = os.path.join(_proj_root, 'config', '.env')
    if os.path.isfile(_env_path):
        load_dotenv(_env_path, override=True)
    else:
        load_dotenv()
except Exception:
    # Si no está python-dotenv, seguimos con variables del entorno del proceso
    pass


# Variables de entorno para MercadoLibre API
MELI_SELLER_ID: Optional[str] = os.getenv('MELI_SELLER_ID')
MELI_ACCESS_TOKEN: Optional[str] = os.getenv('MELI_ACCESS_TOKEN')
MELI_REFRESH_TOKEN: Optional[str] = os.getenv('MELI_REFRESH_TOKEN')
MELI_CLIENT_ID: Optional[str] = os.getenv('MELI_CLIENT_ID')
MELI_CLIENT_SECRET: Optional[str] = os.getenv('MELI_CLIENT_SECRET')

# Perfiles Dragonfish: selector 0/1 para alternar entre clientes/hosts/tokens
# Puedes cambiar el perfil activo con la variable de entorno DRAGON_PROFILE_SELECT o editando el valor por defecto.
DRAGON_PROFILE_SELECT: int = int(os.getenv('DRAGON_PROFILE_SELECT', '1'))  # 0=legacy, 1=nuevo (por defecto)

_DRAGON_PROFILES: dict[int, dict[str, str]] = {
    # 0) Perfil legacy/actual (host anterior)
    0: {
        'base': 'http://deposito_2:8888/api.Dragonfish/ConsultaStockYPreciosEntreLocales',
        'id_cliente': 'MATIAPP',
        # Token previo (si tienes un token distinto para el perfil 0, puedes moverlo aquí)
        'token': os.getenv('DRAGON_API_KEY', 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MTc5ODg0ODQsInVzdWFyaW8iOiJhZG1pbiIsInBhc3N3b3JkIjoiMDE5NGRkMGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4MWQwMyJ9.zAWCBxY5smFLyDrNAPqeaaoOJbmG-R-SM7mFFg7MQeE'),
    },
    # 1) Perfil nuevo (IP y credenciales provistas)
    1: {
        # Nota: La URL de docs fue provista; usamos el endpoint real de consulta
        'base': 'http://190.211.201.217:8888/api.Dragonfish/ConsultaStockYPreciosEntreLocales',
        'id_cliente': 'MATIAPP',
        'token': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MTc5ODg0ODQsInVzdWFyaW8iOiJhZG1pbiIsInBhc3N3b3JkIjoiMDE5NGRkMGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4MWQwMyJ9.zAWCBxY5smFLyDrNAPqeaaoOJbmG-R-SM7mFFg7MQeE',
    },
}

# Construcción de variables efectivas a partir del perfil seleccionado (con override por ENV si existen)
_sel = _DRAGON_PROFILES.get(DRAGON_PROFILE_SELECT, _DRAGON_PROFILES[1])

DRAGON_API_BASES: list[str] = [
    s.strip() for s in os.getenv('DRAGON_API_BASES', _sel['base']).split(',') if s.strip()
]
# Compat: primer base como "base principal"
DRAGON_API_BASE: Optional[str] = os.getenv('DRAGON_API_BASE', DRAGON_API_BASES[0] if DRAGON_API_BASES else None)
DRAGON_API_KEY: Optional[str] = os.getenv('DRAGON_API_KEY', _sel['token'])
DRAGON_ID_CLIENTE: Optional[str] = os.getenv('DRAGON_ID_CLIENTE', _sel['id_cliente'])

# Switch único de destino de movimiento: 'WOO' o 'MELI'
MOVIMIENTO_TARGET: str = os.getenv('MOVIMIENTO_TARGET', 'MELI').strip()

# Base de datos objetivo para registrar movimientos (derivada, pero sobre-escribible por env)
DRAGON_BASEDEDATOS: Optional[str] = os.getenv('DRAGON_BASEDEDATOS', MOVIMIENTO_TARGET)

# Conexión SQL Server:
#  - SQLSERVER_CONN_STR: Base Dragon (EQUI/ART) para consultas de artículos
#  - SQLSERVER_APP_CONN_STR: Base de la app (orders_meli)
# Default ajustado al servidor real de Dragonfish provisto por el usuario
SQLSERVER_CONN_STR: Optional[str] = os.getenv(
    'SQLSERVER_CONN_STR',
    'DRIVER={ODBC Driver 17 for SQL Server};SERVER=ranchoaspen\\zoo2025;DATABASE=dragonfish_deposito;Trusted_Connection=yes;'
)
SQLSERVER_APP_CONN_STR: Optional[str] = os.getenv(
    'SQLSERVER_APP_CONN_STR',
    'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
)

# Alternativas de API Dragonfish (credenciales/host secundarios)
_ALT_BASES_RAW = os.getenv('DRAGON_ALT_API_BASES', '').strip()
DRAGON_ALT_API_BASES: list[str] = [s.strip() for s in _ALT_BASES_RAW.split(',') if s.strip()]
DRAGON_ALT_API_KEY: Optional[str] = os.getenv('DRAGON_ALT_API_KEY')
DRAGON_ALT_ID_CLIENTE: Optional[str] = os.getenv('DRAGON_ALT_ID_CLIENTE')

# Lista de depósitos candidatos para fallback per-depósito (BaseDeDatos header)
# Se puede sobreescribir por env con DRAGON_DEPOT_CANDIDATES="DEPOSITO,MUNDOCAB,MONBAHIA,..."
_dep_env = os.getenv('DRAGON_DEPOT_CANDIDATES', 'DEPOSITO,MUNDOCAB,MONBAHIA,MTGBBPS,MTGROCA,MUNDOAL,MUNDOROC,NQNALB,NQNSHOP,MTGCOM')
DRAGON_DEPOT_CANDIDATES: list[str] = [s.strip().upper() for s in _dep_env.split(',') if s.strip()]

# URL de Movimiento de Stock (WOO→WOO) - Dragonfish
DRAGON_MOV_URL: Optional[str] = os.getenv('DRAGON_MOV_URL', 'http://190.211.201.217:8009/api.Dragonfish/Movimientodestock/')

# Parámetros editables por defecto para movimiento (OrigenDestino)
# OrigenDestino por defecto deriva de MOVIMIENTO_TARGET, pero puede sobre-escribirse por env
MOV_ORIGENDESTINO_DEFAULT: str = os.getenv('MOV_ORIGENDESTINO_DEFAULT', MOVIMIENTO_TARGET)
MOV_TIPO_DEFAULT: int = int(os.getenv('MOV_TIPO_DEFAULT', '2'))

# Variables de configuración del pipeline
SLEEP_BETWEEN_CYCLES: int = int(os.getenv('SLEEP_BETWEEN_CYCLES', '300'))  # 5 minutos
DEPOSIT_PRIORITY: list[str] = os.getenv('DEPOSIT_PRIORITY', 'DEP1,DEP2,DEP3').split(',')

# Variables de notificaciones
WEBHOOK_STOCK_ZERO: Optional[str] = os.getenv('WEBHOOK_STOCK_ZERO')

# Configuración de timeouts y reintentos
API_TIMEOUT: int = int(os.getenv('API_TIMEOUT', '30'))
API_RETRIES: int = int(os.getenv('API_RETRIES', '3'))

# Lógica de multiventa/cluster (apagada por defecto para no romper lo actual)
MULTIVENTA_MODE: str = os.getenv('MULTIVENTA_MODE', 'clustered').strip()  # valores: 'off' | 'clustered'
MAX_SHIPMENTS: int = int(os.getenv('MAX_SHIPMENTS', '2'))

# Definición de clusters de depósitos cercanos (validado con el usuario)
# Cercanos: 'DEPO', 'MUNDOAL', 'MTGBBL', 'MONBAHIA', 'MTGBBPS'
# Importante: usar SIEMPRE 'MTGBBPS' (no 'BBPS'). Se mantiene 'DEP' como alias de 'DEPO'.
CLUSTERS: Dict[str, List[str]] = {
    'A': ['DEPO', 'DEP', 'MUNDOAL', 'MTGBBL', 'MONBAHIA', 'MTGBBPS'],
    'B': ['MUNDOROC', 'MTGROCA'],
}
LEJANOS: List[str] = ['MTGCOM', 'NQNSHOP', 'NQNALB', 'MUNDOCAB']


def validate_config() -> dict[str, bool]:
    """
    Valida que las variables de configuración críticas estén presentes.
    
    Returns:
        Dict con el estado de validación de cada variable crítica
    """
    return {
        'meli_seller_id': MELI_SELLER_ID is not None,
        'meli_access_token': MELI_ACCESS_TOKEN is not None,
        'sqlserver_conn_str': SQLSERVER_CONN_STR is not None,
        'sqlserver_app_conn_str': SQLSERVER_APP_CONN_STR is not None,
        'dragon_api_base': DRAGON_API_BASE is not None,
        'dragon_api_key': DRAGON_API_KEY is not None,
        'dragon_id_cliente': DRAGON_ID_CLIENTE is not None,
        'dragon_mov_url': DRAGON_MOV_URL is not None,
    }
