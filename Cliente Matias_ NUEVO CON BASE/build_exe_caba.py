#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para generar el ejecutable CABA usando exactamente el mismo comando que el original.
"""

import os
import sys
import subprocess

def safe_print(text):
    """Imprime texto de forma segura, evitando errores Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: remover emojis y caracteres especiales
        safe_text = text.encode('ascii', 'ignore').decode('ascii')
        print(safe_text)

def build_caba_exe():
    """Construye el ejecutable CABA usando PyInstaller."""
    
    safe_print("[CABA] GENERANDO EJECUTABLE CABA")
    safe_print("=" * 40)
    
    # Verificar que estamos en el directorio correcto
    if not os.path.exists('gui/app_gui_v3_caba_real.py'):
        safe_print("[ERROR] Error: No se encuentra gui/app_gui_v3_caba_real.py")
        safe_print("   Ejecute este script desde el directorio del proyecto")
        return False
    
    # Comando PyInstaller idéntico al original pero para CABA
    cmd = [
        'pyinstaller',
        '--onefile',
        '--console',
        '--name', 'Cliente_Matias_GUI_v3_CABA',
        '--add-data', '.env;.',
        '--add-data', 'config_override_caba.py;.',
        '--add-data', 'api;api',
        '--add-data', 'services;services',
        '--add-data', 'models;models',
        '--add-data', 'utils;utils',
        '--add-data', 'printing;printing',
        '--hidden-import', 'ttkbootstrap',
        '--hidden-import', 'requests',
        '--hidden-import', 'python-dotenv',
        '--hidden-import', 'tkinter',
        '--clean',
        'gui/app_gui_v3_caba_real.py'
    ]
    
    print("🔨 Ejecutando PyInstaller...")
    print(f"📝 Comando: {' '.join(cmd[:5])}... (comando completo muy largo)")
    
    try:
        # Ejecutar PyInstaller
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Ejecutable CABA construido exitosamente")
            
            # Verificar que el archivo existe
            exe_path = "dist/Cliente_Matias_GUI_v3_CABA.exe"
            if os.path.exists(exe_path):
                file_size = os.path.getsize(exe_path) / (1024*1024)  # MB
                print(f"📁 Archivo generado: {exe_path} ({file_size:.1f} MB)")
                
                # Crear carpeta de distribución
                create_distribution(exe_path)
                return True
            else:
                print(f"❌ No se encontró el ejecutable esperado: {exe_path}")
                return False
        else:
            print("❌ Error construyendo ejecutable:")
            print("STDOUT:", result.stdout[-1000:] if result.stdout else "Sin salida")
            print("STDERR:", result.stderr[-1000:] if result.stderr else "Sin errores")
            return False
            
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def create_distribution(exe_path):
    """Crea carpeta de distribución para CABA."""
    
    print("\n📦 Creando distribución CABA...")
    
    import shutil
    
    # Crear carpeta
    dist_folder = "DISTRIBUCION_CABA"
    if os.path.exists(dist_folder):
        shutil.rmtree(dist_folder)
    os.makedirs(dist_folder)
    
    # Copiar ejecutable
    shutil.copy2(exe_path, dist_folder)
    print(f"✅ Ejecutable copiado a {dist_folder}")
    
    # Crear README específico para CABA
    readme = """
CLIENTE MATÍAS - VERSIÓN CABA
============================

INSTALACIÓN:
1. Copie Cliente_Matias_GUI_v3_CABA.exe a la PC destino
2. Ejecute el archivo

CONFIGURACIÓN AUTOMÁTICA:
• API Dragonfish: http://190.211.201.217:8009/api.Dragonfish
• SQL Server: DESKTOP-CK25NCF\\ZOOLOGIC
• Base de datos: DRAGONFISH_MUNDOCAB
• Depósito: MUNDOCAB (para movimientos SQL)
• Filtros: CAB, CABA, MUNDOCAB

REQUISITOS EN PC DESTINO:
• Windows 10/11
• Conexión a internet (para API remota)
• Acceso al SQL Server CABA
• Driver ODBC SQL Server

USO:
1. Ejecutar Cliente_Matias_GUI_v3_CABA.exe
2. Usar "Cargar Pedidos" (filtra automáticamente por CABA)
3. Usar "Pickear" normalmente
4. Usar "Más opciones" > "Imprimir Lista" para PDFs

DIFERENCIAS CON VERSIÓN ORIGINAL:
• Conecta al servidor remoto de Bahía Blanca
• Filtra solo pedidos CAB/CABA/MUNDOCAB
• Movimientos SQL usan depósito "MUNDOCAB"
• Resto de funcionalidades idénticas

PROBLEMAS COMUNES:
• Si no conecta API: Verificar internet y firewall
• Si no conecta SQL: Verificar acceso a red CABA
• Si falta driver: Instalar ODBC Driver for SQL Server

Versión: CABA v1.0
Basado en: Cliente Matías GUI v3
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
echo Configuracion CABA:
echo - API: http://190.211.201.217:8009/api.Dragonfish
echo - SQL: DESKTOP-CK25NCF\\ZOOLOGIC / DRAGONFISH_MUNDOCAB
echo - Filtros: CAB, CABA, MUNDOCAB
echo.

if not exist "Cliente_Matias_GUI_v3_CABA.exe" (
    echo ERROR: No se encuentra Cliente_Matias_GUI_v3_CABA.exe
    pause
    exit /b 1
)

echo Iniciando aplicacion CABA...
echo.
start "" "Cliente_Matias_GUI_v3_CABA.exe"

echo Aplicacion iniciada.
echo Si hay problemas, lea README_CABA.txt
timeout /t 3 /nobreak >nul
"""
    
    with open(os.path.join(dist_folder, "INICIAR_CABA.bat"), 'w', encoding='utf-8') as f:
        f.write(launcher)
    
    print(f"✅ Distribución CABA creada en: {dist_folder}")
    print("📁 Archivos incluidos:")
    for item in os.listdir(dist_folder):
        print(f"   - {item}")

def main():
    """Función principal."""
    
    print("CONSTRUCTOR DE EJECUTABLE CABA")
    print("Usa exactamente el mismo comando que la version original")
    print("pero configurado especificamente para CABA")
    print()
    
    # Verificar PyInstaller
    try:
        import PyInstaller
        print("✅ PyInstaller encontrado")
    except ImportError:
        print("❌ PyInstaller no encontrado")
        print("   Instale con: pip install pyinstaller")
        return 1
    
    # Verificar archivos críticos
    critical_files = [
        'gui/app_gui_v3_caba_real.py',
        'config_override_caba.py'
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
    
    print("\n🎉 ¡CONSTRUCCIÓN CABA COMPLETADA!")
    print("=" * 40)
    print("📦 Ejecutable listo en: DISTRIBUCION_CABA/")
    print("🚀 Para usar en CABA:")
    print("   1. Copie la carpeta DISTRIBUCION_CABA completa")
    print("   2. Ejecute INICIAR_CABA.bat")
    print("   3. La aplicación es idéntica pero con config CABA")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        input("\nPresione Enter para salir...")
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nConstruccion cancelada")
        sys.exit(1)
    except Exception as e:
        print(f"\nError inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
        sys.exit(1)
