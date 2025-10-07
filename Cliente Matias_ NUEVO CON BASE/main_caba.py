#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLIENTE MATÍAS - VERSIÓN CABA
===============================

Aplicación de picking específica para MUNDO CABA.

Configuración:
- API Dragonfish: Servidor remoto en Bahía Blanca (190.211.201.217:8009)
- Base de datos: DRAGONFISH_MUNDOCAB en DESKTOP-CK25NCF\ZOOLOGIC
- Filtros: CAB, CABA, MUNDOCAB

Autor: Sistema de Picking
Versión: CABA v1.0
"""

import sys
import os
import time
import traceback
from pathlib import Path

# CONFIGURACIÓN CABA: Establecer variable de entorno para identificar versión
os.environ['CABA_VERSION'] = 'true'

# Agregar el directorio raíz al path para imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Importar configuración específica de CABA
import config_caba

def setup_logging():
    """Configura el sistema de logging para CABA."""
    import logging
    from utils.logger import get_logger
    
    # Configurar logging específico para CABA
    log = get_logger("CABA_MAIN")
    log.info("=" * 60)
    log.info("🏢 INICIANDO SISTEMA CABA")
    log.info("=" * 60)
    log.info(f"📡 API Dragonfish: {config_caba.DRAGONFISH_BASE_URL}")
    log.info(f"🗄️ SQL Server: {config_caba.SQL_SERVER}")
    log.info(f"📊 Base de datos: {config_caba.DATABASE_NAME}")
    log.info(f"🏷️ Keywords: {config_caba.KEYWORDS_NOTE_CABA}")
    log.info("=" * 60)
    
    return log

def test_dependencies():
    """Verifica que todas las dependencias estén disponibles."""
    log = setup_logging()
    
    try:
        # Test imports críticos
        log.info("🔍 Verificando dependencias...")
        
        import tkinter
        log.info("✅ tkinter disponible")
        
        import ttkbootstrap
        log.info("✅ ttkbootstrap disponible")
        
        import requests
        log.info("✅ requests disponible")
        
        import pyodbc
        log.info("✅ pyodbc disponible")
        
        from reportlab.lib.pagesizes import A4
        log.info("✅ reportlab disponible")
        
        log.info("✅ Todas las dependencias verificadas")
        return True
        
    except ImportError as e:
        log.error(f"❌ Dependencia faltante: {e}")
        return False
    except Exception as e:
        log.error(f"❌ Error verificando dependencias: {e}")
        return False

def test_connections():
    """Prueba las conexiones remotas."""
    log = setup_logging()
    
    try:
        log.info("🔧 Probando conexiones remotas...")
        
        # Test API Dragonfish
        from api.dragonfish_api_caba import dragonfish_caba
        api_ok = dragonfish_caba.test_connection()
        
        if api_ok:
            log.info("✅ Conexión API Dragonfish OK")
        else:
            log.warning("⚠️ Conexión API Dragonfish FALLO")
        
        # Test Base de datos
        from utils.db_caba import db_caba
        db_ok = db_caba.test_connection()
        
        if db_ok:
            log.info("✅ Conexión Base de datos OK")
        else:
            log.warning("⚠️ Conexión Base de datos FALLO")
        
        return api_ok and db_ok
        
    except Exception as e:
        log.error(f"❌ Error probando conexiones: {e}")
        return False

def show_startup_info():
    """Muestra información de inicio en consola."""
    print("\n" + "=" * 60)
    print("🏢 CLIENTE MATÍAS - VERSIÓN CABA")
    print("=" * 60)
    print(f"📡 API Dragonfish: {config_caba.DRAGONFISH_BASE_URL}")
    print(f"🗄️ SQL Server: {config_caba.SQL_SERVER}")
    print(f"📊 Base de datos: {config_caba.DATABASE_NAME}")
    print(f"🏷️ Filtros: {', '.join(config_caba.KEYWORDS_NOTE_CABA)}")
    print(f"🏪 Depósito: {config_caba.DEPOSITO_DISPLAY_NAME}")
    print("=" * 60)
    print("🚀 Iniciando aplicación...")
    print()

def main():
    """Función principal para lanzar la aplicación CABA."""
    try:
        # Mostrar información de inicio
        show_startup_info()
        
        # Verificar dependencias
        if not test_dependencies():
            print("❌ Error: Dependencias faltantes. Instale los paquetes requeridos.")
            input("Presione Enter para salir...")
            return 1
        
        # Probar conexiones (no bloqueante)
        connections_ok = test_connections()
        if not connections_ok:
            print("⚠️ Advertencia: Algunas conexiones remotas fallaron.")
            print("   La aplicación iniciará pero algunas funciones pueden no funcionar.")
            print("   Verifique la conectividad de red y configuración.")
        
        # Importar y lanzar GUI
        print("🎨 Iniciando interfaz gráfica CABA...")
        from gui.app_gui_v3_caba import launch_gui_v3_caba
        
        # Lanzar aplicación
        launch_gui_v3_caba()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ Aplicación interrumpida por el usuario")
        return 1
        
    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("   Verifique que todos los archivos estén presentes.")
        traceback.print_exc()
        try:
            input("Presione Enter para salir...")
        except:
            time.sleep(5)  # Esperar 5 segundos si input() falla
        return 1
        
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        traceback.print_exc()
        try:
            input("Presione Enter para salir...")
        except:
            time.sleep(5)  # Esperar 5 segundos si input() falla
        return 1

def show_help():
    """Muestra ayuda de la aplicación."""
    help_text = """
