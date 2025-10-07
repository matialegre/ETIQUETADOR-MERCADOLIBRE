#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para construir el ejecutable de la versión DEPÓSITO (normal).
Usa exactamente el mismo comando que la versión original.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def main():
    print("🏭 CONSTRUCTOR DE EJECUTABLE DEPÓSITO")
    print("Versión normal con configuración de depósito local")
    print()
    
    # Verificar que PyInstaller esté disponible
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
        print("✅ PyInstaller encontrado")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller no encontrado. Instálelo con: pip install pyinstaller")
        return False
    
    # Verificar archivos críticos
    required_files = [
        "main.py",
        "gui/app_gui_v3.py",
        "services/picker_service.py",
        "utils/db.py"
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Archivo crítico no encontrado: {file}")
            return False
    
    print("✅ Archivos críticos verificados")
    
    # Comando de PyInstaller para DEPÓSITO (versión normal)
    print("🏭 GENERANDO EJECUTABLE DEPÓSITO")
    print("=" * 40)
    
    cmd = [
        "pyinstaller",
        "--onefile",
        "--console",
        "--name", "Cliente_Matias_GUI_v3_DEPOSITO",
        "--add-data", "gui;gui",
        "--add-data", "services;services", 
        "--add-data", "utils;utils",
        "--add-data", "assets;assets",
        "--hidden-import", "tkinter",
        "--hidden-import", "ttkbootstrap",
        "--hidden-import", "PIL",
        "--hidden-import", "requests",
        "--hidden-import", "pyodbc",
        "--hidden-import", "webbrowser",
        "--hidden-import", "threading",
        "--hidden-import", "queue",
        "--hidden-import", "datetime",
        "--hidden-import", "json",
        "--hidden-import", "os",
        "--hidden-import", "sys",
        "--hidden-import", "logging",
        "--hidden-import", "traceback",
        "--hidden-import", "time",
        "--hidden-import", "urllib.parse",
        "--hidden-import", "base64",
        "--hidden-import", "hashlib",
        "--hidden-import", "uuid",
        "--hidden-import", "socket",
        "--hidden-import", "ssl",
        "--hidden-import", "http.client",
        "--hidden-import", "email.mime.text",
        "--hidden-import", "email.mime.multipart",
        "--hidden-import", "smtplib",
        "--hidden-import", "concurrent.futures",
        "--hidden-import", "functools",
        "--hidden-import", "itertools",
        "--hidden-import", "collections",
        "--hidden-import", "dataclasses",
        "--hidden-import", "typing",
        "--hidden-import", "pathlib",
        "--hidden-import", "tempfile",
        "--hidden-import", "shutil",
        "--hidden-import", "subprocess",
        "--hidden-import", "platform",
        "--hidden-import", "getpass",
        "--hidden-import", "locale",
        "--hidden-import", "calendar",
        "--hidden-import", "random",
        "--hidden-import", "string",
        "--hidden-import", "re",
        "--hidden-import", "math",
        "--hidden-import", "statistics",
        "--hidden-import", "decimal",
        "--hidden-import", "fractions",
        "--hidden-import", "operator",
        "--hidden-import", "copy",
        "--hidden-import", "pickle",
        "--hidden-import", "csv",
        "--hidden-import", "xml.etree.ElementTree",
        "--hidden-import", "html.parser",
        "--hidden-import", "urllib.request",
        "--hidden-import", "urllib.error",
        "--hidden-import", "http.server",
        "--hidden-import", "socketserver",
        "--hidden-import", "select",
        "--hidden-import", "signal",
        "--hidden-import", "atexit",
        "--hidden-import", "weakref",
        "--hidden-import", "gc",
        "--hidden-import", "ctypes",
        "--hidden-import", "struct",
        "--hidden-import", "array",
        "--hidden-import", "mmap",
        "--hidden-import", "io",
        "--hidden-import", "codecs",
        "--hidden-import", "encodings",
        "--hidden-import", "unicodedata",
        "--hidden-import", "locale",
        "--hidden-import", "gettext",
        "--hidden-import", "argparse",
        "--hidden-import", "configparser",
        "--hidden-import", "logging.handlers",
        "--hidden-import", "logging.config",
        "--hidden-import", "warnings",
        "--hidden-import", "contextlib",
        "--hidden-import", "abc",
        "--hidden-import", "enum",
        "--hidden-import", "types",
        "--hidden-import", "inspect",
        "--hidden-import", "dis",
        "--hidden-import", "ast",
        "--hidden-import", "keyword",
        "--hidden-import", "token",
        "--hidden-import", "tokenize",
        "--hidden-import", "py_compile",
        "--hidden-import", "compileall",
        "--hidden-import", "zipfile",
        "--hidden-import", "tarfile",
        "--hidden-import", "gzip",
        "--hidden-import", "bz2",
        "--hidden-import", "lzma",
        "--hidden-import", "zlib",
        "--hidden-import", "hashlib",
        "--hidden-import", "hmac",
        "--hidden-import", "secrets",
        "--hidden-import", "ssl",
        "--hidden-import", "socket",
        "--hidden-import", "ipaddress",
        "--hidden-import", "email",
        "--hidden-import", "email.message",
        "--hidden-import", "email.parser",
        "--hidden-import", "email.generator",
        "--hidden-import", "email.policy",
        "--hidden-import", "email.contentmanager",
        "--hidden-import", "email.headerregistry",
        "--hidden-import", "email.utils",
        "--hidden-import", "email.errors",
        "--hidden-import", "mailbox",
        "--hidden-import", "mimetypes",
        "--hidden-import", "base64",
        "--hidden-import", "binhex",
        "--hidden-import", "binascii",
        "--hidden-import", "quopri",
        "--hidden-import", "uu",
        "main.py"
    ]
    
    print("🔨 Ejecutando PyInstaller...")
    print(f"📝 Comando: pyinstaller --onefile --console --name Cliente_Matias_GUI_v3_DEPOSITO... (comando completo muy largo)")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Ejecutable DEPÓSITO construido exitosamente")
        
        # Verificar que el archivo se creó
        exe_path = Path("dist/Cliente_Matias_GUI_v3_DEPOSITO.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📁 Archivo generado: {exe_path} ({size_mb:.1f} MB)")
        else:
            print("❌ El archivo ejecutable no se encontró después de la compilación")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error durante la compilación: {e}")
        print(f"📝 Salida de error: {e.stderr}")
        return False
    
    # Crear distribución DEPÓSITO
    print("\n📦 Creando distribución DEPÓSITO...")
    
    dist_dir = Path("DISTRIBUCION_DEPOSITO")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()
    
    # Copiar ejecutable
    exe_source = Path("dist/Cliente_Matias_GUI_v3_DEPOSITO.exe")
    exe_dest = dist_dir / "Cliente_Matias_GUI_v3_DEPOSITO.exe"
    shutil.copy2(exe_source, exe_dest)
    print("✅ Ejecutable copiado a DISTRIBUCION_DEPOSITO")
    
    # Crear archivo .bat para DEPÓSITO
    bat_content = '''@echo off
title Cliente Matias - GUI v3 DEPOSITO
echo.
echo ==========================================
echo    CLIENTE MATIAS - GUI v3 DEPOSITO
echo ==========================================
echo.
echo 🏭 Iniciando version DEPOSITO (local)...
echo.
Cliente_Matias_GUI_v3_DEPOSITO.exe
pause
'''
    
    bat_path = dist_dir / "INICIAR_DEPOSITO.bat"
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    
    # Crear README para DEPÓSITO
    readme_content = '''# CLIENTE MATIAS - GUI v3 DEPÓSITO

## 📋 DESCRIPCIÓN
Esta es la versión DEPÓSITO del sistema de picking de Cliente Matías.
Configurada para usar la base de datos y API local del depósito.

## 🚀 INSTALACIÓN Y USO

### Opción 1: Usar el archivo .bat (RECOMENDADO)
1. Haga doble clic en `INICIAR_DEPOSITO.bat`
2. El programa se iniciará automáticamente

### Opción 2: Ejecutar directamente
1. Haga doble clic en `Cliente_Matias_GUI_v3_DEPOSITO.exe`

## ⚙️ CONFIGURACIÓN DEPÓSITO

- 📡 **API Dragonfish**: Local (configuración por defecto)
- 🗄️ **Base de datos SQL**: DRAGONFISH_DEPOSITO (local)
- 🏷️ **Filtros de nota**: DEPO, MUNDOAL, MTGBBL, BBPS, MONBAHIA, MTGBBPS
- 🏦 **Depósito**: DEPOSITO

## 📁 ARCHIVOS INCLUIDOS

- `Cliente_Matias_GUI_v3_DEPOSITO.exe` - Ejecutable principal
- `INICIAR_DEPOSITO.bat` - Launcher con interfaz amigable
- `README_DEPOSITO.txt` - Este archivo de ayuda

## 🔧 SOLUCIÓN DE PROBLEMAS

Si el programa no inicia:
1. Verifique que tenga permisos de administrador
2. Verifique la conexión a la base de datos SQL local
3. Verifique la conexión a la API Dragonfish local

## 📞 SOPORTE
Para soporte técnico, contacte al administrador del sistema.

---
Versión: GUI v3 DEPÓSITO
Fecha: ''' + str(Path().cwd().stat().st_mtime) + '''
'''
    
    readme_path = dist_dir / "README_DEPOSITO.txt"
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("✅ Distribución DEPÓSITO creada en: DISTRIBUCION_DEPOSITO")
    print("📁 Archivos incluidos:")
    print("   - Cliente_Matias_GUI_v3_DEPOSITO.exe")
    print("   - INICIAR_DEPOSITO.bat")
    print("   - README_DEPOSITO.txt")
    
    print("\n🎉 ¡CONSTRUCCIÓN DEPÓSITO COMPLETADA!")
    print("=" * 40)
    print("📦 Ejecutable listo en: DISTRIBUCION_DEPOSITO/")
    print("🚀 Para usar en DEPÓSITO:")
    print("   1. Copie la carpeta DISTRIBUCION_DEPOSITO completa")
    print("   2. Ejecute INICIAR_DEPOSITO.bat")
    print("   3. La aplicación usa configuración local de depósito")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        print(f"\n{'✅ ÉXITO' if success else '❌ FALLO'}")
        input("\nPresione Enter para salir...")
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️ Construcción cancelada")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
        sys.exit(1)
