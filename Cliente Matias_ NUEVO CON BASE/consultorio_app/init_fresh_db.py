#!/usr/bin/env python3
"""
Script simple para crear una base de datos completamente nueva
"""

import os
import sys

# Eliminar cualquier archivo de base de datos existente
db_files = ['consultorio.db', 'instance/consultorio.db']
for db_file in db_files:
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Eliminado: {db_file}")

# Crear directorio instance si no existe
os.makedirs('instance', exist_ok=True)

print("🔄 Creando nueva base de datos...")

# Importar después de limpiar
from app import app, db, Usuario, Profesional, Turno
from datetime import datetime, date, time

with app.app_context():
    # Forzar recreación de todas las tablas
    db.drop_all()
    db.create_all()
    
    print("✅ Tablas creadas con nueva estructura")
    
    # Crear profesionales
    profesionales = [
        Profesional(nombre="Juan", apellido="Pérez", especialidad="Fonoaudiología General", imagen="doctor1.jpg"),
        Profesional(nombre="María", apellido="González", especialidad="Terapia del Lenguaje", imagen="doctor2.jpg"),
        Profesional(nombre="Carlos", apellido="Rodríguez", especialidad="Audiología", imagen="doctor3.jpg"),
        Profesional(nombre="Ana", apellido="Martínez", especialidad="Fonoaudiología Infantil", imagen="doctor4.jpg")
    ]
    
    for prof in profesionales:
        db.session.add(prof)
    
    db.session.commit()
    print(f"✅ {len(profesionales)} profesionales creados")
    
    # Crear usuario de ejemplo
    usuario = Usuario(
        dni="12345678",
        nombre="Pedro",
        apellido="López", 
        telefono="1234567890",
        tiene_obra_social=True
    )
    db.session.add(usuario)
    db.session.commit()
    print("✅ Usuario de ejemplo creado")
    
    print("\n🎉 Base de datos inicializada correctamente!")
    print("📋 Nuevas columnas agregadas:")
    print("   - es_emergencia (Boolean)")
    print("   - observaciones (Text)")
