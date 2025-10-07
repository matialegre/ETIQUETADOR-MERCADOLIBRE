#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script simplificado para generar el ejecutable CABA.
"""

import os
import sys
import subprocess
import shutil

def build_caba_exe():
    """Construye el ejecutable CABA usando PyInstaller con comando directo."""
    
    print("🏢 GENERADOR SIMPLIFICADO DE EJECUTABLE CABA")
    print("=" * 50)
    
    # Verificar PyInstaller
    try:
        import PyInstaller
        print("✅ PyInstaller encontrado")
    except ImportError:
        print("❌ PyInstaller no encontrado")
        print("   Instale con: pip install pyinstaller")
        return False
    
    # Comando PyInstaller simplificado
    cmd = [
        'pyinstaller',
        '--onefile',                    # Un solo archivo ejecutable
        '--windowed',                   # Sin ventana de consola (cambiar a --console para debug)
        '--name=ClienteMatias_CABA',    # Nombre del ejecutable
        '--add-data=config_caba.py;.',  # Incluir configuración
        '--add-data=api;api',           # Incluir toda la carpeta api
        '--add-data=utils;utils',       # Incluir toda la carpeta utils
        '--add-data=models;models',     # Incluir toda la carpeta models
        '--add-data=gui;gui',           # Incluir toda la carpeta gui
        '--add-data=services;services', # Incluir toda la carpeta services
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.messagebox',
        '--hidden-import=ttkbootstrap',
        '--hidden-import=requests',
        '--hidden-import=pyodbc',
        '--hidden-import=reportlab.lib.pagesizes',
        '--hidden-import=reportlab.platypus',
        '--hidden-import=config_caba',
        '--hidden-import=gui.state',
        '--hidden-import=gui.order_refresher',
        '--hidden-import=api.dragonfish_api_caba',
        '--hidden-import=utils.db_caba',
        '--hidden-import=services.picker_service_caba',
        '--hidden-import=services.print_service_caba',
        'main_caba.py'                  # Archivo principal
    ]
    
    print("🔨 Iniciando construcción...")
    print(f"📝 Comando: {' '.join(cmd[:5])}... (comando completo muy largo)")
    
    try:
        # Ejecutar PyInstaller
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Ejecutable construido exitosamente")
            
            # Verificar que el archivo existe
            exe_path = "dist/ClienteMatias_CABA.exe"
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path) / (1024*1024)  # MB
                print(f"📁 Archivo generado: {exe_path} ({file_size:.1f} MB)")
                return True
            else:
                print(f"❌ No se encontró el ejecutable esperado: {exe_path}")
                return False
        else:
            print("❌ Error construyendo ejecutable:")
            print("STDOUT:", result.stdout[-1000:])  # Últimas 1000 chars
            print("STDERR:", result.stderr[-1000:])  # Últimas 1000 chars
            return False
            
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def create_distribution():
    """Crea carpeta de distribución."""
    
    print("\n📦 Creando distribución...")
    
    # Crear carpeta
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
        print(f"❌ No se encontró: {exe_source}")
        return False
    
    # Crear README
    readme = f"""
CLIENTE MATÍAS - VERSIÓN CABA
============================

INSTALACIÓN:
1. Copie ClienteMatias_CABA.exe a la PC destino
2. Ejecute el archivo

CONFIGURACIÓN:
• API: http://190.211.201.217:8009/api.Dragonfish
• SQL: DESKTOP-CK25NCF\\ZOOLOGIC / DRAGONFISH_MUNDOCAB
• Filtros: CAB, CABA, MUNDOCAB

REQUISITOS:
• Windows 10/11
• Conexión a internet
• Acceso al SQL Server
• Driver ODBC SQL Server

USO:
1. Ejecutar ClienteMatias_CABA.exe
2. "Test Conexiones" para verificar
3. "Cargar Pedidos CABA" para cargar
4. "Imprimir PDF CABA" para imprimir

