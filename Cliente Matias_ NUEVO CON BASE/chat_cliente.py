#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chat Cliente - Mundo Outdoor
Cliente de chat para comunicación entre Oficina y Depósito
IP Cliente: 192.168.0.105 (o cualquier IP de la red)
"""

import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import webbrowser
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mundo_outdoor_chat_cliente_2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

class ChatClient:
    def __init__(self):
        self.server_host = None  # Se configurará dinámicamente
        self.server_port = 5556
        self.client_port = 5557  # Puerto para la interfaz web del cliente
        self.client_host = '0.0.0.0'  # Escuchar en todas las interfaces
        
# Rutas Flask
@app.route('/')
def index():
    return render_template('chat_cliente.html', server_port=chat_client.server_port)

# Inicializar cliente
chat_client = ChatClient()

def start_client():
    """Iniciar el cliente de chat"""
    print("🚀 Iniciando Cliente de Chat - Mundo Outdoor")
    print(f"🌐 Cliente Web: http://localhost:{chat_client.client_port}")
    print(f"🔗 También disponible en red: http://0.0.0.0:{chat_client.client_port}")
    print("📝 Ingresa la IP del servidor en la interfaz web")
    print("=" * 50)
    
    # Abrir navegador automáticamente
    def open_browser():
        time.sleep(2)
        webbrowser.open(f'http://localhost:{chat_client.client_port}')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Iniciar servidor web del cliente
    socketio.run(app, 
                host=chat_client.client_host, 
                port=chat_client.client_port, 
                debug=False,
                allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    start_client()
