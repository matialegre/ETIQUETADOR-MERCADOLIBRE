import os, sys, pathlib

# Si es EXE, usa el token al lado del ejecutable; si no, usa el de desarrollo
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    token_path = os.path.join(exe_dir, 'token_cuenta1.json')
else:
    project_root = pathlib.Path(__file__).resolve().parents[1]
    token_path = str(project_root / 'config' / 'token.json')

# Hacer visible para los servicios que leen TOKEN_PATH
os.environ['TOKEN_PATH'] = token_path
os.environ['ML_TOKEN_PATH'] = token_path  # Para utils.meli_token_helper / api.ml_api
os.environ['CABA_VERSION'] = 'true'

# Asegurar imports del proyecto
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Importar la app CABA real (ubicada en el mismo directorio que este launcher)
import app_gui_v3_caba_real as app

# Lanzar la GUI
if hasattr(app, 'launch_gui_v3'):
    app.launch_gui_v3()
else:
    app.AppV3().mainloop()
