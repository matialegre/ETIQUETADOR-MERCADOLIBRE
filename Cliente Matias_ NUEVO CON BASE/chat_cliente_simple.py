#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chat Cliente Simple - Mundo Outdoor
Cliente simplificado para generar .exe sin problemas
"""

import time
import webbrowser
import threading
import os
import sys
from flask import Flask, render_template

# Configuración para .exe
if getattr(sys, 'frozen', False):
    # Ejecutándose como .exe
    template_dir = os.path.join(sys._MEIPASS, 'templates')
else:
    # Ejecutándose como script
    template_dir = 'templates'

app = Flask(__name__, template_folder=template_dir)
app.config['SECRET_KEY'] = 'mundo_outdoor_chat_cliente_simple_2025'

class ChatClientSimple:
    def __init__(self):
        self.client_port = 5557
        self.client_host = '0.0.0.0'
        
# Rutas Flask
@app.route('/')
def index():
    return render_template('chat_cliente_simple.html')

# Inicializar cliente
chat_client = ChatClientSimple()

def start_client():
    """Iniciar el cliente de chat simple"""
    print("🚀 Iniciando Cliente de Chat Simple - Mundo Outdoor")
    print(f"🌐 Cliente Web: http://localhost:{chat_client.client_port}")
    print("📝 Ingresa la IP del servidor en la interfaz web")
    print("=" * 50)
    
    # Abrir navegador automáticamente
    def open_browser():
        time.sleep(2)
        webbrowser.open(f'http://localhost:{chat_client.client_port}')
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Iniciar servidor web del cliente (sin SocketIO)
    app.run(host=chat_client.client_host, 
            port=chat_client.client_port, 
            debug=False,
            threaded=True)

if __name__ == '__main__':
    start_client()
