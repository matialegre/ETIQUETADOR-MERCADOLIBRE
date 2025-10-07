#!/usr/bin/env python3
"""
Script de inicio para el Sistema de Turnos del Consultorio
Ejecutar con: python run.py
"""

import os
import sys

def install_requirements():
    """Instalar dependencias si no están instaladas"""
    try:
        import flask
        import flask_sqlalchemy
        print("✅ Dependencias ya instaladas")
    except ImportError:
        print("📦 Instalando dependencias...")
        os.system("pip install -r requirements.txt")

def main():
    print("🏥 Sistema de Turnos - Consultorio de Fonoaudiología")
    print("=" * 50)
    
    # Verificar e instalar dependencias
    install_requirements()
    
    # Importar y ejecutar la aplicación
    try:
        from app import app
        print("🚀 Iniciando servidor en http://localhost:5001")
        print("🌐 También disponible en tu IP pública:5001")
        print("👤 Usuario: secretario")
        print("🔑 Contraseña: admin123")
        print("=" * 50)
        
        app.run(host='0.0.0.0', port=5001, debug=True)
        
    except Exception as e:
        print(f"❌ Error al iniciar la aplicación: {e}")
        print("💡 Asegúrate de estar en el directorio correcto")
        sys.exit(1)

if __name__ == "__main__":
    main()