CLIENTE MATÍAS - VERSIÓN CABA
=============================

USO:
    python main_caba.py          - Iniciar aplicación normal
    python main_caba.py --help   - Mostrar esta ayuda
    python main_caba.py --test   - Solo probar conexiones
    python main_caba.py --info   - Mostrar información de configuración

CONFIGURACIÓN CABA:
    • API Dragonfish: http://190.211.201.217:8009/api.Dragonfish
    • SQL Server: DESKTOP-CK25NCF\\ZOOLOGIC
    • Base de datos: DRAGONFISH_MUNDOCAB
    • Filtros: CAB, CABA, MUNDOCAB

REQUISITOS:
    • Python 3.8+
    • Conexión a internet (para API remota)
    • Acceso a red local (para SQL Server)
    • Dependencias: tkinter, ttkbootstrap, requests, pyodbc, reportlab

SOPORTE:
    Para problemas de configuración o conectividad, contacte al administrador.
    """
    print(help_text)

if __name__ == "__main__":
    try:
        # Manejar argumentos de línea de comandos
        if len(sys.argv) > 1:
            arg = sys.argv[1].lower()
            
            if arg in ['--help', '-h', 'help']:
                show_help()
                sys.exit(0)
                
            elif arg in ['--test', '-t', 'test']:
                print("🔧 Modo de prueba - Solo probando conexiones...")
                setup_logging()
                if test_connections():
                    print("✅ Todas las conexiones OK")
                    sys.exit(0)
                else:
                    print("❌ Algunas conexiones fallaron")
                    sys.exit(1)
                    
            elif arg in ['--info', '-i', 'info']:
                show_startup_info()
                print("ℹ️ Información mostrada. Use 'python main_caba.py' para iniciar la aplicación.")
                sys.exit(0)
                
            else:
                print(f"❌ Argumento desconocido: {arg}")
                print("Use 'python main_caba.py --help' para ver opciones disponibles.")
                sys.exit(1)
        
        # Ejecutar aplicación normal
        exit_code = main()
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"❌ Error crítico en main: {e}")
        traceback.print_exc()
        try:
            input("Presione Enter para salir...")
        except:
            time.sleep(5)
        sys.exit(1)
