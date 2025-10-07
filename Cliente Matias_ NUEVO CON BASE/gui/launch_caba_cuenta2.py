import os, sys, pathlib
import tkinter as tk
import ttkbootstrap as tb
import json
from datetime import datetime, timedelta

# EXE: token al lado del ejecutable; DEV: usar config/token_cuenta2.json
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    token_path = os.path.join(exe_dir, 'token_cuenta2.json')
else:
    project_root = pathlib.Path(__file__).resolve().parents[1]
    primary_dev_path = project_root / 'config' / 'token_cuenta2.json'
    fallback_dev_path = pathlib.Path(__file__).resolve().parent / 'token_02.json'
    if primary_dev_path.exists():
        token_path = str(primary_dev_path)
    elif fallback_dev_path.exists():
        token_path = str(fallback_dev_path)
        print(f"[CABA CUENTA2][WARN] No se encontró {primary_dev_path}. Usando fallback: {fallback_dev_path}")
    else:
        # Default (aunque no exista) para que el log muestre dónde se esperaba
        token_path = str(primary_dev_path)
        print(f"[CABA CUENTA2][ERROR] No se encontró token en {primary_dev_path} ni fallback {fallback_dev_path}.")

# Variables de entorno para servicios que leen la ubicación del token
os.environ['TOKEN_PATH'] = token_path
os.environ['ML_TOKEN_PATH'] = token_path
os.environ['CABA_VERSION'] = 'true'

# Banner configurable (igual que cuenta1, pero se puede personalizar)
os.environ.setdefault('BANNER_TEXT', 'PAQUETERÍA CORREO (CÓDIGO QR)')
os.environ.setdefault('BANNER_FG', '#FF0000')  # rojo
os.environ.setdefault('BANNER_BG', '#000000')  # negro

# Logs de diagnóstico útiles
print(f"[CABA CUENTA2] frozen={getattr(sys, 'frozen', False)}")
print(f"[CABA CUENTA2] TOKEN_PATH={token_path}")

# Si el token falta o no tiene refresh_token, activar bootstrap interactivo
try:
    need_bootstrap = False
    if not os.path.isfile(token_path):
        need_bootstrap = True
    else:
        try:
            with open(token_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not data.get('refresh_token'):
                need_bootstrap = True
                print("[CABA CUENTA2][WARN] token presente pero sin refresh_token: se habilita bootstrap interactivo.")
        except Exception as e:
            need_bootstrap = True
            print(f"[CABA CUENTA2][WARN] No se pudo leer token ({e}): se habilita bootstrap interactivo.")
    if need_bootstrap:
        os.environ['ML_INTERACTIVE_BOOTSTRAP'] = '1'
        print("[CABA CUENTA2] ML_INTERACTIVE_BOOTSTRAP=1 habilitado para generar token.")
except Exception:
    pass

# Asegurar imports del proyecto (modo desarrollo/pyinstaller)
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import robusto del módulo principal
try:
    from gui import app_gui_v3_caba_real as app
except ModuleNotFoundError:
    import app_gui_v3_caba_real as app

# Lanzar la GUI de la misma forma que cuenta1 para poder inyectar banner
window = app.AppV3()

# Ajustar rango de fechas por defecto: desde hace 7 días hasta hoy
try:
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)
    # Establecer valores en los StringVar de la ventana
    if hasattr(window, 'var_from') and hasattr(window, 'var_to'):
        window.var_from.set(seven_days_ago.strftime("%d/%m/%Y"))
        window.var_to.set(today.strftime("%d/%m/%Y"))
except Exception:
    # No bloquear si falla el ajuste de fechas
    pass

# Inyectar banner superior grande (si está configurado)
try:
    banner_text = os.environ.get('BANNER_TEXT', '').upper()
    banner_fg = os.environ.get('BANNER_FG', '#FFD400')
    banner_bg = os.environ.get('BANNER_BG', '#000000')
    if banner_text:
        banner = tb.Label(window, text=banner_text, anchor='center',
                          font=('Segoe UI', 24, 'bold'),
                          foreground=banner_fg, background=banner_bg)
        banner.pack(side='top', fill='x')
except Exception:
    # No bloquear si el banner falla
    pass

window.mainloop()