PROBLEMAS COMUNES:
• Si no inicia: Instalar Visual C++ Redistributable
• Si falla SQL: Verificar driver ODBC
• Si falla API: Verificar conectividad de red

Versión: CABA v1.0
"""
    
    with open(os.path.join(dist_folder, "README_CABA.txt"), 'w', encoding='utf-8') as f:
        f.write(readme)
    
    # Crear launcher batch
    launcher = """@echo off
title Cliente Matias CABA
echo ========================================
echo CLIENTE MATIAS - VERSION CABA
echo ========================================
echo.
echo Iniciando aplicacion...
echo.

if not exist "ClienteMatias_CABA.exe" (
    echo ERROR: No se encuentra ClienteMatias_CABA.exe
    echo Verifique que este archivo este en la misma carpeta.
    pause
    exit /b 1
)

echo Ejecutando ClienteMatias_CABA.exe...
start "" "ClienteMatias_CABA.exe"

echo.
echo Aplicacion iniciada.
echo Si hay problemas, lea README_CABA.txt
echo.
timeout /t 3 /nobreak >nul
"""
    
    with open(os.path.join(dist_folder, "INICIAR_CABA.bat"), 'w', encoding='utf-8') as f:
        f.write(launcher)
    
    print(f"✅ Distribución creada en: {dist_folder}")
    print("📁 Archivos incluidos:")
    for item in os.listdir(dist_folder):
        print(f"   - {item}")
    
    return True

def cleanup_build():
    """Limpia archivos de construcción."""
    
    cleanup_choice = input("\n¿Limpiar archivos temporales de construcción? (s/N): ").lower()
    if cleanup_choice in ['s', 'si', 'sí', 'y', 'yes']:
        print("🧹 Limpiando...")
        
        for folder in ['build', 'dist', '__pycache__']:
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                    print(f"   Eliminado: {folder}")
                except Exception as e:
                    print(f"   Error eliminando {folder}: {e}")
        
        # Limpiar archivos .spec
        for file in os.listdir('.'):
            if file.endswith('.spec'):
                try:
                    os.remove(file)
                    print(f"   Eliminado: {file}")
                except Exception as e:
                    print(f"   Error eliminando {file}: {e}")
        
        print("✅ Limpieza completada")

def main():
    """Función principal."""
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists('main_caba.py'):
        print("❌ Error: No se encuentra main_caba.py")
        print("   Ejecute este script desde el directorio del proyecto")
        return 1
    
    # Verificar archivos críticos
    critical_files = [
        'config_caba.py',
        'gui/app_gui_v3_caba.py',
        'api/dragonfish_api_caba.py',
        'utils/db_caba.py',
        'services/picker_service_caba.py',
        'services/print_service_caba.py'
    ]
    
    missing_files = [f for f in critical_files if not os.path.exists(f)]
    if missing_files:
        print("❌ Archivos críticos faltantes:")
        for f in missing_files:
            print(f"   - {f}")
        return 1
    
    print("✅ Archivos críticos verificados")
    
    # Construir ejecutable
    if not build_caba_exe():
        print("❌ Fallo en la construcción del ejecutable")
        return 1
    
    # Crear distribución
    if not create_distribution():
        print("❌ Fallo creando distribución")
        return 1
    
    # Limpieza opcional
    cleanup_build()
    
    print("\n🎉 ¡CONSTRUCCIÓN COMPLETADA!")
    print("=" * 40)
    print("📦 Ejecutable listo en: DISTRIBUCION_CABA/")
    print("🚀 Para instalar en CABA:")
    print("   1. Copie la carpeta DISTRIBUCION_CABA completa")
    print("   2. Ejecute INICIAR_CABA.bat o ClienteMatias_CABA.exe")
    print("   3. Lea README_CABA.txt para más información")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        input("\nPresione Enter para salir...")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️ Construcción cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
        sys.exit(1)
