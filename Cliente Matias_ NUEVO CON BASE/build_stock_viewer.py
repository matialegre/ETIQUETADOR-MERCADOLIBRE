#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para compilar el Visor de Movimientos de Stock como ejecutable
"""

import subprocess
import sys
import os
from pathlib import Path

def safe_print(text):
    """Imprime texto de forma segura evitando errores Unicode"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Reemplazar caracteres problemáticos con equivalentes ASCII
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)

def build_stock_viewer():
    """Compila el visor de movimientos como ejecutable"""
    safe_print("=" * 60)
    safe_print("COMPILANDO VISOR DE MOVIMIENTOS DE STOCK")
    safe_print("=" * 60)
    
    # Verificar que el archivo fuente existe
    source_file = "stock_movements_viewer.py"
    if not os.path.exists(source_file):
        safe_print(f"ERROR: No se encuentra el archivo {source_file}")
        return False
    
    # Comando PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",  # Sin consola para interfaz más limpia
        "--name", "Visor_Movimientos_Stock",
        "--clean",
        source_file
    ]
    
    safe_print("Ejecutando comando:")
    safe_print(" ".join(cmd))
    safe_print("")
    
    try:
        # Ejecutar PyInstaller
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            safe_print("COMPILACION EXITOSA!")
            safe_print("")
            safe_print("Archivo generado:")
            exe_path = Path("dist") / "Visor_Movimientos_Stock.exe"
            if exe_path.exists():
                safe_print(f"  {exe_path.absolute()}")
                safe_print(f"  Tamaño: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
            else:
                safe_print("  ADVERTENCIA: No se encontro el archivo .exe generado")
            
            safe_print("")
            safe_print("INSTRUCCIONES:")
            safe_print("1. El ejecutable esta en la carpeta 'dist'")
            safe_print("2. Puedes copiarlo a cualquier PC sin Python")
            safe_print("3. Solo ejecuta 'Visor_Movimientos_Stock.exe'")
            
        else:
            safe_print("ERROR EN LA COMPILACION:")
            safe_print(result.stderr)
            return False
            
    except FileNotFoundError:
        safe_print("ERROR: PyInstaller no esta instalado")
        safe_print("Instala con: pip install pyinstaller")
        return False
    except Exception as e:
        safe_print(f"ERROR INESPERADO: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = build_stock_viewer()
    
    if success:
        safe_print("")
        safe_print("PROCESO COMPLETADO EXITOSAMENTE")
    else:
        safe_print("")
        safe_print("PROCESO FALLIDO - Revisa los errores arriba")
    
    input("\nPresiona Enter para salir...")
