#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chat Servidor - Mundo Outdoor
Servidor de chat para comunicación entre Oficina y Depósito
IP Servidor: 192.168.0.102
"""

import socket
import threading
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit, join_room, leave_room
import webbrowser
import os
import base64
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mundo_outdoor_chat_2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Estado del chat
connected_users = {}
chat_history = []
MAX_HISTORY = 100

# Configuración de archivos
UPLOAD_FOLDER = 'chat_files'
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

class ChatServer:
    def __init__(self):
        self.host = '192.168.0.102'
        self.port = 5555
        self.web_port = 5556
        
    def add_message(self, username, message, msg_type='message'):
        """Agregar mensaje al historial"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        msg_data = {
            'username': username,
            'message': message,
            'timestamp': timestamp,
            'type': msg_type
        }
        
        chat_history.append(msg_data)
        
        # Mantener solo los últimos MAX_HISTORY mensajes
        if len(chat_history) > MAX_HISTORY:
            chat_history.pop(0)
            
        return msg_data

# Rutas Flask
@app.route('/')
def index():
    return render_template('chat_servidor.html')

@app.route('/api/history')
def get_history():
    return jsonify(chat_history)

@app.route('/api/users')
def get_users():
    return jsonify(list(connected_users.values()))

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        return jsonify({
            'success': True,
            'filename': unique_filename,
            'original_name': filename,
            'size': file_size
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Eventos SocketIO
@socketio.on('connect')
def on_connect():
    print(f"🔗 Cliente conectado: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"❌ Cliente desconectado: {request.sid}")
    # Remover usuario si estaba conectado
    user_to_remove = None
    for sid, user in connected_users.items():
        if sid == request.sid:
            user_to_remove = sid
            break
    
    if user_to_remove:
        username = connected_users[user_to_remove]['username']
        del connected_users[user_to_remove]
        
        # Notificar desconexión
        msg_data = chat_server.add_message('SISTEMA', f'{username} se desconectó', 'system')
        socketio.emit('new_message', msg_data)
        socketio.emit('user_list_update', list(connected_users.values()))

@socketio.on('user_login')
def on_user_login(data):
    username = data['username'].strip()
    location = data.get('location', 'Desconocido')
    
    if not username:
        emit('login_error', {'error': 'El nombre no puede estar vacío'})
        return
    
    # Verificar si el nombre ya está en uso
    for user in connected_users.values():
        if user['username'].lower() == username.lower():
            emit('login_error', {'error': 'Este nombre ya está en uso'})
            return
    
    # Registrar usuario
    connected_users[request.sid] = {
        'username': username,
        'location': location,
        'connected_at': datetime.now().strftime('%H:%M:%S')
    }
    
    print(f"👤 Usuario conectado: {username} desde {location}")
    
    # Confirmar login exitoso
    emit('login_success', {'username': username})
    
    # Notificar a todos
    msg_data = chat_server.add_message('SISTEMA', f'{username} ({location}) se conectó', 'system')
    socketio.emit('new_message', msg_data)
    socketio.emit('user_list_update', list(connected_users.values()))

@socketio.on('send_message')
def on_send_message(data):
    if request.sid not in connected_users:
        emit('error', {'error': 'Usuario no autenticado'})
        return
    
    username = connected_users[request.sid]['username']
    message = data['message'].strip()
    
    if not message:
        return
    
    print(f"💬 {username}: {message}")
    
    # Agregar mensaje y enviar a todos
    msg_data = chat_server.add_message(username, message)
    socketio.emit('new_message', msg_data)

@socketio.on('file_shared')
def on_file_shared(data):
    if request.sid not in connected_users:
        emit('error', {'error': 'Usuario no autenticado'})
        return
    
    username = connected_users[request.sid]['username']
    filename = data['filename']
    original_name = data['original_name']
    file_size = data['size']
    
    print(f"📎 {username} compartió archivo: {original_name} ({file_size} bytes)")
    
    # Crear mensaje de archivo compartido
    file_message = f"📎 Archivo compartido: {original_name} ({format_file_size(file_size)})"
    msg_data = chat_server.add_message(username, file_message, 'file')
    msg_data['file_info'] = {
        'filename': filename,
        'original_name': original_name,
        'size': file_size
    }
    
    socketio.emit('new_message', msg_data)

@socketio.on('typing')
def on_typing(data):
    if request.sid not in connected_users:
        return
    
    username = connected_users[request.sid]['username']
    socketio.emit('user_typing', {'username': username, 'typing': data['typing']}, include_self=False)

def format_file_size(size_bytes):
    """Formatear tamaño de archivo en formato legible"""
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"

# Inicializar servidor
chat_server = ChatServer()

def start_server():
    """Iniciar el servidor de chat"""
    print("🚀 Iniciando Servidor de Chat - Mundo Outdoor")
    print(f"📍 IP Servidor: {chat_server.host}")
    print(f"🌐 Puerto Web: {chat_server.web_port}")
    print(f"🔗 URL: http://{chat_server.host}:{chat_server.web_port}")
    print("=" * 50)
    
    # Abrir navegador automáticamente
    def open_browser():
        time.sleep(2)
        webbrowser.open(f'http://{chat_server.host}:{chat_server.web_port}')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Iniciar servidor
    socketio.run(app, 
                host=chat_server.host, 
                port=chat_server.web_port, 
                debug=False,
                allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    start_server()
