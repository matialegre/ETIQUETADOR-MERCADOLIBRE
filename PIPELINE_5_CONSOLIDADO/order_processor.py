"""
PROCESADOR DE ÓRDENES REALES
============================

Extrae y procesa datos de órdenes reales de MercadoLibre.
"""

from datetime import datetime
from typing import Dict, Optional
import sys
import os

# Import para búsqueda de barcode
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'modules'))

try:
    # Intentar importar el módulo de barcode
    import importlib.util
    module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'modules', '02_dragon_db.py')
    spec = importlib.util.spec_from_file_location("dragon_db", module_path)
    dragon_db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dragon_db)
    get_barcode_with_fallback = dragon_db.get_barcode_with_fallback
    print(f"✅ Módulo de barcode cargado correctamente")
except Exception as e:
    print(f"⚠️ Error cargando módulo de barcode: {e}")
    # Fallback si no se puede importar
    def get_barcode_with_fallback(seller_custom_field, seller_sku):
        print(f"⚠️ Módulo de barcode no disponible")
        return None

def extract_seller_sku_from_item(item_data: dict) -> Optional[str]:
    """
    Extrae SELLER_SKU del item de MercadoLibre.
    
    Args:
        item_data: Datos del item de MercadoLibre
        
    Returns:
        SELLER_SKU o None si no se encuentra
    """
    
    try:
        # MÉTODO 1: Buscar directamente en seller_sku (más común)
        seller_sku = item_data.get('seller_sku')
        if seller_sku and seller_sku.strip():
            print(f"   🎯 SELLER_SKU encontrado directamente: {seller_sku}")
            return seller_sku.strip()
        
        # MÉTODO 2: Buscar en variation_attributes
        variation_attributes = item_data.get('variation_attributes', [])
        for attr in variation_attributes:
            if attr.get('id') == 'SELLER_SKU':
                seller_sku = attr.get('value_name')
                if seller_sku and seller_sku.strip():
                    print(f"   🎯 SELLER_SKU encontrado en variation_attributes: {seller_sku}")
                    return seller_sku.strip()
        
        # MÉTODO 3: Buscar en variations
        variations = item_data.get('variations', [])
        for variation in variations:
            attributes = variation.get('attributes', [])
            for attr in attributes:
                if attr.get('id') == 'SELLER_SKU':
                    seller_sku = attr.get('value_name')
                    if seller_sku and seller_sku.strip():
                        print(f"   🎯 SELLER_SKU encontrado en variations: {seller_sku}")
                        return seller_sku.strip()
        
        # MÉTODO 4: Buscar en attributes principales
        attributes = item_data.get('attributes', [])
        for attr in attributes:
            if attr.get('id') == 'SELLER_SKU':
                seller_sku = attr.get('value_name')
                if seller_sku and seller_sku.strip():
                    print(f"   🎯 SELLER_SKU encontrado en attributes: {seller_sku}")
                    return seller_sku.strip()
        
        print(f"   ⚠️ SELLER_SKU no encontrado en ninguna ubicación")
        return None
        
    except Exception as e:
        print(f"❌ Error extrayendo SELLER_SKU: {e}")
        return None

