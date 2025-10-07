#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script robusto para construir AMBOS ejecutables: DEPOSITO y CABA.
Sin emojis para evitar errores Unicode en consolas Windows.
"""

import os
import sys
import subprocess
from pathlib import Path

def safe_print(message):
    """Print seguro que evita errores Unicode."""
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback a ASCII si hay problemas Unicode
        print(message.encode('ascii', 'ignore').decode('ascii'))

def main():
    safe_print("CONSTRUCTOR DE EJECUTABLES - DEPOSITO Y CABA")
    safe_print("Compila ambas versiones en una sola ejecucion")
    safe_print("=" * 60)
    
    # Verificar que PyInstaller esté disponible
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
        safe_print("[OK] PyInstaller encontrado")
    except (subprocess.CalledProcessError, FileNotFoundError):
        safe_print("[ERROR] PyInstaller no encontrado. Instalelo con: pip install pyinstaller")
        return False
    
    # Verificar archivos críticos
    required_files = [
        "gui/app_gui_v3.py",
        "gui/app_gui_v3_caba_real.py", 
        "services/picker_service.py",
        "utils/db.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        safe_print("[ERROR] Archivos criticos no encontrados:")
        for file in missing_files:
            safe_print(f"   - {file}")
        return False
    
    safe_print("[OK] Archivos criticos verificados")
    safe_print("")
    
    # Variables para tracking de éxito
    deposito_success = False
    caba_success = False
    
    # Compilar versión DEPOSITO (si existe main.py)
    if os.path.exists("main.py"):
        safe_print("COMPILANDO VERSION DEPOSITO")
        safe_print("=" * 40)
        
        try:
            # Comando PyInstaller para DEPOSITO
            cmd = [
                "pyinstaller",
                "--onefile",
                "--windowed",
                "--name=Cliente_Matias_GUI_v3_DEPOSITO",
                "--add-data=gui;gui",
                "--add-data=services;services", 
                "--add-data=utils;utils",
                "--add-data=config.py;.",
                "--hidden-import=tkinter",
                "--hidden-import=ttkbootstrap",
                "--hidden-import=pyodbc",
                "--hidden-import=requests",
                "--hidden-import=PIL",
                "--hidden-import=reportlab",
                "main.py"
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            safe_print("[OK] Version DEPOSITO compilada exitosamente")
            deposito_success = True
            
        except subprocess.CalledProcessError as e:
            safe_print(f"[ERROR] Error compilando version DEPOSITO: {e}")
            if e.stdout:
                safe_print(f"Salida: {e.stdout}")
            if e.stderr:
                safe_print(f"Error: {e.stderr}")
    else:
        safe_print("[AVISO] main.py no encontrado, omitiendo version DEPOSITO")
    
    safe_print("")
    
    # Compilar versión CABA (si existe main_caba.py)
    if os.path.exists("main_caba.py"):
        safe_print("COMPILANDO VERSION CABA")
        safe_print("=" * 40)
        
        try:
            # Comando PyInstaller para CABA
            cmd = [
                "pyinstaller",
                "--onefile", 
                "--windowed",
                "--name=Cliente_Matias_GUI_v3_CABA",
                "--add-data=gui;gui",
                "--add-data=services;services",
                "--add-data=utils;utils", 
                "--add-data=config_caba.py;.",
                "--add-data=config_override_caba.py;.",
                "--hidden-import=tkinter",
                "--hidden-import=ttkbootstrap",
                "--hidden-import=pyodbc",
                "--hidden-import=requests",
                "--hidden-import=PIL",
                "--hidden-import=reportlab",
                "main_caba.py"
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            safe_print("[OK] Version CABA compilada exitosamente")
            caba_success = True
            
        except subprocess.CalledProcessError as e:
            safe_print(f"[ERROR] Error compilando version CABA: {e}")
            if e.stdout:
                safe_print(f"Salida: {e.stdout}")
            if e.stderr:
                safe_print(f"Error: {e.stderr}")
    else:
        safe_print("[AVISO] main_caba.py no encontrado, omitiendo version CABA")
    
    safe_print("")
    safe_print("RESUMEN DE COMPILACION")
    safe_print("=" * 30)
    
    if deposito_success:
        safe_print("[OK] DEPOSITO: Cliente_Matias_GUI_v3_DEPOSITO.exe")
    else:
        safe_print("[FALLO] DEPOSITO: No compilado")
        
    if caba_success:
        safe_print("[OK] CABA: Cliente_Matias_GUI_v3_CABA.exe")
    else:
        safe_print("[FALLO] CABA: No compilado")
    
    # Crear carpetas de distribución si hay éxito
    if deposito_success or caba_success:
        safe_print("")
        safe_print("Creando carpetas de distribucion...")
        
        # Crear carpeta DISTRIBUCION_DEPOSITO
        if deposito_success:
            os.makedirs("DISTRIBUCION_DEPOSITO", exist_ok=True)
            if os.path.exists("dist/Cliente_Matias_GUI_v3_DEPOSITO.exe"):
                import shutil
                shutil.copy2("dist/Cliente_Matias_GUI_v3_DEPOSITO.exe", "DISTRIBUCION_DEPOSITO/")
                safe_print("[OK] Ejecutable DEPOSITO copiado a DISTRIBUCION_DEPOSITO/")
        
        # Crear carpeta DISTRIBUCION_CABA  
        if caba_success:
            os.makedirs("DISTRIBUCION_CABA", exist_ok=True)
            if os.path.exists("dist/Cliente_Matias_GUI_v3_CABA.exe"):
                import shutil
                shutil.copy2("dist/Cliente_Matias_GUI_v3_CABA.exe", "DISTRIBUCION_CABA/")
                safe_print("[OK] Ejecutable CABA copiado a DISTRIBUCION_CABA/")
    
    return deposito_success or caba_success

if __name__ == "__main__":
    try:
        success = main()
        safe_print("")
        if success:
            safe_print("COMPILACION COMPLETADA CON EXITO")
        else:
            safe_print("COMPILACION FALLIDA")
        
        input("\nPresione Enter para salir...")
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        safe_print("\nCompilacion cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        safe_print(f"\nError inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
        sys.exit(1)
