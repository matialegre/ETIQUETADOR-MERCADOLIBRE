#!/usr/bin/env python3
"""
Script para recrear la base de datos con la nueva estructura
que incluye campos de emergencia y observaciones
"""

import os
from app import app, db, Usuario, Profesional, Turno
from datetime import datetime, date, time

def recreate_database():
    """Recrear la base de datos con la nueva estructura"""
    
    # Eliminar base de datos existente si existe
    db_path = 'consultorio.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✅ Base de datos anterior eliminada: {db_path}")
    
    # Crear todas las tablas con la nueva estructura
    with app.app_context():
        db.create_all()
        print("✅ Nuevas tablas creadas con estructura actualizada")
        
        # Crear profesionales de ejemplo
        profesionales = [
            Profesional(
                nombre="Juan",
                apellido="Pérez",
                especialidad="Fonoaudiología General",
                imagen="doctor1.jpg"
            ),
            Profesional(
                nombre="María",
                apellido="González",
                especialidad="Terapia del Lenguaje",
                imagen="doctor2.jpg"
            ),
            Profesional(
                nombre="Carlos",
                apellido="Rodríguez",
                especialidad="Audiología",
                imagen="doctor3.jpg"
            ),
            Profesional(
                nombre="Ana",
                apellido="Martínez",
                especialidad="Fonoaudiología Infantil",
                imagen="doctor4.jpg"
            )
        ]
        
        for prof in profesionales:
            db.session.add(prof)
        
        # Crear algunos usuarios de ejemplo
        usuarios = [
            Usuario(
                dni="12345678",
                nombre="Pedro",
                apellido="López",
                telefono="1234567890",
                tiene_obra_social=True,
                historial="Paciente regular"
            ),
            Usuario(
                dni="87654321",
                nombre="Laura",
                apellido="García",
                telefono="0987654321",
                tiene_obra_social=False,
                historial="Primera consulta"
            )
        ]
        
        for usuario in usuarios:
            db.session.add(usuario)
        
        # Commit para obtener IDs
        db.session.commit()
        
        # Crear algunos turnos de ejemplo con la nueva estructura
        turnos_ejemplo = [
            Turno(
                profesional_id=1,
                usuario_id=1,
                fecha=date(2025, 8, 4),  # Lunes
                hora=time(9, 0),
                confirmado=True,
                es_emergencia=False,
                observaciones="Consulta de rutina"
            ),
            Turno(
                profesional_id=1,
                usuario_id=2,
                fecha=date(2025, 8, 5),  # Martes
                hora=time(10, 0),
                confirmado=True,
                es_emergencia=True,
                observaciones="Turno de emergencia - dolor agudo"
            ),
            Turno(
                profesional_id=2,
                usuario_id=1,
                fecha=date(2025, 8, 6),  # Miércoles
                hora=time(14, 0),
                confirmado=True,
                es_emergencia=False,
                observaciones="Seguimiento terapia"
            )
        ]
        
        for turno in turnos_ejemplo:
            db.session.add(turno)
        
        db.session.commit()
        print("✅ Datos de ejemplo creados")
        print(f"   - {len(profesionales)} profesionales")
        print(f"   - {len(usuarios)} usuarios")
        print(f"   - {len(turnos_ejemplo)} turnos (incluyendo emergencia)")
        
        print("\n🎉 Base de datos recreada exitosamente!")
        print("📋 Estructura actualizada incluye:")
        print("   - Campo 'es_emergencia' en turnos")
        print("   - Campo 'observaciones' en turnos")
        print("   - Datos de ejemplo para probar")

if __name__ == "__main__":
    recreate_database()
