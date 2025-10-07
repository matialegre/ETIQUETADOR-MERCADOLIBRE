@echo off
echo 🏔️ MUNDO OUTDOOR - Instalador Automatico
echo ==========================================
echo.

echo 📋 Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python no encontrado
    echo.
    echo 📥 Por favor instala Python desde: https://python.org
    echo ✅ Asegurate de marcar "Add to PATH" durante la instalacion
    echo.
    pause
    exit /b 1
)

echo ✅ Python encontrado
echo.

echo 📦 Instalando dependencias...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo ❌ Error instalando dependencias
    pause
    exit /b 1
)

echo ✅ Dependencias instaladas correctamente
echo.

echo 🚀 Iniciando sistema...
python simple_launcher.py

pause
