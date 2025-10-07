# Sistema de Turnos - Consultorio de Fonoaudiología

## 🏥 Descripción
Sistema completo de gestión de turnos para consultorios privados en Argentina, especializado en fonoaudiología. Permite gestionar hasta 1000 usuarios con historiales completos.

## 🚀 Características Principales
- **Login de Secretario**: Acceso seguro al sistema
- **Gestión de Profesionales**: 4 profesionales con especialidades
- **Calendario Inteligente**: Vista mensual con horarios de lunes a viernes
- **Auto-completado**: Búsqueda automática por DNI
- **Base de Datos**: SQLite para almacenamiento local
- **Responsive**: Diseño adaptable con Bootstrap

## 📋 Requisitos del Sistema
- Python 3.7 o superior
- Navegador web moderno
- Conexión a internet (para Bootstrap y FontAwesome)

## 🛠️ Instalación

### Opción 1: Instalación Automática
```bash
cd consultorio_app
python run.py
```

### Opción 2: Instalación Manual
```bash
cd consultorio_app
pip install -r requirements.txt
python app.py
```

## 🌐 Acceso al Sistema
- **URL Local**: http://localhost:5001
- **URL Red**: http://TU_IP:5001
- **Usuario**: secretario
- **Contraseña**: admin123

## 📱 Uso del Sistema

### 1. Login
- Ingresa con las credenciales por defecto
- El sistema validará el acceso

### 2. Selección de Profesional
- Elige entre los 4 profesionales disponibles
- Cada uno tiene su especialidad definida

### 3. Gestión de Turnos
- **Navegación**: Usa las flechas para cambiar de mes
- **Horarios**: 8:00 AM a 6:00 PM, lunes a viernes
- **Nuevo Turno**: Click en casilla vacía
- **Editar Turno**: Click en turno existente
- **Auto-completado**: Ingresa DNI y presiona Enter

## 🗃️ Estructura de Datos

### Usuarios
- DNI (único)
- Nombre y Apellido
- Teléfono
- Obra Social (Sí/No)
- Historial médico

### Profesionales
- Dr. Juan Pérez - Fonoaudiología General
- Dra. María González - Terapia del Lenguaje
- Dr. Carlos Rodríguez - Audiología
- Dra. Ana Martínez - Deglución

### Turnos
- Fecha y hora
- Profesional asignado
- Usuario asociado
- Estado de confirmación

## 🎨 Diseño Visual
- **Colores**: Esquema verde-azulado con elementos violetas
- **Turnos Asignados**: Fondo verde claro
- **Turnos Libres**: Fondo gris claro
- **Elementos Interactivos**: Efectos hover y transiciones

## 🔧 Configuración Avanzada

### Cambiar Puerto
Edita `app.py` línea final:
```python
app.run(host='0.0.0.0', port=NUEVO_PUERTO, debug=True)
```

### Agregar Profesionales
Modifica la función `init_db()` en `app.py`

### Modificar Horarios
Cambia el rango en la ruta `/calendario`:
```python
for hour in range(8, 19):  # 8 AM a 6 PM
```

## 🚨 Solución de Problemas

### Error de Puerto Ocupado
```bash
netstat -ano | findstr :5001
taskkill /PID [PID_NUMBER] /F
```

### Base de Datos Corrupta
```bash
rm consultorio.db
python app.py  # Se recreará automáticamente
```

### Dependencias Faltantes
```bash
pip install --upgrade -r requirements.txt
```

## 🔐 Seguridad
- Cambiar credenciales por defecto en producción
- Implementar hash de contraseñas
- Configurar HTTPS para producción
- Backup regular de la base de datos

## 📞 Soporte
Para soporte técnico o nuevas funcionalidades, contactar al desarrollador.

## 🔄 Próximas Funcionalidades
- Aplicación para profesionales
- Reportes y estadísticas
- Notificaciones automáticas
- Integración con sistemas externos
