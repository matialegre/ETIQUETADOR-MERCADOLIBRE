#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para generar .exe del cliente de chat
"""

import os
import sys
import subprocess

def build_client_exe():
    """Generar ejecutable del cliente de chat"""
    
    print("🚀 Generando ejecutable del Cliente de Chat...")
    print("=" * 50)
    
    # Verificar que PyInstaller esté instalado
    try:
        import PyInstaller
        print("✅ PyInstaller encontrado")
    except ImportError:
        print("❌ PyInstaller no encontrado. Instalando...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller instalado")
    
    # Comando PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",                    # Un solo archivo
        "--windowed",                   # Sin consola
        "--name", "ChatCliente_MundoOutdoor",  # Nombre del exe
        "--add-data", "templates;templates",   # Incluir templates
        "--hidden-import", "flask",
        "--hidden-import", "flask_socketio",
        "--hidden-import", "python_socketio",
        "--hidden-import", "python_engineio",
        "--hidden-import", "werkzeug",
        "--hidden-import", "threading",
        "--clean",                      # Limpiar cache
        "chat_cliente.py"
    ]
    
    print("📦 Ejecutando PyInstaller...")
    print(f"Comando: {' '.join(cmd)}")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Compilación exitosa!")
        print()
        print("📁 Archivo generado:")
        print("   dist/ChatCliente_MundoOutdoor.exe")
        print()
        print("📋 Instrucciones:")
        print("1. Copia el archivo .exe a la computadora del depósito")
        print("2. Ejecuta el .exe (no necesita Python instalado)")
        print("3. Se abrirá el navegador automáticamente")
        print("4. Ingresa la IP del servidor (tu computadora)")
        print("5. Ingresa tu nombre y ubicación")
        print("6. ¡Listo para chatear y enviar archivos!")
        
    except subprocess.CalledProcessError as e:
        print("❌ Error en la compilación:")
        print(e.stdout)
        print(e.stderr)
        return False
    
    return True

if __name__ == "__main__":
    success = build_client_exe()
    if success:
        print("\n🎉 ¡Cliente compilado exitosamente!")
    else:
        print("\n💥 Error al compilar el cliente")
    
    input("\nPresiona Enter para continuar...")
