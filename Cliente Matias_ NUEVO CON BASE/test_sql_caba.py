#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de prueba para verificar la conexión SQL CABA.
"""

import sys
import os

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar configuración CABA ANTES que cualquier otra cosa
print("🔧 Aplicando configuración CABA...")
import config_override_caba

def test_sql_connection():
    """Prueba la conexión SQL usando la configuración CABA."""
    
    print("\n🔍 PROBANDO CONEXIÓN SQL CABA")
    print("=" * 40)
    
    # Mostrar configuración que se va a usar
    sql_conn_str = os.environ.get('SQL_CONN_STR', 'NO CONFIGURADO')
    print(f"🔗 String de conexión: {sql_conn_str}")
    
    try:
        import pyodbc
        print("✅ pyodbc importado correctamente")
        
        print("🔌 Intentando conectar...")
        conn = pyodbc.connect(sql_conn_str)
        print("✅ Conexión establecida")
        
        cursor = conn.cursor()
        print("✅ Cursor creado")
        
        print("📊 Ejecutando consulta de prueba...")
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"✅ Consulta exitosa: {result}")
        
        # Probar consulta a una tabla específica
        print("📋 Probando consulta a tabla de artículos...")
        cursor.execute("SELECT TOP 1 * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
        table_info = cursor.fetchone()
        if table_info:
            print(f"✅ Base de datos accesible. Primera tabla: {table_info[2]}")
        else:
            print("⚠️ No se encontraron tablas")
        
        cursor.close()
        conn.close()
        print("✅ Conexión cerrada correctamente")
        
        return True
        
    except ImportError as e:
        print(f"❌ Error importando pyodbc: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Error de conexión SQL: {e}")
        print("\n🔧 POSIBLES SOLUCIONES:")
        print("1. Verificar que el servidor SQL esté accesible desde esta red")
        print("2. Verificar que el nombre del servidor sea correcto")
        print("3. Verificar que la base de datos exista")
        print("4. Verificar permisos de acceso")
        print("5. Verificar que SQL Server permita conexiones remotas")
        return False

def test_api_connection():
    """Prueba la conexión a la API Dragonfish."""
    
    print("\n🌐 PROBANDO CONEXIÓN API DRAGONFISH")
    print("=" * 40)
    
    api_url = os.environ.get('DRAGONFISH_BASE_URL', 'NO CONFIGURADO')
    print(f"📡 URL API: {api_url}")
    
    try:
        import requests
        print("✅ requests importado correctamente")
        
        # Probar conexión básica
        test_url = f"{api_url}/health"
        print(f"🔌 Probando: {test_url}")
        
        response = requests.get(test_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ API responde correctamente")
            return True
        else:
            print(f"⚠️ API responde con código: {response.status_code}")
            return False
            
    except ImportError as e:
        print(f"❌ Error importando requests: {e}")
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión API: {e}")
        print("\n🔧 POSIBLES SOLUCIONES:")
        print("1. Verificar conexión a internet")
        print("2. Verificar que la IP sea accesible desde esta red")
        print("3. Verificar firewall/proxy")
        return False

def main():
    """Función principal de prueba."""
    
    print("🏢 PRUEBA DE CONFIGURACIÓN CABA")
    print("=" * 50)
    
    # Mostrar configuración aplicada
    print("\n📋 CONFIGURACIÓN DETECTADA:")
    print(f"📡 API Dragonfish: {os.environ.get('DRAGONFISH_BASE_URL', 'NO CONFIGURADO')}")
    print(f"🗄️ SQL Server: {os.environ.get('SQL_SERVER', 'NO CONFIGURADO')}")
    print(f"📊 Base de datos: {os.environ.get('DATABASE_NAME', 'NO CONFIGURADO')}")
    print(f"🏦 Depósito: {os.environ.get('DEPOSITO_NAME', 'NO CONFIGURADO')}")
    print(f"🏷️ Filtros: {config_override_caba.KEYWORDS_NOTE_CABA}")
    
    # Probar conexiones
    sql_ok = test_sql_connection()
    api_ok = test_api_connection()
    
    # Resumen final
    print("\n📊 RESUMEN DE PRUEBAS")
    print("=" * 30)
    print(f"🗄️ SQL Server: {'✅ OK' if sql_ok else '❌ FALLO'}")
    print(f"📡 API Dragonfish: {'✅ OK' if api_ok else '❌ FALLO'}")
    
    if sql_ok and api_ok:
        print("\n🎉 ¡TODAS LAS CONEXIONES OK!")
        print("✅ La configuración CABA está lista para usar")
    else:
        print("\n⚠️ ALGUNAS CONEXIONES FALLARON")
        print("❌ Revise la configuración antes de usar la aplicación")
    
    return sql_ok and api_ok

if __name__ == "__main__":
    try:
        success = main()
        print(f"\n{'✅ ÉXITO' if success else '❌ FALLO'}")
        input("\nPresione Enter para salir...")
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️ Prueba cancelada")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        input("\nPresione Enter para salir...")
        sys.exit(1)
