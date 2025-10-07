#!/usr/bin/env python3
"""
Script de prueba para movimiento de stock CABA.
Permite probar el movimiento de stock desde MUNDOCAB hacia MELI.

CONFIGURACIÓN CABA:
- Base de datos: MUNDOCAB
- Depósito origen: MUNDOCAB
- Depósito destino: MELI
- API: Dragonfish remota (190.211.201.217:8009)

USO:
python test_stock_movement_caba.py
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Aplicar configuración CABA ANTES de importar otros módulos
import config_override_caba

import requests
import json
from datetime import datetime
from utils.logger import get_logger
from utils import config

log = get_logger(__name__)

class StockMovementTesterCaba:
    """Tester para movimientos de stock en CABA."""
    
    def __init__(self):
        self.api_base = "http://190.211.201.217:8888/api.Dragonfish"
        # Token que funciona en el test online
        self.token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MTc5ODg0ODQsInVzdWFyaW8iOiJhZG1pbiIsInBhc3N3b3JkIjoiMDE5NGRkMGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4MWQwMyJ9.zAWCBxY5smFLyDrNAPqeaaoOJbmG-R-SM7mFFg7MQeE"
        self.deposito_origen = "MUNDOCAB"  # Por defecto CABA
        self.deposito_destino = "MELI"
        
        log.info("🏢 Tester de stock CABA inicializado")
        log.info(f"📡 API: {self.api_base}")
        log.info(f"📦 Movimiento: {self.deposito_origen} → {self.deposito_destino}")
    
    def test_connection(self) -> bool:
        """Prueba la conexión con la API Dragonfish CABA."""
        try:
            url = f"{self.api_base}/docs/"
            log.info(f"🔗 Probando conexión a: {url}")
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                log.info("✅ Conexión exitosa con API Dragonfish CABA")
                return True
            else:
                log.error(f"❌ Error de conexión: {response.status_code}")
                return False
                
        except Exception as e:
            log.error(f"❌ Excepción en conexión: {e}")
            return False
    
    def test_stock_movement(self, sku: str, quantity: int = 1, deposito_origen: str = "MUNDOCAB") -> dict:
        """
        Prueba un movimiento de stock específico.
        
        Args:
            sku: SKU del producto a mover
            quantity: Cantidad a mover (default: 1)
            
        Returns:
            dict: Resultado del movimiento con status y detalles
        """
        log.info(f"🔄 Iniciando movimiento de prueba:")
        log.info(f"   SKU: {sku}")
        log.info(f"   Cantidad: {quantity}")
        log.info(f"   Origen: {deposito_origen}")
        log.info(f"   Destino: {self.deposito_destino}")
        
        try:
            # Preparar datos del movimiento (formato Dragonfish)
            from datetime import timezone, timedelta
            import uuid
            
            # Generar fecha en formato Dragonfish
            zona = timezone(timedelta(hours=-3))
            ms = int(datetime.now(zona).timestamp() * 1000)
            fecha_dragonfish = f"/Date({ms}-0300)/"
            
            # Generar número único incremental (mayor que 91220384)
            base_numero = 91220400  # Base mayor que el último usado
            numero_unico = base_numero + int(str(ms)[-4:])  # Suma últimos 4 dígitos para variación
            
            # Generar código único incremental
            codigo_base = f"PRU{int(str(ms)[-6:])}"
            
            # Formato CABA: invertido (MUNDOCAB como origen, MELI como destino en header)
            if deposito_origen == "MUNDOCAB":
                movement_data = {
                    "OrigenDestino": "MUNDOCAB",  # Origen en el payload
                    "Tipo": 1,  # Entrada (no salida)
                    "Motivo": "API",
                    "vendedor": "API",
                    "Remito": "-",
                    "CompAfec": [],
                    "Fecha": fecha_dragonfish,
                    "Observacion": f"PRUEBA {deposito_origen} - SKU:{sku} - ID:{uuid.uuid4().hex[:8]}",
                    "MovimientoDetalle": [
                        {
                            "Articulo": sku,  # SKU real va en Articulo
                            "ArticuloDetalle": "",
                            "Color": "",
                            "ColorDetalle": "",
                            "Talle": "",
                            "Cantidad": quantity,
                            "NroItem": 1
                        }
                    ],
                    "InformacionAdicional": {
                        "FechaTransferencia": None,
                        "EstadoTransferencia": "",  # Vacío para CABA
                        "FechaAltaFW": None,  # Null para CABA
                        "HoraAltaFW": "",  # Vacío para CABA
                        "FechaModificacionFW": None,  # Null para CABA
                        "HoraModificacionFW": "",  # Vacío para CABA
                        "FechaImpo": None,
                        "HoraImpo": "",
                        "FechaExpo": None,
                        "HoraExpo": "",
                        "UsuarioAltaFW": "",  # Vacío para CABA
                        "UsuarioModificacionFW": "",  # Vacío para CABA
                        "SerieAltaFW": "",  # Vacío para CABA
                        "SerieModificacionFW": "",  # Vacío para CABA
                        "BaseDeDatosAltaFW": "",  # Vacío para CABA
                        "BaseDeDatosModificacionFW": "",  # Vacío para CABA
                        "VersionAltaFW": "",
                        "VersionModificacionFW": "",
                        "ZADSFW": ""
                    }
                }
            else:
                # Formato DEPOSITO: normal
                movement_data = {
                    "Codigo": codigo_base,  # Código único incremental
                    "OrigenDestino": self.deposito_destino,  # MELI
                    "Tipo": 2,
                    "Motivo": "API",
                    "vendedor": "API",
                    "Remito": "-",
                    "CompAfec": [],
                    "Numero": numero_unico,  # Número único incremental
                    "Fecha": fecha_dragonfish,
                    "Observacion": f"PRUEBA {deposito_origen} - SKU:{sku} - ID:{uuid.uuid4().hex[:8]}",
                "MovimientoDetalle": [
                    {
                        "Codigo": "",  # Codigo VACÍO como en la app real
                        "Articulo": sku,  # SKU real va en Articulo
                        "ArticuloDetalle": "",
                        "Color": "",  # Se podría llenar con datos reales
                        "ColorDetalle": "",
                        "Talle": "",  # Se podría llenar con datos reales
                        "Cantidad": quantity,
                        "NroItem": 1
                    }
                ],
                "InformacionAdicional": {
                    "FechaTransferencia": None,
                    "EstadoTransferencia": "PENDIENTE",  # Estado específico como en la app
                    "FechaAltaFW": fecha_dragonfish,  # Fecha real como en la app
                    "HoraAltaFW": datetime.now().strftime("%H:%M:%S"),  # Hora real
                    "FechaModificacionFW": fecha_dragonfish,  # Fecha real
                    "HoraModificacionFW": datetime.now().strftime("%H:%M:%S"),  # Hora real
                    "FechaImpo": None,
                    "HoraImpo": "",
                    "FechaExpo": None,
                    "HoraExpo": "",
                    "UsuarioAltaFW": "API",  # Usuario específico
                    "UsuarioModificacionFW": "API",  # Usuario específico
                    "SerieAltaFW": "901224",  # Serie como en la app
                    "SerieModificacionFW": "901224",  # Serie como en la app
                    "BaseDeDatosAltaFW": "MELI",  # Base específica como en la app
                    "BaseDeDatosModificacionFW": "MELI",  # Base específica como en la app
                    "VersionAltaFW": "",
                    "VersionModificacionFW": "",
                    "ZADSFW": ""
                }
            }
            
            # Headers (formato Dragonfish) - INVERTIDO para CABA
            if deposito_origen == "MUNDOCAB":
                base_datos = "MELI"  # Para CABA: BaseDeDatos es el DESTINO
            else:
                base_datos = "DEPOSITO"  # Para DEPOSITO: BaseDeDatos es el ORIGEN
                
            headers = {
                "accept": "application/json",
                "Authorization": self.token,
                "IdCliente": "PRUEBA-WEB",
                "Content-Type": "application/json",
                "BaseDeDatos": base_datos
            }
            
            # URL del endpoint de movimiento (correcto)
            url = f"{self.api_base}/Movimientodestock/"
            
            log.info(f"📤 Enviando request a: {url}")
            log.info(f"📋 Datos: {json.dumps(movement_data, indent=2)}")
            
            # Realizar el request
            response = requests.post(
                url,
                json=movement_data,
                headers=headers,
                timeout=30
            )
            
            # Procesar respuesta
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 201,  # API devuelve 201 para éxito
                "timestamp": datetime.now().isoformat(),
                "request_data": movement_data,
                "response_headers": dict(response.headers),
                "response_text": response.text
            }
            
            try:
                result["response_json"] = response.json()
            except:
                result["response_json"] = None
            
            # Log del resultado
            if result["success"]:
                log.info("✅ Movimiento exitoso!")
                log.info(f"📊 Respuesta: {response.text}")
            else:
                log.error(f"❌ Error en movimiento: {response.status_code}")
                log.error(f"📊 Respuesta completa: {response.text}")
                log.error(f"📋 Headers de respuesta: {dict(response.headers)}")
                
                # Intentar decodificar la respuesta si es JSON
                try:
                    if response.text:
                        error_json = response.json()
                        log.error(f"🔍 Error JSON: {json.dumps(error_json, indent=2)}")
                except:
                    log.error(f"🔍 Respuesta no es JSON válido: {repr(response.text)}")
            
            return result
            
        except Exception as e:
            log.error(f"❌ Excepción en movimiento: {e}")
            return {
                "status_code": None,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "request_data": movement_data if 'movement_data' in locals() else None
            }
    
    def interactive_test(self):
        """Modo interactivo para probar movimientos."""
        print("\n" + "="*60)
        print("🏢 TESTER DE MOVIMIENTO DE STOCK - COMPARACIÓN")
        print("="*60)
        print(f"📡 API: {self.api_base}")
        print(f"📦 Comparando: DEPOSITO vs MUNDOCAB → MELI")
        print("="*60)
        
        # Probar conexión primero
        print("\n1️⃣ Probando conexión...")
        if not self.test_connection():
            print("❌ No se pudo conectar. Verifica la configuración.")
            return
        
        # Solicitar datos del movimiento
        print("\n2️⃣ Configurando movimiento de prueba...")
        print()
        sku = input("📦 Ingresa el SKU a mover (ej: NEPLA6ABHB): ").strip() or "PRUEBAAPI"
        quantity_input = input("🔢 Cantidad a mover (default: 1): ").strip()
        quantity = int(quantity_input) if quantity_input else 1
        
        # Confirmar movimiento
        print(f"\n📋 RESUMEN DE LA COMPARACIÓN:")
        print(f"   SKU: {sku}")
        print(f"   Cantidad: {quantity}")
        print(f"   Pruebas: DEPOSITO → MELI vs MUNDOCAB → MELI")
        
        confirm = input("\n¿Ejecutar comparación? (s/N): ").strip().lower()
        if confirm not in ['s', 'si', 'sí', 'y', 'yes']:
            print("❌ Comparación cancelada")
            return
        
        # Ejecutar movimientos de ambos depósitos
        print("\n3️⃣ Ejecutando comparación...")
        print("\n🔵 PROBANDO DEPOSITO → MELI:")
        result_deposito = self.test_stock_movement(sku, quantity, "DEPOSITO")
        
        print("\n🟡 PROBANDO MUNDOCAB → MELI:")
        result_mundocab = self.test_stock_movement(sku, quantity, "MUNDOCAB")
        
        # Mostrar comparación detallada
        print("\n" + "="*80)
        print("📊 COMPARACIÓN DE RESULTADOS")
        print("="*80)
        print(f"🔵 DEPOSITO → MELI:")
        print(f"   ✅ Éxito: {'SÍ' if result_deposito['success'] else 'NO'}")
        print(f"   📡 Status Code: {result_deposito['status_code']}")
        print(f"   🕐 Timestamp: {result_deposito['timestamp']}")
        print()
        print(f"🟡 MUNDOCAB → MELI:")
        print(f"   ✅ Éxito: {'SÍ' if result_mundocab['success'] else 'NO'}")
        print(f"   📡 Status Code: {result_mundocab['status_code']}")
        print(f"   🕐 Timestamp: {result_mundocab['timestamp']}")
        print()
        print(f"🎯 CONCLUSIÓN:")
        if result_deposito['success'] and not result_mundocab['success']:
            print("   ✅ DEPOSITO funciona, MUNDOCAB falla - Revisar configuración CABA")
        elif not result_deposito['success'] and result_mundocab['success']:
            print("   ✅ MUNDOCAB funciona, DEPOSITO falla - Problema con DEPOSITO")
        elif result_deposito['success'] and result_mundocab['success']:
            print("   ✅ Ambos funcionan - No hay problema de configuración")
        else:
            print("   ❌ Ambos fallan - Problema general de API o token")
        print("="*80)
    
    def test_caba_depot_names(self, sku="PRUEBAAPI", quantity=1):
        """Prueba diferentes nombres de depósito CABA para encontrar el correcto."""
        print("\n" + "="*80)
        print("🔍 PROBANDO NOMBRES DE DEPÓSITO CABA")
        print("="*80)
        
        # Nombres posibles para CABA
        nombres_caba = [
            "MUNDOCAB",
            "CABA", 
            "CAB",
            "MUNDOCABA",
            "MUNDO_CAB",
            "MUNDO-CAB",
            "DEPOSITO_CABA",
            "DEP_CABA"
        ]
        
        resultados = []
        
        for nombre in nombres_caba:
            print(f"\n🧪 Probando: {nombre} → MELI")
            result = self.test_stock_movement(sku, quantity, nombre)
            resultados.append({
                'nombre': nombre,
                'success': result['success'],
                'status_code': result['status_code']
            })
            
            if result['success']:
                print(f"   ✅ {nombre}: FUNCIONA!")
            else:
                print(f"   ❌ {nombre}: Falla ({result['status_code']})")
        
        # Resumen final
        print("\n" + "="*80)
        print("📊 RESUMEN DE NOMBRES PROBADOS")
        print("="*80)
        
        funcionan = [r for r in resultados if r['success']]
        fallan = [r for r in resultados if not r['success']]
        
        if funcionan:
            print("✅ NOMBRES QUE FUNCIONAN:")
            for r in funcionan:
                print(f"   🟢 {r['nombre']} (Status: {r['status_code']})")
        else:
            print("❌ NINGÚN NOMBRE FUNCIONA")
            
        if fallan:
            print("\n❌ NOMBRES QUE FALLAN:")
            for r in fallan:
                print(f"   🔴 {r['nombre']} (Status: {r['status_code']})")
                
        print("="*80)
        
        return funcionan

def main():
    """Función principal."""
    tester = StockMovementTesterCaba()
    
    print("\n🎯 OPCIONES DE PRUEBA:")
    print("1️⃣ Comparación DEPOSITO vs MUNDOCAB")
    print("2️⃣ Probar diferentes nombres de depósito CABA")
    print("3️⃣ Test individual")
    
    opcion = input("\n¿Qué prueba quieres ejecutar? (1/2/3): ").strip()
    
    if opcion == "2":
        # Probar nombres de depósito CABA
        if not tester.test_connection():
            print("❌ No se pudo conectar. Verifica la configuración.")
            return
        
        sku = input("\n📦 SKU para probar (default: PRUEBAAPI): ").strip() or "PRUEBAAPI"
        tester.test_caba_depot_names(sku)
    elif opcion == "3":
        # Test individual
        if not tester.test_connection():
            print("❌ No se pudo conectar. Verifica la configuración.")
            return
            
        sku = input("\n📦 SKU: ").strip() or "PRUEBAAPI"
        deposito = input("🏢 Depósito origen: ").strip() or "MUNDOCAB"
        result = tester.test_stock_movement(sku, 1, deposito)
        print(f"\n📊 Resultado: {'✅ ÉXITO' if result['success'] else '❌ FALLA'} (Status: {result['status_code']})")
    else:
        # Comparación por defecto
        tester.interactive_test()

if __name__ == "__main__":
    main()