def determine_shipping_estado(order: dict, shipping: dict, shipping_status: str, shipping_substatus: str, status: str, substatus: str) -> str:
    """
    Determina el estado de shipping usando la lógica que funcionaba en VERSION 2.
    
    Args:
        order: Orden completa
        shipping: Datos de shipping
        shipping_status: Estado de shipping
        shipping_substatus: Subestado de shipping
        status: Estado general
        substatus: Subestado general
        
    Returns:
        Estado de shipping determinado
    """
    
    try:
        # Analizar tags para determinar estado de impresión
        tags_list = order.get('tags', [])
        
        print(f"   🏷️ Tags disponibles: {tags_list}")
        print(f"   📊 Status: {status}, Substatus: {substatus}")
        print(f"   📦 Shipping status: {shipping_status}, substatus: {shipping_substatus}")
        
        # LÓGICA ADAPTADA para usar tags reales disponibles
        
        # 1. Estados específicos de shipping (si los hubiera)
        if shipping_substatus == 'ready_to_print' or shipping_status == 'ready_to_print':
            print(f"   ✅ Estado desde shipping API: ready_to_print")
            return 'ready_to_print'
        elif shipping_substatus == 'printed' or shipping_status == 'printed':
            print(f"   ✅ Estado desde shipping API: printed")
            return 'printed'
        elif shipping_status in ['shipped', 'delivered']:
            print(f"   ✅ Estado desde shipping API: {shipping_status}")
            return shipping_status
        
        # 2. Usar tags específicos si existen
        if 'ready_to_print' in tags_list:
            print(f"   ✅ Estado desde tag: ready_to_print")
            return 'ready_to_print'
        elif 'printed' in tags_list:
            print(f"   ✅ Estado desde tag: printed")
            return 'printed'
        elif 'shipped' in tags_list:
            print(f"   ✅ Estado desde tag: shipped")
            return 'shipped'
        
        # 3. LÓGICA INFERIDA desde tags disponibles
        if status == 'paid' and 'not_delivered' in tags_list:
            # Orden pagada pero no entregada = probablemente ready_to_print
            print(f"   🎯 Estado inferido: ready_to_print (paid + not_delivered)")
            return 'ready_to_print'
        elif 'delivered' in tags_list:
            print(f"   ✅ Estado desde tag: delivered")
            return 'delivered'
        elif 'cancelled' in tags_list or status == 'cancelled':
            print(f"   ❌ Estado: cancelled")
            return 'cancelled'
        
        # Estados específicos de shipping
        if shipping_substatus in ['shipped', 'delivered']:
            return shipping_substatus
        elif shipping_status in ['shipped', 'delivered']:
            return shipping_status
        
        # Estados generales
        if substatus in ['ready_to_print', 'printed', 'shipped', 'delivered']:
            return substatus
        
        # Mapear estados comunes
        if status == 'paid':
            return 'paid'
        elif status == 'cancelled':
            return 'cancelled'
        elif status == 'confirmed':
            return 'confirmed'
        
        # Fallback: usar status o 'unknown'
        return status if status else 'unknown'
        
    except Exception as e:
        print(f"❌ Error determinando shipping_estado: {e}")
        return status if status else 'unknown'

