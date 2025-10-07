from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, date, timedelta
import calendar
import secrets
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_aqui_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///consultorio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'tu_clave_secreta_aqui'
app.config['JWT_SECRET_KEY'] = secrets.token_hex(32)

db = SQLAlchemy(app)
CORS(app, origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"], 
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Modelos de Base de Datos
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dni = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    tiene_obra_social = db.Column(db.Boolean, default=False)
    historial = db.Column(db.Text, default='')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

class Profesional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    especialidad = db.Column(db.String(100), nullable=False)
    imagen = db.Column(db.String(200), default='default.jpg')

class Professional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    avatar = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Turno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    profesional_id = db.Column(db.Integer, db.ForeignKey('profesional.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    dni_paciente = db.Column(db.String(20), nullable=False)
    nombre_paciente = db.Column(db.String(100), nullable=False)
    apellido_paciente = db.Column(db.String(100), nullable=False)
    telefono_paciente = db.Column(db.String(20), nullable=False)
    obra_social = db.Column(db.String(100), nullable=False)
    es_emergencia = db.Column(db.Boolean, default=False)
    observaciones = db.Column(db.Text, nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    profesional = db.relationship('Profesional', backref=db.backref('turnos', lazy=True))

# Rutas principales
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_login():
    usuario = request.form.get('usuario')
    password = request.form.get('password')
    
    # Login simple - en producción usar hash de passwords
    if usuario == 'secretario' and password == 'admin123':
        session['logged_in'] = True
        session['usuario'] = usuario
        return redirect(url_for('profesionales'))
    else:
        return render_template('login.html', error='Usuario o contraseña incorrectos')

@app.route('/profesionales')
def profesionales():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    profesionales = Profesional.query.all()
    return render_template('profesionales.html', profesionales=profesionales)

@app.route('/calendario/<int:profesional_id>')
@app.route('/calendario/<int:profesional_id>/<int:year>/<int:week>')
def calendario(profesional_id, year=None, week=None):
    profesional = Profesional.query.get_or_404(profesional_id)
    
    if year is None or week is None:
        today = datetime.now().date()
        year = today.year
        # Obtener número de semana del año
        week = today.isocalendar()[1]
    
    # Obtener el primer día de la semana (lunes)
    jan_1 = datetime(year, 1, 1).date()
    # Encontrar el primer lunes del año
    days_to_monday = (7 - jan_1.weekday()) % 7
    if jan_1.weekday() != 0:  # Si no es lunes
        days_to_monday = 7 - jan_1.weekday()
    first_monday = jan_1 + timedelta(days=days_to_monday)
    
    # Calcular el lunes de la semana solicitada
    monday_of_week = first_monday + timedelta(weeks=week-1)
    
    # Generar los 5 días laborables de la semana
    dias_semana = []
    for i in range(5):  # Lunes a viernes
        fecha = monday_of_week + timedelta(days=i)
        dias_semana.append({
            'day': fecha.day,
            'date': fecha,
            'weekday': i,
            'weekday_name': ['LUN', 'MAR', 'MIÉ', 'JUE', 'VIE'][i],
            'month_name': calendar.month_name[fecha.month]
        })
    
    # Horarios disponibles (8:00 a 18:00)
    horarios = []
    for hour in range(8, 19):
        horarios.append(f"{hour:02d}:00")
    
    # Información de la semana
    semana_info = {
        'numero': week,
        'año': year,
        'fecha_inicio': monday_of_week,
        'fecha_fin': monday_of_week + timedelta(days=4),
        'mes_nombre': calendar.month_name[monday_of_week.month]
    }
    
    # Obtener turnos de la semana
    fecha_inicio = monday_of_week
    fecha_fin = monday_of_week + timedelta(days=4)
    
    turnos = Turno.query.filter(
        Turno.profesional_id == profesional_id,
        Turno.fecha >= fecha_inicio,
        Turno.fecha <= fecha_fin
    ).all()
    
    # Organizar turnos por fecha y hora para el template
    turnos_organizados = {}
    for turno in turnos:
        fecha_str = turno.fecha.strftime('%Y-%m-%d')
        hora_str = turno.hora.strftime('%H:%M')
        
        if fecha_str not in turnos_organizados:
            turnos_organizados[fecha_str] = {}
        
        turnos_organizados[fecha_str][hora_str] = turno
    
    # También mantener el formato anterior para compatibilidad
    turnos_dict = {}
    for turno in turnos:
        key = f"{turno.fecha}_{turno.hora}"
        turnos_dict[key] = turno
    
    # Calcular semana anterior y siguiente
    semana_anterior = week - 1 if week > 1 else 52
    year_anterior = year if week > 1 else year - 1
    
    semana_siguiente = week + 1 if week < 52 else 1
    year_siguiente = year if week < 52 else year + 1
    
    return render_template('calendario.html', 
                         profesional=profesional,
                         dias_semana=dias_semana,
                         semana_info=semana_info,
                         year=year,
                         week=week,
                         semana_anterior=semana_anterior,
                         year_anterior=year_anterior,
                         semana_siguiente=semana_siguiente,
                         year_siguiente=year_siguiente,
                         horarios=horarios,
                         turnos=turnos_dict,
                         turnos_organizados=turnos_organizados)

@app.route('/eliminar_turno/<int:turno_id>', methods=['DELETE'])
def eliminar_turno(turno_id):
    try:
        turno = Turno.query.get_or_404(turno_id)
        db.session.delete(turno)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Turno eliminado correctamente'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/buscar_usuario/<dni>')
def buscar_usuario(dni):
    usuario = Usuario.query.filter_by(dni=dni).first()
    if usuario:
        return jsonify({
            'encontrado': True,
            'id': usuario.id,
            'nombre': usuario.nombre,
            'apellido': usuario.apellido,
            'telefono': usuario.telefono,
            'tiene_obra_social': usuario.tiene_obra_social
        })
    else:
        return jsonify({'encontrado': False})

@app.route('/crear_turno', methods=['POST'])
def crear_turno():
    data = request.json
    
    # Buscar o crear usuario
    usuario = Usuario.query.filter_by(dni=data['dni']).first()
    if not usuario:
        usuario = Usuario(
            dni=data['dni'],
            nombre=data['nombre'],
            apellido=data['apellido'],
            telefono=data['telefono'],
            tiene_obra_social=data['tiene_obra_social']
        )
        db.session.add(usuario)
        db.session.flush()  # Para obtener el ID
    
    # Verificar si ya existe un turno en esa fecha/hora
    fecha = datetime.strptime(data['fecha'], '%Y-%m-%d').date()
    hora = datetime.strptime(data['hora'], '%H:%M').time()
    
    es_emergencia = data.get('es_emergencia', False)
    observaciones = data.get('observaciones', '')
    
    turno_existente = Turno.query.filter_by(
        profesional_id=data['profesional_id'],
        fecha=fecha,
        hora=hora
    ).first()
    
    if turno_existente and not es_emergencia:
        # Actualizar turno existente (solo si no es emergencia)
        turno_existente.usuario_id = usuario.id
        turno_existente.confirmado = True
        turno_existente.observaciones = observaciones
    else:
        # Crear nuevo turno (normal o de emergencia)
        turno = Turno(
            profesional_id=data['profesional_id'],
            usuario_id=usuario.id,
            fecha=fecha,
            hora=hora,
            confirmado=True,
            es_emergencia=es_emergencia,
            observaciones=observaciones
        )
        db.session.add(turno)
    
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================================
# RUTAS API PARA FRONTEND REACT
# ================================

def generate_token(professional_id):
    """Generar JWT token para autenticación"""
    payload = {
        'professional_id': professional_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')

def verify_token(token):
    """Verificar JWT token"""
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        return payload['professional_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@app.route('/api/professional/login', methods=['POST'])
def api_professional_login():
    """Login endpoint para profesionales"""
    print(f"🔍 LOGIN REQUEST: {request.method} {request.url}")
    print(f"🔍 Headers: {dict(request.headers)}")
    print(f"🔍 Content-Type: {request.content_type}")
    
    try:
        data = request.get_json()
        print(f"🔍 Data received: {data}")
        
        if not data:
            print("❌ No JSON data received")
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
            
        email = data.get('email')
        password = data.get('password')
        print(f"🔍 Email: {email}, Password: {'*' * len(password) if password else 'None'}")
        
        if not email or not password:
            print("❌ Email o contraseña faltantes")
            return jsonify({'error': 'Email y contraseña son requeridos'}), 400
        
        # Buscar profesional por email
        professional = Professional.query.filter_by(email=email, is_active=True).first()
        print(f"🔍 Professional found: {professional.name if professional else 'None'}")
        
        if not professional:
            print("❌ Professional not found")
            return jsonify({'error': 'Credenciales inválidas'}), 401
            
        if not check_password_hash(professional.password, password):
            print("❌ Password incorrect")
            return jsonify({'error': 'Credenciales inválidas'}), 401
        
        # Generar token
        token = generate_token(professional.id)
        print(f"✅ Login successful for {professional.name}")
        
        return jsonify({
            'success': True,
            'token': token,
            'id': str(professional.id),
            'name': professional.name,
            'email': professional.email,
            'specialization': professional.specialization,
            'phone': professional.phone,
            'avatar': professional.avatar
        })
        
    except Exception as e:
        print(f"❌ Exception in login: {str(e)}")
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/professional/dashboard', methods=['GET'])
def api_professional_dashboard():
    """Dashboard data para profesionales"""
    try:
        # Verificar token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token requerido'}), 401
        
        token = auth_header.split(' ')[1]
        professional_id = verify_token(token)
        
        if not professional_id:
            return jsonify({'error': 'Token inválido'}), 401
        
        # Obtener estadísticas del día
        today = date.today()
        turnos_hoy = Turno.query.filter_by(
            profesional_id=professional_id,
            fecha=today
        ).all()
        
        # Próximo turno
        proximo_turno = Turno.query.filter(
            Turno.profesional_id == professional_id,
            Turno.fecha >= today
        ).order_by(Turno.fecha, Turno.hora).first()
        
        # Estadísticas
        stats = {
            'todayAppointments': len(turnos_hoy),
            'completedToday': len([t for t in turnos_hoy if t.observaciones]),
            'pendingToday': len([t for t in turnos_hoy if not t.observaciones]),
            'emergencyCount': len([t for t in turnos_hoy if t.es_emergencia]),
            'nextAppointment': None
        }
        
        if proximo_turno:
            stats['nextAppointment'] = {
                'id': str(proximo_turno.id),
                'patientName': f"{proximo_turno.nombre_paciente} {proximo_turno.apellido_paciente}",
                'patientDni': proximo_turno.dni_paciente,
                'patientPhone': proximo_turno.telefono_paciente,
                'date': proximo_turno.fecha.isoformat(),
                'time': proximo_turno.hora.strftime('%H:%M'),
                'status': 'emergency' if proximo_turno.es_emergencia else 'scheduled'
            }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/professional/schedule/<int:year>/<int:week>', methods=['GET'])
def api_professional_schedule(year, week):
    """Horarios semanales para profesionales"""
    try:
        # Verificar token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token requerido'}), 401
        
        token = auth_header.split(' ')[1]
        professional_id = verify_token(token)
        
        if not professional_id:
            return jsonify({'error': 'Token inválido'}), 401
        
        # Calcular fechas de la semana
        first_day = datetime.strptime(f'{year}-W{week:02d}-1', '%Y-W%W-%w').date()
        days = [first_day + timedelta(days=i) for i in range(5)]  # Lunes a viernes
        
        # Obtener turnos de la semana
        turnos = Turno.query.filter(
            Turno.profesional_id == professional_id,
            Turno.fecha.between(days[0], days[4])
        ).all()
        
        # Formatear turnos para el frontend
        appointments = []
        for turno in turnos:
            appointments.append({
                'id': str(turno.id),
                'patientId': turno.dni_paciente,
                'patientName': f"{turno.nombre_paciente} {turno.apellido_paciente}",
                'patientDni': turno.dni_paciente,
                'patientPhone': turno.telefono_paciente,
                'date': turno.fecha.isoformat(),
                'time': turno.hora.strftime('%H:%M'),
                'duration': 30,
                'status': 'emergency' if turno.es_emergencia else ('completed' if turno.observaciones else 'scheduled'),
                'notes': turno.observaciones or '',
                'treatmentType': 'Fonoaudiología'
            })
        
        return jsonify({
            'appointments': appointments,
            'weekDates': [day.isoformat() for day in days]
        })
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/api/patients/search', methods=['GET'])
def api_patients_search():
    """Búsqueda de pacientes"""
    try:
        # Verificar token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token requerido'}), 401
        
        token = auth_header.split(' ')[1]
        professional_id = verify_token(token)
        
        if not professional_id:
            return jsonify({'error': 'Token inválido'}), 401
        
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'patients': []})
        
        # Buscar usuarios por DNI o nombre
        usuarios = Usuario.query.filter(
            db.or_(
                Usuario.dni.like(f'%{query}%'),
                Usuario.nombre.like(f'%{query}%'),
                Usuario.apellido.like(f'%{query}%')
            )
        ).limit(10).all()
        
        patients = []
        for usuario in usuarios:
            # Obtener último turno
            ultimo_turno = Turno.query.filter_by(
                dni_paciente=usuario.dni
            ).order_by(Turno.fecha.desc()).first()
            
            patients.append({
                'id': str(usuario.id),
                'firstName': usuario.nombre,
                'lastName': usuario.apellido,
                'dni': usuario.dni,
                'phone': usuario.telefono,
                'insurance': 'Sí' if usuario.tiene_obra_social else 'No',
                'lastVisit': ultimo_turno.fecha.isoformat() if ultimo_turno else None,
                'treatmentStatus': 'active'
            })
        
        return jsonify({'patients': patients})
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

def init_db():
    """Inicializar la base de datos con datos de ejemplo"""
    db.create_all()
    
    # Crear profesionales de ejemplo si no existen
    if Profesional.query.count() == 0:
        profesionales = [
            Profesional(nombre='Dr. Juan', apellido='Pérez', especialidad='Fonoaudiología General', imagen='doctor1.jpg'),
            Profesional(nombre='Dra. María', apellido='González', especialidad='Terapia del Lenguaje', imagen='doctor2.jpg'),
            Profesional(nombre='Dr. Carlos', apellido='Rodríguez', especialidad='Audiología', imagen='doctor3.jpg'),
            Profesional(nombre='Dra. Ana', apellido='Martínez', especialidad='Deglución', imagen='doctor4.jpg')
        ]
        
        for prof in profesionales:
            db.session.add(prof)
        
        db.session.commit()
    
    # Crear profesionales para el sistema React si no existen
    if Professional.query.count() == 0:
        react_professionals = [
            Professional(
                name='Dr. Juan Pérez',
                email='juan.perez@consultorio.com',
                password=generate_password_hash('123456'),
                specialization='Fonoaudiología General',
                phone='+54 11 1234-5678',
                avatar=None
            ),
            Professional(
                name='Dra. María González',
                email='maria.gonzalez@consultorio.com',
                password=generate_password_hash('123456'),
                specialization='Terapia del Lenguaje',
                phone='+54 11 2345-6789',
                avatar=None
            ),
            Professional(
                name='Dr. Carlos Rodríguez',
                email='carlos.rodriguez@consultorio.com',
                password=generate_password_hash('123456'),
                specialization='Audiología',
                phone='+54 11 3456-7890',
                avatar=None
            ),
            Professional(
                name='Dra. Ana Martínez',
                email='ana.martinez@consultorio.com',
                password=generate_password_hash('123456'),
                specialization='Deglución',
                phone='+54 11 4567-8901',
                avatar=None
            )
        ]
        
        for prof in react_professionals:
            db.session.add(prof)
        
        db.session.commit()
        print("✅ Profesionales creados para el sistema React:")
        for prof in react_professionals:
            print(f"   📧 {prof.email} - Contraseña: 123456")

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
