#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para construir AMBOS ejecutables: DEPÓSITO y CABA.
Compila las dos versiones en una sola ejecución.
"""

import os
import sys
import subprocess
from pathlib import Path

def safe_print(text):
    """Imprime texto de forma segura, evitando errores Unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: remover emojis y caracteres especiales
        safe_text = text.encode('ascii', 'ignore').decode('ascii')
        print(safe_text)

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
    
    # Verificar archivos críticos comunes
    common_files = [
        "gui/app_gui_v3.py",
        "gui/app_gui_v3_caba_real.py",
        "services/picker_service.py",
        "utils/db.py",
        "config_override_caba.py"
    ]
    
    # Verificar archivos específicos de cada versión
    deposito_files = ["main.py"]
    caba_files = ["main_caba.py"]
    
    missing_files = []
    
    # Verificar archivos comunes
    for file in common_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    # Verificar archivos específicos
    missing_deposito = []
    for file in deposito_files:
        if not os.path.exists(file):
            missing_deposito.append(file)
    
    missing_caba = []
    for file in caba_files:
        if not os.path.exists(file):
            missing_caba.append(file)
    
    if missing_files:
        safe_print("[ERROR] Archivos comunes no encontrados:")
        for file in missing_files:
            safe_print(f"   - {file}")
        return False
    
    if missing_deposito:
        safe_print("[AVISO] Archivos DEPOSITO no encontrados (se omitira esa version):")
        for file in missing_deposito:
            safe_print(f"   - {file}")
    
    if missing_caba:
        safe_print("[AVISO] Archivos CABA no encontrados (se omitira esa version):")
        for file in missing_caba:
            safe_print(f"   - {file}")
    
    if missing_deposito and missing_caba:
        safe_print("[ERROR] No se pueden compilar ninguna de las dos versiones")
        return False
    
    safe_print("[OK] Archivos criticos verificados")
    safe_print("")
    
    # Variables para tracking de éxito
    deposito_success = False
    caba_success = False
    
    # Compilar versión DEPÓSITO (solo si tiene archivos necesarios)
    if not missing_deposito:
        safe_print("[DEPOSITO] COMPILANDO VERSION DEPOSITO")
        safe_print("=" * 40)
        
        try:
            result = subprocess.run([
                sys.executable, "build_exe_deposito.py"
            ], check=True, capture_output=True, text=True)
            
            safe_print("[OK] Version DEPOSITO compilada exitosamente")
            safe_print("[INFO] Disponible en: DISTRIBUCION_DEPOSITO/")
            deposito_success = True
            
        except subprocess.CalledProcessError as e:
            safe_print(f"[ERROR] Error compilando version DEPOSITO: {e}")
            safe_print(f"[INFO] Salida: {e.stdout}")
            safe_print(f"[INFO] Error: {e.stderr}")
        
        safe_print("")
    else:
        safe_print("[AVISO] OMITIENDO VERSION DEPOSITO (archivos faltantes)")
        safe_print("")
    
    # Compilar versión CABA (solo si tiene archivos necesarios)
    if not missing_caba:
        safe_print("[CABA] COMPILANDO VERSION CABA")
        safe_print("=" * 40)
        
        try:
            result = subprocess.run([
                sys.executable, "build_exe_caba.py"
            ], check=True, capture_output=True, text=True)
            
            safe_print("[OK] Version CABA compilada exitosamente")
            safe_print("[INFO] Disponible en: DISTRIBUCION_CABA/")
            caba_success = True
            
        except subprocess.CalledProcessError as e:
            safe_print(f"[ERROR] Error compilando version CABA: {e}")
            safe_print(f"[INFO] Salida: {e.stdout}")
            safe_print(f"[INFO] Error: {e.stderr}")
        
        safe_print("")
    else:
        safe_print("[AVISO] OMITIENDO VERSION CABA (archivos faltantes)")
        safe_print("")
    
    # Verificar que al menos una versión se compiló exitosamente
    if not deposito_success and not caba_success:
        safe_print("[ERROR] NINGUNA VERSION SE COMPILO EXITOSAMENTE")
        return False
    
    # Resumen final
    safe_print("\n[EXITO] COMPILACION COMPLETA!")
    safe_print("=" * 50)
    
    # Mostrar estado de cada versión
    versions_compiled = []
    if deposito_success:
        versions_compiled.append("DEPÓSITO")
    if caba_success:
        versions_compiled.append("CABA")
    
    if versions_compiled:
        safe_print(f"[OK] VERSIONES COMPILADAS: {', '.join(versions_compiled)}")
    else:
        safe_print("[ERROR] NINGUNA VERSION SE COMPILO")
        return False
    
    safe_print("")
    safe_print("[INFO] ARCHIVOS GENERADOS:")
    
    if deposito_success:
        safe_print("[DEPOSITO] DEPOSITO:")
        safe_print("   [INFO] Carpeta: DISTRIBUCION_DEPOSITO/")
        safe_print("   [INFO] Ejecutar: INICIAR_DEPOSITO.bat")
        safe_print("   [INFO] Config: Base local, filtros DEPO/MUNDOAL/etc")
        safe_print("")
    
    if caba_success:
        safe_print("[CABA] CABA:")
        safe_print("   [INFO] Carpeta: DISTRIBUCION_CABA/")
        safe_print("   [INFO] Ejecutar: INICIAR_CABA.bat")
        safe_print("   [INFO] Config: SQL remoto, filtros CAB/CABA/MUNDOCAB")
        safe_print("")
    
    safe_print("[INFO] INSTRUCCIONES DE USO:")
    safe_print("1. Copie la carpeta correspondiente a cada ubicacion")
    safe_print("2. Ejecute el archivo .bat correspondiente")
    safe_print("3. Cada version tiene su configuracion especifica")
    
    # Verificar tamaños de archivos
    deposito_exe = Path("DISTRIBUCION_DEPOSITO/Cliente_Matias_GUI_v3_DEPOSITO.exe")
    caba_exe = Path("DISTRIBUCION_CABA/Cliente_Matias_GUI_v3_CABA.exe")
    
    sizes_info = []
    total_size = 0
    
    if deposito_success and deposito_exe.exists():
        deposito_size = deposito_exe.stat().st_size / (1024 * 1024)
        sizes_info.append(f"🏭 DEPÓSITO: {deposito_size:.1f} MB")
        total_size += deposito_size
    
    if caba_success and caba_exe.exists():
        caba_size = caba_exe.stat().st_size / (1024 * 1024)
        sizes_info.append(f"🏢 CABA: {caba_size:.1f} MB")
        total_size += caba_size
    
    if sizes_info:
        safe_print(f"\n[INFO] TAMANOS DE ARCHIVOS:")
        for size_info in sizes_info:
            safe_print(size_info)
        if len(sizes_info) > 1:
            safe_print(f"[INFO] Total: {total_size:.1f} MB")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        safe_print(f"\n{'[EXITO] EXITO TOTAL' if success else '[ERROR] FALLO'}")
        input("\nPresione Enter para salir...")
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        safe_print("\n[AVISO] Compilacion cancelada")
        sys.exit(1)
        
    except Exception as e:
        safe_print(f"\n[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
        sys.exit(1)