def extract_order_data(order: dict, meli_client=None) -> Optional[Dict]:
    """
    Extrae datos relevantes de una orden de MercadoLibre con estados reales de shipping.
    
    Args:
        order: Orden raw de MercadoLibre API
        meli_client: Cliente MercadoLibre para consultas adicionales
        
    Returns:
        Dict con datos procesados o None si hay error
    """
    
    try:
        # Datos básicos
        order_id = order.get('id')
        if not order_id:
            return None
        
        # Estado y subestado
        status = order.get('status', 'unknown')
        substatus = order.get('substatus', 'unknown')
        
        # Shipping info básico
        shipping = order.get('shipping', {})
        shipping_id = shipping.get('id')
        shipping_status = shipping.get('status', 'unknown')
        shipping_substatus = shipping.get('substatus', 'unknown')
        
        # 🔥 OBTENER ESTADOS REALES DE SHIPPING VÍA API
        if meli_client and shipping_id and shipping_id != 'unknown':
            try:
                print(f"🚚 Consultando estados reales de shipping para {shipping_id}...")
                real_shipping = meli_client.get_shipping_details(shipping_id)
                if 'error' not in real_shipping:
                    shipping_status = real_shipping.get('status', shipping_status)
                    shipping_substatus = real_shipping.get('substatus', shipping_substatus)
                    print(f"✅ Estados reales obtenidos: {shipping_status}/{shipping_substatus}")
                else:
                    print(f"⚠️ No se pudieron obtener estados reales: {real_shipping.get('error')}")
            except Exception as e:
                print(f"⚠️ Error consultando shipping {shipping_id}: {e}")
        
        # Items
        order_items = order.get('order_items', [])
        
        # Extraer SKUs: seller_custom_field Y seller_sku
        sku = None
        seller_sku = None
        item_id = None
        quantity = 0
        
        if order_items:
            first_item = order_items[0]
            item_data = first_item.get('item', {})
            # Título/nombre de la publicación
            item_title = item_data.get('title') or order.get('title')
            # Si no viene en la orden, consultar /items/{item_id}
            if (not item_title) and meli_client:
                try:
                    iid = item_data.get('id')
                    if iid:
                        resp = meli_client.get_item(iid)
                        if isinstance(resp, dict) and 'error' not in resp:
                            item_title = resp.get('title') or item_title
                            if item_title:
                                print(f"   🏷️ Título obtenido por /items: {item_title}")
                        else:
                            print(f"   ⚠️ No se pudo obtener título por /items: {resp.get('error') if isinstance(resp, dict) else resp}")
                except Exception as e:
                    print(f"   ⚠️ Error consultando /items para título: {e}")
            # Log SIEMPRE visible del título
            print(f"   🏷️ Título publicación: {item_title if item_title else '(sin título)'}")
            
            # Extraer seller_custom_field (PRIORIDAD 1)
            seller_custom_field = item_data.get('seller_custom_field')
            
            # Extraer SELLER_SKU de variations/attributes (FALLBACK)
            extracted_seller_sku = extract_seller_sku_from_item(item_data)
            
            # LÓGICA CORREGIDA: Guardar AMBOS SKUs siempre
            
            # SKU principal (para columna 'sku'): priorizar seller_custom_field
            if seller_custom_field and seller_custom_field.strip() != '':
                # seller_custom_field tiene valor válido - USAR ESTE como principal
                sku = seller_custom_field.strip()
                print(f"   🎯 SKU principal desde seller_custom_field: {sku}")
            elif extracted_seller_sku and extracted_seller_sku.strip() != '':
                # seller_custom_field vacío/null - USAR SELLER_SKU como principal
                sku = extracted_seller_sku.strip()
                print(f"   🔄 SKU principal desde SELLER_SKU (fallback): {sku}")
            else:
                # Ninguno disponible
                sku = 'sin_sku'
                print(f"   ⚠️ Sin SKU disponible - usando: {sku}")
            
            # seller_sku (para columna 'seller_sku'): SIEMPRE el valor de SELLER_SKU
            seller_sku = extracted_seller_sku  # Puede ser None si no existe
            
            # Logs para debug
            print(f"   📊 seller_custom_field: {seller_custom_field}")
            print(f"   📊 seller_sku extraído: {seller_sku}")
            print(f"   🎯 SKU final para búsqueda: {sku}")
                
            item_id = item_data.get('id')
            quantity = first_item.get('quantity', 0)
        
        # Precio
        total_amount = order.get('total_amount', 0)
        
        # Fechas
        date_created = order.get('date_created')
        date_closed = order.get('date_closed')
        
        # Pack info y detección de multiventas
        pack_id = order.get('pack_id')
        multiventa_grupo = None
        is_pack_complete = False
        venta_tipo = 'individual'
        
        # 🔥 DETECTAR Y PROCESAR MULTIVENTAS POR PACK_ID
        if pack_id and meli_client:
            # Defaults to keep logging safe if API fails
            orders_in_pack = []
            is_pack_complete = False
            try:
                print(f"📦 pack_id detectado: {pack_id} → consultando /marketplace/orders/pack/{pack_id}")
                pack_details = meli_client.get_pack_details(pack_id)
                if not pack_details or 'error' in pack_details:
                    # No nos arriesgamos: clasificamos como individual si no podemos confirmar multiventa
                    multiventa_grupo = f"PACK_{pack_id}_ERROR"
                    venta_tipo = 'individual'
                else:
                    orders_in_pack = pack_details.get('orders', []) or pack_details.get('results', []) or []
                    total_in_pack = len(orders_in_pack)
                    is_pack_complete = total_in_pack > 0
                    # Multiventa SOLO si el pack tiene MÁS de 1 orden
                    if total_in_pack > 1:
                        multiventa_grupo = f"PACK_{pack_id}"
                        venta_tipo = 'multiventa'
                        # Si el pack trae shipment.id, usarlo como shipping_id unificado
                        try:
                            pack_shipment = pack_details.get('shipment') or {}
                            pack_ship_id = pack_shipment.get('id')
                            if pack_ship_id:
                                shipping_id = str(pack_ship_id)
                        except Exception:
                            pass
                    else:
                        # Pack con una sola orden → tratar como individual
                        multiventa_grupo = f"PACK_{pack_id}_SINGLE"
                        venta_tipo = 'individual'
                    print(f"📦 Pack consultado: {multiventa_grupo} (orders={total_in_pack}, complete={is_pack_complete})")
                print(f"   📊 Total órdenes en pack: {len(orders_in_pack)}")
                print(f"   ✅ Pack completo: {is_pack_complete}")
            except Exception as e:
                print(f"⚠️ Error procesando pack {pack_id}: {e}")
                # Conservador: individual si falla la consulta
                multiventa_grupo = f"PACK_{pack_id}_ERROR"
                venta_tipo = 'individual'
        elif pack_id:
            # Pack_id existe pero no hay cliente para consultar detalles → conservador: individual
            multiventa_grupo = f"PACK_{pack_id}_BASIC"
            venta_tipo = 'individual'
            print(f"📦 Pack detectado (sin detalles): {multiventa_grupo}")
        else:
            # Sin pack_id desde ML: asignar el mismo valor que order_id (solicitud del usuario)
            pack_id = order_id
            multiventa_grupo = None
            venta_tipo = 'individual'
        
        # Determinar shipping_estado basado en múltiples fuentes
        shipping_estado = determine_shipping_estado(order, shipping, shipping_status, shipping_substatus, status, substatus)
        
        # Determinar color de display
        display_color = get_display_color(shipping_estado, status)
        
        # Normalizar seller_custom_field para búsqueda de barcode (e.g. "466-I--" -> "466-I")
        def _normalize_scf_for_barcode(s: Optional[str]) -> Optional[str]:
            try:
                if not s:
                    return s
                parts = [p for p in str(s).strip().split('-') if p != '']
                return '-'.join(parts) if parts else s
            except Exception:
                return s
        normalized_scf = _normalize_scf_for_barcode(seller_custom_field)

        # Hardcodes de barcode solicitados (aplica antes de consultar DB)
        barcode = None
        try:
            if normalized_scf:
                if normalized_scf in ("466-I", "466-I-"):
                    barcode = "466-I-"
                    print(f"   🔧 Hardcode BARCODE aplicado: {normalized_scf} -> {barcode}")
                elif normalized_scf == "TDRK20-15":
                    barcode = "TDRK20-15"
                    print(f"   🔧 Hardcode BARCODE aplicado: {normalized_scf} -> {barcode}")
                elif normalized_scf in ("201-HF500", "201-HF500-"):
                    barcode = "201-HF500"
                    print(f"   🔧 Hardcode BARCODE aplicado: {normalized_scf} -> {barcode}")
        except Exception:
            pass

        # Si no hay hardcode, usar la lógica de fallback (DB)
        if not barcode:
            print(f"   🔍 Buscando barcode para seller_custom_field(normalizado): {normalized_scf}, seller_sku: {seller_sku}")
            barcode = get_barcode_with_fallback(normalized_scf, seller_sku)
        if barcode:
            print(f"   ✅ BARCODE ENCONTRADO: {barcode}")
        else:
            print(f"   ❌ BARCODE NO ENCONTRADO")
        
        # Parsear ARTICULO-COLOR-TALLE desde SKU (formato esperado ART-COLOR-TALLE)
        def parse_sku_parts(s: Optional[str]):
            try:
                if not s:
                    return None, None, None
                parts = s.strip().split('-')
                if len(parts) >= 3:
                    return parts[0], parts[1], parts[2]
                # Algunos SKU vienen sin guiones, intentar por patrones conocidos (no agresivo)
                return parts[0], None, None
            except Exception:
                return None, None, None

        articulo, color, talle = parse_sku_parts(sku)

        # Intentar extraer atributos reales desde la API de Items (prioritario sobre parseo)
        try:
            if meli_client and item_id:
                item_details = meli_client.get_item_details(item_id)
                if isinstance(item_details, dict) and 'error' not in item_details:
                    # Buscar atributos a nivel item
                    attrs = item_details.get('attributes', []) or []
                    def _find_attr(keys: list[str]) -> Optional[str]:
                        for a in attrs:
                            if not isinstance(a, dict):
                                continue
                            aid = str(a.get('id', '')).upper()
                            aname = str(a.get('name', '')).upper()
                            val = a.get('value_name') or a.get('value_id') or a.get('value')
                            if any(k in (aid, aname) for k in keys):
                                return str(val) if val is not None else None
                        return None
                    # Heurísticas comunes en ML
                    color_attr = _find_attr(['COLOR', 'COLOR PRIMARIO', 'COLOUR'])
                    talle_attr = _find_attr(['SIZE', 'TALLE', 'TALLA', 'NUMERACIÓN'])
                    # ARTICULO: usar la parte base del SKU si no hay atributo específico
                    articulo_attr = _find_attr(['SKU', 'SELLER_SKU', 'MODELO', 'MODEL'])

                    # Si hay variaciones, intentar extraer color/talle de la variación usada
                    variation_id = None
                    try:
                        # Algunas órdenes traen variation_id en order_items[0].item.variation_id
                        variation_id = first_item.get('item', {}).get('variation_id')
                    except Exception:
                        variation_id = None
                    if variation_id and 'variations' in item_details:
                        for var in item_details.get('variations', []) or []:
                            if str(var.get('id')) == str(variation_id):
                                for va in var.get('attribute_combinations', []) or []:
                                    vname = str(va.get('name', '')).upper()
                                    vval = va.get('value_name') or va.get('value_id') or va.get('value')
                                    if 'COLOR' in vname and vval:
                                        color_attr = str(vval)
                                    if (vname in ('TALLE', 'TALLA', 'SIZE') or 'TALLE' in vname or 'SIZE' in vname) and vval:
                                        talle_attr = str(vval)
                                break

                    # Asignar si se obtuvieron
                    if articulo_attr:
                        # Normalizar a primera parte si viene completo tipo ART-COLOR-TALLE
                        articulo = articulo_attr.split('-')[0].strip() if articulo_attr else articulo
                    if color_attr:
                        color = color_attr.strip()
                    if talle_attr:
                        talle = str(talle_attr).strip()

                    print(f"   🧩 Atributos ML → articulo={articulo}, color={color}, talle={talle}")
        except Exception as _e:
            print(f"⚠️ No se pudieron extraer atributos avanzados del item {item_id}: {_e}")

        # Construir datos procesados
        # Normalizar tipos numéricos
        try:
            quantity = int(quantity or 0)
        except Exception:
            quantity = 0
        try:
            total_amount = float(total_amount or 0)
        except Exception:
            total_amount = 0.0

        # Intentar castear pack_id a int si viene string numérica
        if pack_id is not None:
            try:
                pack_id = int(pack_id)
            except Exception:
                pass

        processed_data = {
            'order_id': str(order_id),
            'sku': sku or 'sin_sku',
            'seller_sku': seller_sku,  # Nueva columna para SELLER_SKU
            'barcode': barcode,  # NUEVO: Código de barra encontrado
            'item_id': item_id,
            'pack_id': pack_id,
            'multiventa_grupo': multiventa_grupo,  # NUEVO: Grupo de multiventa
            'is_pack_complete': is_pack_complete,  # NUEVO: Flag de pack completo
            'quantity': quantity,
            'total_amount': total_amount,
            'status': status,
            'substatus': substatus,
            'shipping_id': shipping_id,
            'shipping_estado': shipping_estado,
            'shipping_subestado': shipping_substatus if shipping_substatus else shipping_estado,
            'date_created': date_created,
            'date_closed': date_closed,
            'display_color': display_color,
            'nombre': item_title,
            'asignado_flag': False,  # Por defecto no asignado
            'movimiento_realizado': 0,  # Por defecto no realizado
            'fecha_actualizacion': datetime.now().isoformat(),
            'articulo': articulo,
            'color': color,
            'talle': talle,
            'venta_tipo': venta_tipo,
            # Identificador de cuenta ML (seller user_id) para la columna MELI
            'meli_user_id': (getattr(meli_client, 'user_id', None) if meli_client else None),
        }
        
        return processed_data
        
    except Exception as e:
        print(f"❌ Error extrayendo datos de orden: {e}")
        return None

def get_display_color(shipping_estado: str, status: str) -> str:
    """
    Determina el color de display basado en el estado.
    
    Args:
        shipping_estado: Estado de shipping
        status: Estado general
        
    Returns:
        Color para display
    """
    
    color_map = {
        'ready_to_print': 'yellow',
        'printed': 'blue',
        'shipped': 'green',
        'delivered': 'gray',
        'cancelled': 'red',
        'paid': 'lightblue'
    }
    
    # Priorizar shipping_estado
    if shipping_estado in color_map:
        return color_map[shipping_estado]
    
    # Fallback a status
    if status in color_map:
        return color_map[status]
    
    # Default
    return 'white'
