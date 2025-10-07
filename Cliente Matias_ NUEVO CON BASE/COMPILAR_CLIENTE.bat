@echo off
title Compilando Cliente Chat - Mundo Outdoor
echo.
echo ========================================
echo   COMPILANDO CLIENTE DE CHAT
echo ========================================
echo.
echo Instalando PyInstaller si no esta...
pip install pyinstaller
echo.
echo Compilando cliente...
echo.
pyinstaller --onefile --windowed --name "ChatCliente_MundoOutdoor" --add-data "templates;templates" --hidden-import "flask" --hidden-import "flask_socketio" --hidden-import "python_socketio" --hidden-import "python_engineio" --hidden-import "werkzeug" --hidden-import "threading" --clean chat_cliente.py
echo.
echo ========================================
echo   COMPILACION COMPLETADA
echo ========================================
echo.
echo El archivo .exe esta en: dist\ChatCliente_MundoOutdoor.exe
echo.
echo Copia este archivo a la computadora del deposito
echo y ejecutalo directamente (no necesita Python)
echo.
pause
