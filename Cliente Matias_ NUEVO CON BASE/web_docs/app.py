#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Servidor web de documentación para el Sistema de Picking de Mundo Outdoor.
Hostea en puerto 5003 una guía completa para usuarios del sistema.
"""

from flask import Flask, render_template, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# Configuración
app.config['SECRET_KEY'] = 'mundo_outdoor_docs_2025'

@app.route('/')
def index():
    """Página principal con información general."""
    return render_template('index.html')

@app.route('/guia-rapida')
def guia_rapida():
    """Guía rápida de uso del sistema."""
    return render_template('guia_rapida.html')

@app.route('/guia_practica')
def guia_practica():
    """Guía práctica de uso del sistema."""
    return render_template('guia_practica.html')

@app.route('/instalacion')
def instalacion():
    """Instrucciones de instalación."""
    return render_template('instalacion.html')

@app.route('/picking')
def picking():
    """Guía detallada del proceso de picking."""
    return render_template('picking.html')

@app.route('/problemas')
def problemas():
    """Solución de problemas comunes."""
    return render_template('problemas.html')

@app.route('/api/status')
def api_status():
    """API endpoint para verificar estado del servidor."""
    return jsonify({
        'status': 'online',
        'service': 'Mundo Outdoor - Sistema de Picking',
        'version': '3.0',
        'timestamp': datetime.now().isoformat(),
        'empresa': 'Mundo Outdoor'
    })

@app.errorhandler(404)
def not_found(error):
    """Página de error 404 personalizada."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Página de error 500 personalizada."""
    return render_template('500.html'), 500

if __name__ == '__main__':
    print("🌐 SERVIDOR WEB MUNDO OUTDOOR")
    print("=" * 50)
    print("🏢 Empresa: Mundo Outdoor")
    print("📖 Servicio: Documentación Sistema de Picking")
    print("🌍 Puerto: 5003")
    print("📱 Acceso: http://tu-ip-publica:5003")
    print("=" * 50)
    print("🚀 Iniciando servidor...")
    
    # Ejecutar en todas las interfaces (0.0.0.0) para acceso remoto
    app.run(
        host='0.0.0.0',  # Permite acceso desde cualquier IP
        port=5003,       # Puerto específico solicitado
        debug=False,     # Desactivar debug en producción
        threaded=True    # Permitir múltiples conexiones
    )
