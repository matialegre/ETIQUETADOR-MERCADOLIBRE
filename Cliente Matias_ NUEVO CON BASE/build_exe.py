#!/usr/bin/env python3
"""
🏗️ SCRIPT PARA CREAR EXE COMPLETO
Empaqueta todo el sistema en un .exe distribuible
"""

import subprocess
import sys
import os
from pathlib import Path
import shutil

def build_complete_exe():
    """Crear .exe completo con todo incluido."""
    
    print("🏗️ Construyendo .exe completo del sistema...")
    
    # Verificar que PyInstaller esté instalado
    try:
        import PyInstaller
        print("✅ PyInstaller encontrado")
    except ImportError:
        print("❌ PyInstaller no encontrado. Instalando...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Directorio base
    base_dir = Path(__file__).parent
    
    # Buscar imagen de fondo
    background_files = []
    for ext in ['.png', '.jpg', '.jpeg', '.bmp']:
        bg_file = base_dir / f"background{ext}"
        if bg_file.exists():
            background_files.append(f"background{ext};.")
            print(f"✅ Imagen de fondo encontrada: {bg_file.name}")
    
    # Comando PyInstaller
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name=MundoOutdoor_StockPicking",
        "--icon=icon.ico" if (base_dir / "icon.ico").exists() else "",
    ]
    
    # Agregar imagen de fondo si existe
    for bg in background_files:
        cmd.extend(["--add-data", bg])
    
    # Agregar carpetas importantes
    important_dirs = ["gui", "services", "utils", "config"]
    for dir_name in important_dirs:
        dir_path = base_dir / dir_name
        if dir_path.exists():
            cmd.extend(["--add-data", f"{dir_name};{dir_name}"])
            print(f"✅ Incluyendo carpeta: {dir_name}")
    
    # Agregar archivos de configuración
    config_files = ["requirements.txt", "config.json", "*.db"]
    for pattern in config_files:
        for file_path in base_dir.glob(pattern):
            if file_path.is_file():
                cmd.extend(["--add-data", f"{file_path.name};."])
                print(f"✅ Incluyendo archivo: {file_path.name}")
    
    # Archivo principal
    cmd.append("simple_launcher.py")
    
    # Filtrar comandos vacíos
    cmd = [c for c in cmd if c]
    
    print(f"\n🚀 Ejecutando comando:")
    print(" ".join(cmd))
    print()
    
    try:
        # Ejecutar PyInstaller
        result = subprocess.run(cmd, cwd=base_dir, check=True)
        
        if result.returncode == 0:
            exe_path = base_dir / "dist" / "MundoOutdoor_StockPicking.exe"
            print(f"\n🎉 ¡.exe creado exitosamente!")
            print(f"📁 Ubicación: {exe_path}")
            print(f"📏 Tamaño: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")
            
            # Crear carpeta de distribución
            dist_folder = base_dir / "DISTRIBUCION"
            if dist_folder.exists():
                shutil.rmtree(dist_folder)
            dist_folder.mkdir()
            
            # Copiar .exe
            shutil.copy2(exe_path, dist_folder / "MundoOutdoor_StockPicking.exe")
            
            # Crear README
            readme_content = """
🏔️ MUNDO OUTDOOR - Sistema de Stock Picking
==========================================

📋 INSTRUCCIONES DE INSTALACIÓN:

1. Copiar toda esta carpeta a la PC destino
2. Ejecutar: MundoOutdoor_StockPicking.exe
3. ¡Listo! El sistema se abrirá automáticamente

🔧 REQUISITOS:
- Windows 7 o superior
- No requiere Python instalado
- No requiere dependencias adicionales

📞 SOPORTE:
- Contactar al desarrollador si hay problemas
- Versión: 3.0 Optimizada

🚀 CARACTERÍSTICAS:
- Launcher visual con imagen de fondo
- Sistema completo de picking integrado
- Procesamiento paralelo optimizado
- Cache diario para máximo rendimiento
"""
            
            with open(dist_folder / "README.txt", "w", encoding="utf-8") as f:
                f.write(readme_content)
            
            print(f"\n📦 Carpeta de distribución creada: {dist_folder}")
            print("✅ Lista para copiar a otra PC")
            
        else:
            print("❌ Error al crear .exe")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en PyInstaller: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == "__main__":
    build_complete_exe()
