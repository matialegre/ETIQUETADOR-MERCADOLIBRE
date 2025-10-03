@echo off
setlocal ENABLEDELAYEDEXPANSION

rem Ir a la carpeta EnvioStock (relativa a este .bat)
pushd "%~dp0EnvioStock" || (echo No se pudo entrar a EnvioStock & exit /b 1)

rem Detectar PyInstaller del venv; si no, usar del PATH
set "PYI=pyinstaller"
if exist ".venv\Scripts\pyinstaller.exe" set "PYI=.venv\Scripts\pyinstaller.exe"

rem Lanzar cada build en CONSOLAS SEPARADAS que se cierran al terminar
start "Build MONBAHIA" cmd /c ""%PYI%" --onefile --console --name "Cliente_Matias_GUI_v3_MONBAHIA" --icon "icono.ico" --clean --add-data "api;api" --add-data "services;services" --add-data "models;models" --add-data "utils;utils" --add-data "printing;printing" --add-data "gui;gui" --hidden-import "ttkbootstrap" --hidden-import "ttkbootstrap.dialogs" --hidden-import "requests" --hidden-import "python-dotenv" --hidden-import "tkinter" --hidden-import "win32print" --hidden-import "win32api" --hidden-import "reportlab" --collect-all reportlab launch_monbahia.py"

start "Build MUNDOAL" cmd /c ""%PYI%" --onefile --console --name "Cliente_Matias_GUI_v3_MUNDOAL" --icon "icono.ico" --clean --add-data "api;api" --add-data "services;services" --add-data "models;models" --add-data "utils;utils" --add-data "printing;printing" --add-data "gui;gui" --hidden-import "ttkbootstrap" --hidden-import "ttkbootstrap.dialogs" --hidden-import "requests" --hidden-import "python-dotenv" --hidden-import "tkinter" --hidden-import "win32print" --hidden-import "win32api" --hidden-import "reportlab" --collect-all reportlab launch_mundoal.py"

start "Build MTGBBPS" cmd /c ""%PYI%" --onefile --console --name "Cliente_Matias_GUI_v3_MTGBBPS" --icon "icono.ico" --clean --add-data "api;api" --add-data "services;services" --add-data "models;models" --add-data "utils;utils" --add-data "printing;printing" --add-data "gui;gui" --hidden-import "ttkbootstrap" --hidden-import "ttkbootstrap.dialogs" --hidden-import "requests" --hidden-import "python-dotenv" --hidden-import "tkinter" --hidden-import "win32print" --hidden-import "win32api" --hidden-import "reportlab" --collect-all reportlab launch_bbps.py"

popd
endlocal
