"""
Variante ROCA de la app GUI v3.
No modifica código base; solo fija configuración y filtros propios de ROCA.
"""
from __future__ import annotations

import os
import sys, pathlib
# Permitir ejecución directa añadiendo el directorio raíz al sys.path (igual que CABA)
# Evitar modificar sys.path cuando está congelado (PyInstaller)
FROZEN = getattr(sys, "frozen", False)
if not FROZEN:
    ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

from utils import config

# --- Configuración específica ROCA ---
# 2) Base URL de Dragonfish (IP pública)
config.DRAGONFISH_BASE_URL = "http://190.211.201.217:8009/api.Dragonfish"

# 3) SQL Server y Base de datos
#    Conexión por Trusted_Connection (Windows). Ajustar si se requiere usuario/clave.
SQL_SERVER = r"DESKTOP-BPHJOFO\ZOOLOGIC"
DATABASE_NAME = "DRAGONFISH_MUNDOROC"

config.SQL_CONN_STR = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={DATABASE_NAME};"
    f"Trusted_Connection=yes;"
)

# PickerService usa DATABASE_NAME desde el entorno para armar queries (schema ZooLogic)
os.environ["DATABASE_NAME"] = DATABASE_NAME
os.environ["ROCA_VERSION"] = "true"

# Importar la app base recién ahora, para que tome la config anterior
try:
    import app_gui_v3 as base
except ModuleNotFoundError:
    # Fallback cuando corre desde un entorno donde el módulo se resuelve como paquete 'gui'
    from gui import app_gui_v3 as base

# 1) Filtro por comentario/nota (se puede fijar después de importar)
base.KEYWORDS_NOTE = ['MUNDOROC']


if __name__ == '__main__':
    app = base.AppV3()
    try:
        app.title("Cliente Matías – ROCA")
    except Exception:
        pass
    app.mainloop()
