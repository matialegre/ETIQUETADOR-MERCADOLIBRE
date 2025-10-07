import os, sys, pathlib
import tkinter as tk
import ttkbootstrap as tb

# Si es EXE, usa el token al lado del ejecutable; si no, usa el de desarrollo
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    token_path = os.path.join(exe_dir, 'token_cuenta1.json')
else:
    project_root = pathlib.Path(__file__).resolve().parents[1]
    token_path = str(project_root / 'config' / 'token_cuenta1.json')

# Hacer visible para los servicios que leen TOKEN_PATH
os.environ['TOKEN_PATH'] = token_path
os.environ['ML_TOKEN_PATH'] = token_path
os.environ['CABA_VERSION'] = 'true'
os.environ['BANNER_TEXT'] = 'paqueteria andreani (codigo de barra)'
os.environ['BANNER_FG'] = '#FFD400'  # amarillo
os.environ['BANNER_BG'] = '#000000'  # negro

# Si el token no existe, activar bootstrap interactivo para generarlo
try:
    if not os.path.isfile(token_path):
        os.environ['ML_INTERACTIVE_BOOTSTRAP'] = '1'
        print(f"[CABA CUENTA1][WARN] No existe token en {token_path}. Se habilita ML_INTERACTIVE_BOOTSTRAP=1 para generarlo.")
except Exception:
    pass

# Logs de diagnóstico útiles
print(f"[CABA CUENTA1] frozen={getattr(sys, 'frozen', False)}")
print(f"[CABA CUENTA1] TOKEN_PATH={token_path}")

# Asegurar imports del proyecto
ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

"""Import robusto del módulo principal de la GUI.
Primero intentamos importarlo como parte del paquete 'gui' para que PyInstaller
lo detecte y lo incluya correctamente. Si no existe el paquete, usamos el import
plano como estaba antes (modo desarrollo ejecutando dentro de gui/).
"""
try:
    from gui import app_gui_v3_caba_real as app
except ModuleNotFoundError:
    import app_gui_v3_caba_real as app

# Lanzar la GUI
window = app.AppV3()

# Inyectar banner superior grande y coloreado
try:
    banner_text = os.environ.get('BANNER_TEXT', '').upper()
    banner_fg = os.environ.get('BANNER_FG', '#FFD400')
    banner_bg = os.environ.get('BANNER_BG', '#000000')
    if banner_text:
        banner = tb.Label(window, text=banner_text, anchor='center',
                          font=('Segoe UI', 24, 'bold'),
                          foreground=banner_fg, background=banner_bg)
        banner.pack(side='top', fill='x')
except Exception as e:
    # Si falla la inyección del banner, continuar sin bloquear la app
    pass

window.mainloop()
