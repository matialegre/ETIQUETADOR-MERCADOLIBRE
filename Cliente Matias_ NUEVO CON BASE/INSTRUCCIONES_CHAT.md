# 💬 Chat Mundo Outdoor - Instrucciones

## 📋 Descripción
Sistema de chat profesional para comunicación entre oficina y depósito con transferencia de archivos hasta 200MB.

## 🚀 Instalación Rápida

### 1. Instalar Dependencias
```bash
pip install -r requirements_chat.txt
```

### 2. Para el SERVIDOR (Oficina - 192.168.0.102)
- Ejecutar: `iniciar_servidor_chat.bat`
- O manualmente: `python chat_servidor.py`
- Se abre automáticamente en: http://192.168.0.102:5556

### 3. Para el CLIENTE (Depósito - cualquier IP)
**Opción A: Con Python instalado**
- Ejecutar: `iniciar_cliente_chat.bat`
- O manualmente: `python chat_cliente.py`

**Opción B: Ejecutable standalone (SIN Python)**
- Ejecutar: `python build_chat_cliente.py`
- Copiar `dist/ChatCliente_MundoOutdoor.exe` al depósito
- Ejecutar el .exe directamente

## 🔧 Uso

### Servidor (Oficina):
1. Ejecutar servidor
2. Ingresar nombre y ubicación
3. Listo para recibir conexiones

### Cliente (Depósito):
1. Ejecutar cliente
2. **Ingresar IP del servidor** (ej: 192.168.0.102)
3. Ingresar nombre y ubicación
4. Conectar

## 📁 Transferencia de Archivos

### Enviar Archivo:
- Click en botón 📎 (clip)
- Seleccionar archivo (máximo 200MB)
- Se sube automáticamente y notifica a todos

### Descargar Archivo:
- Click en mensaje de archivo (color azul/verde)
- Se descarga automáticamente

### Tipos de Archivo Soportados:
- ✅ Ejecutables (.exe) hasta 200MB
- ✅ Documentos (PDF, Word, Excel)
- ✅ Imágenes (JPG, PNG, etc.)
- ✅ Cualquier tipo de archivo

## 🌐 Configuración de Red

### IPs de Ejemplo:
- **Servidor (Oficina):** 192.168.0.102:5556
- **Cliente puede ser cualquier IP:** 192.168.0.105, 192.168.0.110, etc.

### Puertos Utilizados:
- **Servidor:** 5556 (chat web)
- **Cliente:** 5557 (interfaz local)

## 🎨 Características

### Chat:
- ✅ Mensajes en tiempo real
- ✅ Indicador de "escribiendo..."
- ✅ Historial de mensajes
- ✅ Lista de usuarios conectados
- ✅ Notificaciones de conexión/desconexión

### Archivos:
- ✅ Transferencia hasta 200MB
- ✅ Barra de progreso
- ✅ Descarga con un click
- ✅ Nombres de archivo preservados
- ✅ Información de tamaño

### Interfaz:
- ✅ Diseño Bootstrap profesional
- ✅ Colores diferenciados por ubicación
- ✅ Responsive (funciona en móviles)
- ✅ Auto-scroll de mensajes

## 🔍 Solución de Problemas

### "No se puede conectar al servidor"
- Verificar que el servidor esté ejecutándose
- Verificar la IP ingresada (debe ser la del servidor)
- Verificar que estén en la misma red

### "Error subiendo archivo"
- Verificar tamaño del archivo (máximo 200MB)
- Verificar conexión a internet/red
- Reintentar la subida

### "El .exe no funciona"
- Verificar que se compiló correctamente
- Ejecutar como administrador si es necesario
- Verificar que no esté bloqueado por antivirus

## 📞 Comandos Útiles

### Generar .exe del cliente:
```bash
python build_chat_cliente.py
```

### Instalar dependencias:
```bash
pip install flask==2.3.3 flask-socketio==5.3.6 python-socketio==5.8.0 python-engineio==4.7.1 eventlet==0.33.3
```

### Verificar IP local:
```bash
ipconfig
```

## 📂 Estructura de Archivos
```
├── chat_servidor.py          # Servidor principal
├── chat_cliente.py           # Cliente principal
├── templates/
│   ├── chat_servidor.html    # Interfaz del servidor
│   └── chat_cliente.html     # Interfaz del cliente
├── build_chat_cliente.py     # Script para generar .exe
├── requirements_chat.txt     # Dependencias
├── iniciar_servidor_chat.bat # Inicio rápido servidor
├── iniciar_cliente_chat.bat  # Inicio rápido cliente
└── chat_files/              # Archivos transferidos (se crea automáticamente)
```

## 🎉 ¡Listo!
El sistema está completo y listo para usar. Cualquier duda, revisar este archivo o contactar al desarrollador.
