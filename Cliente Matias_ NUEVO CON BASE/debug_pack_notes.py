#!/usr/bin/env python3
"""
Debug específico para el pack 2000008721927913
Consulta directamente las notas de cada orden del pack para ver qué está pasando
"""

import sys
import pathlib
ROOT_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api import ml_api
import requests
import json

def debug_pack_notes():
    """Debug específico para el pack problemático"""
    
    # Obtener token
    print("🔑 Obteniendo access token...")
    try:
        access_token, seller_id = ml_api.refresh_access_token()
        print(f"✅ Token obtenido - Seller ID: {seller_id}")
    except Exception as e:
        print(f"❌ Error obteniendo token: {e}")
        return
    
    pack_id = "2000008721927913"
    print(f"\n🔍 DEBUG DETALLADO PARA PACK {pack_id}")
    print("=" * 60)
    
    # 1. Obtener órdenes del pack
    print(f"1️⃣ Obteniendo órdenes del pack {pack_id}...")
    try:
        pack_order_ids = ml_api.get_pack_orders(pack_id, access_token)
        print(f"   📦 Órdenes encontradas: {pack_order_ids}")
    except Exception as e:
        print(f"   ❌ Error obteniendo órdenes del pack: {e}")
        return
    
    if not pack_order_ids:
        print("   ⚠️ No se encontraron órdenes en el pack")
        return
    
    # 2. Consultar nota del pack directamente
    print(f"\n2️⃣ Consultando nota del pack {pack_id} directamente...")
    try:
        pack_note = ml_api.get_latest_note(pack_id, access_token)
        print(f"   📝 Nota del pack: '{pack_note}'")
    except Exception as e:
        print(f"   ❌ Error obteniendo nota del pack: {e}")
    
    # 3. Consultar nota de cada orden individual
    print(f"\n3️⃣ Consultando notas de cada orden individual...")
    for i, order_id in enumerate(pack_order_ids, 1):
        print(f"   Orden {i}/{len(pack_order_ids)}: {order_id}")
        
        try:
            # Nota individual
            individual_note = ml_api.get_latest_note(order_id, access_token)
            print(f"      📝 Nota individual: '{individual_note}'")
            
            # Detalles de la orden
            order_details = ml_api.get_order_details(order_id, access_token)
            if order_details:
                order_note_field = order_details.get("notes", "")
                print(f"      📋 Campo 'notes' de la orden: '{order_note_field}'")
                
                # Items de la orden
                items = order_details.get("order_items", [])
                print(f"      📦 Artículos en la orden: {len(items)}")
                for j, item in enumerate(items, 1):
                    title = item.get("title", "Sin título")[:50]
                    print(f"         {j}. {title}...")
            else:
                print(f"      ❌ No se pudieron obtener detalles de la orden")
                
        except Exception as e:
            print(f"      ❌ Error consultando orden {order_id}: {e}")
    
    # 4. Consultar endpoint de notas directamente
    print(f"\n4️⃣ Consultando endpoint de notas directamente...")
    for order_id in pack_order_ids:
        print(f"   Consultando /orders/{order_id}/notes...")
        try:
            url = f"https://api.mercadolibre.com/orders/{order_id}/notes"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers, timeout=10)
            
            print(f"      Status: {response.status_code}")
            if response.status_code == 200:
                notes_data = response.json()
                print(f"      Respuesta cruda: {json.dumps(notes_data, indent=2)}")
            else:
                print(f"      Error: {response.text}")
                
        except Exception as e:
            print(f"      ❌ Error en consulta directa: {e}")
    
    print(f"\n" + "=" * 60)
    print("🏁 Debug completado")

if __name__ == "__main__":
    debug_pack_notes()
