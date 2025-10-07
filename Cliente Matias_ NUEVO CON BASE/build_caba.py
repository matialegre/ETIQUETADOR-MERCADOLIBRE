#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para generar el ejecutable (.exe) de la versión CABA.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def create_caba_spec():
    """Crea el archivo .spec para PyInstaller específico para CABA."""
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main_caba.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config_caba.py', '.'),
        ('api/*', 'api'),
        ('utils/*', 'utils'),
        ('models/*', 'models'),
        ('gui/*', 'gui'),
        ('services/*', 'services'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'ttkbootstrap',
        'ttkbootstrap.constants',
        'requests',
        'pyodbc',
        'reportlab.lib.pagesizes',
        'reportlab.platypus',
        'reportlab.lib.styles',
        'reportlab.lib.colors',
        'reportlab.lib.units',
        'datetime',
        'threading',
        'time',
        'os',
        'sys',
        'pathlib',
        'json',
        'logging',
        'subprocess',
        'config_caba',
        'api.ml_api',
        'api.dragonfish_api',
        'api.dragonfish_api_caba',
        'utils.logger',
        'utils.config',
        'utils.db',
        'utils.db_caba',
        'utils.daily_stats',
        'utils.daily_cache',
        'utils.sku_resolver',
        'models.order',
        'models.item',
        'gui.state',
        'gui.order_refresher',
        'gui.order_widgets',
        'gui.app_gui_v3_caba',
        'services.picker_service',
        'services.picker_service_caba',
        'services.print_service',
        'services.print_service_caba',
        'services.parallel_picker',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ClienteMatias_CABA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Con ventana de consola para debug
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon_caba.ico' if os.path.exists('icon_caba.ico') else None,
)
'''
    
    with open('ClienteMatias_CABA.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ Archivo .spec creado: ClienteMatias_CABA.spec")

def check_dependencies():
    """Verifica que PyInstaller esté instalado."""
    try:
        import PyInstaller
        print("✅ PyInstaller encontrado")
        return True
    except ImportError:
        print("❌ PyInstaller no encontrado")
        print("   Instale con: pip install pyinstaller")
        return False

def build_exe():
    """Construye el ejecutable usando PyInstaller."""
    try:
        print("🔨 Iniciando construcción del ejecutable CABA...")
        
        # Comando PyInstaller
        cmd = [
            'pyinstaller',
            '--clean',
            '--noconfirm',
            'ClienteMatias_CABA.spec'
        ]
        
        print(f"📝 Ejecutando: {' '.join(cmd)}")
        
        # Ejecutar PyInstaller
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Ejecutable construido exitosamente")
            return True
        else:
            print("❌ Error construyendo ejecutable:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def create_distribution_folder():
    """Crea carpeta de distribución con todos los archivos necesarios."""
    try:
        print("📦 Creando carpeta de distribución...")
        
        # Crear carpeta de distribución
        dist_folder = "DISTRIBUCION_CABA"
        if os.path.exists(dist_folder):
            shutil.rmtree(dist_folder)
        os.makedirs(dist_folder)
        
        # Copiar ejecutable
        exe_source = "dist/ClienteMatias_CABA.exe"
        if os.path.exists(exe_source):
            shutil.copy2(exe_source, dist_folder)
            print(f"✅ Ejecutable copiado a {dist_folder}")
        else:
            print(f"❌ No se encontró el ejecutable: {exe_source}")
            return False
        
        # Crear archivo README para CABA
        readme_content = """
CLIENTE MATÍAS - VERSIÓN CABA
============================

INSTALACIÓN:
1. Copie toda esta carpeta a la PC de destino
2. Ejecute ClienteMatias_CABA.exe

CONFIGURACIÓN INCLUIDA:
• API Dragonfish: http://190.211.201.217:8009/api.Dragonfish
• SQL Server: DESKTOP-CK25NCF\\ZOOLOGIC
• Base de datos: DRAGONFISH_MUNDOCAB
• Filtros: CAB, CABA, MUNDOCAB

REQUISITOS EN LA PC DESTINO:
• Windows 10/11
• Conexión a internet (para API remota)
• Acceso a la red donde está el SQL Server
• Driver ODBC para SQL Server (normalmente ya instalado)

PRIMER USO:
1. Ejecute el programa
2. Use "Test Conexiones" para verificar conectividad
3. Cargue pedidos con "Cargar Pedidos CABA"
4. Use "Imprimir PDF CABA" para generar listas

SOPORTE:
Para problemas, contacte al administrador del sistema.

Versión: CABA v1.0
Generado: """ + str(subprocess.check_output(['date', '/t'], shell=True, text=True).strip()) + """
"""
        
        with open(os.path.join(dist_folder, "README_CABA.txt"), 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        # Crear script de instalación simple
        install_script = """@echo off
echo ========================================
echo CLIENTE MATIAS - VERSION CABA
echo ========================================
echo.
echo Verificando sistema...

REM Verificar que el ejecutable existe
if not exist "ClienteMatias_CABA.exe" (
    echo ERROR: No se encuentra ClienteMatias_CABA.exe
    pause
    exit /b 1
)

echo ✅ Ejecutable encontrado
echo.
echo Iniciando aplicacion CABA...
echo.

REM Ejecutar la aplicación
start "" "ClienteMatias_CABA.exe"

echo ✅ Aplicacion iniciada
echo.
echo Si hay problemas de conexion, verifique:
echo - Conexion a internet
echo - Acceso al servidor SQL
echo - Configuracion de firewall
echo.
pause
"""
        
        with open(os.path.join(dist_folder, "INICIAR_CABA.bat"), 'w', encoding='utf-8') as f:
            f.write(install_script)
        
        print(f"✅ Carpeta de distribución creada: {dist_folder}")
        print(f"📁 Contenido:")
        for item in os.listdir(dist_folder):
            print(f"   - {item}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creando distribución: {e}")
        return False

def cleanup():
    """Limpia archivos temporales."""
    try:
        print("🧹 Limpiando archivos temporales...")
        
        # Eliminar carpetas de build
        for folder in ['build', 'dist', '__pycache__']:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                print(f"   Eliminado: {folder}")
        
        # Eliminar archivo .spec
        if os.path.exists('ClienteMatias_CABA.spec'):
            os.remove('ClienteMatias_CABA.spec')
            print("   Eliminado: ClienteMatias_CABA.spec")
        
        print("✅ Limpieza completada")
        
    except Exception as e:
        print(f"⚠️ Error en limpieza: {e}")

def main():
    """Función principal del script de construcción."""
    print("🏢 GENERADOR DE EJECUTABLE CABA")
    print("=" * 40)
    
    # Verificar dependencias
    if not check_dependencies():
        return 1
    
    # Crear archivo .spec
    create_caba_spec()
    
    # Construir ejecutable
    if not build_exe():
        print("❌ Fallo en la construcción")
        return 1
    
    # Crear distribución
    if not create_distribution_folder():
        print("❌ Fallo creando distribución")
        return 1
    
    # Limpieza opcional
    cleanup_choice = input("\n¿Limpiar archivos temporales? (s/N): ").lower()
    if cleanup_choice in ['s', 'si', 'sí', 'y', 'yes']:
        cleanup()
    
    print("\n🎉 ¡CONSTRUCCIÓN COMPLETADA!")
    print("=" * 40)
    print("📦 El ejecutable CABA está listo en la carpeta DISTRIBUCION_CABA")
    print("📋 Lea el archivo README_CABA.txt para instrucciones de instalación")
    print("🚀 Use INICIAR_CABA.bat para ejecutar en la PC destino")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    input("\nPresione Enter para salir...")
    sys.exit(exit_code)
