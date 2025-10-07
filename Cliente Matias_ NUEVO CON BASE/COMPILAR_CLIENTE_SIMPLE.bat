@echo off
title Compilando Cliente Simple - Mundo Outdoor
echo.
echo ========================================
echo   COMPILANDO CLIENTE SIMPLE DE CHAT
echo ========================================
echo.
echo Este cliente NO usa SocketIO del lado del servidor
echo Solo usa Flask simple + JavaScript con Socket.IO del navegador
echo.
echo Instalando PyInstaller si no esta...
pip install pyinstaller
echo.
echo Compilando cliente simple...
echo.
pyinstaller --onefile --windowed --name "ChatClienteSimple_MundoOutdoor" --add-data "templates;templates" --hidden-import "flask" --hidden-import "werkzeug" --hidden-import "threading" --clean chat_cliente_simple.py
echo.
echo ========================================
echo   COMPILACION COMPLETADA
echo ========================================
echo.
echo El archivo .exe esta en: dist\ChatClienteSimple_MundoOutdoor.exe
echo.
echo VENTAJAS del cliente simple:
echo - No usa SocketIO del lado servidor (evita errores)
echo - Solo Flask + JavaScript puro
echo - Mas compatible para .exe
echo - Mismo funcionamiento completo
echo.
echo Copia este archivo a la computadora del deposito
echo y ejecutalo directamente (no necesita Python)
echo.
pause
