from flask import Flask, request, jsonify
import json, os, datetime, traceback, sys, time, re
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Configuración básica
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
SYNC_PROCESSING = (os.getenv("SYNC_PROCESSING", "true").lower() in ["1", "true", "yes"])  # espera por defecto

def log(msg, level="INFO"):
    """Función simple de logging"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", file=sys.stderr)

# Asegurar que el directorio de logs existe
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    log(f"Directorio de logs: {LOG_DIR}")
except Exception as e:
    log(f"No se pudo crear el directorio de logs: {e}", "ERROR")
    sys.exit(1)

@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

@app.route("/meli/oauth/callback", methods=["GET", "POST"])
def oauth_callback():
    """Callback de OAuth (dummy): solo registra y responde 200 para evitar 404."""
    try:
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")
        body_json = request.get_json(silent=True)
        payload = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "method": request.method,
            "headers": dict(request.headers),
            "args": request.args.to_dict(flat=True),
            "json": body_json,
            "data": request.get_data(as_text=True),
        }
        topic_dir = os.path.join(LOG_DIR, "oauth")
        os.makedirs(topic_dir, exist_ok=True)
        log_file = os.path.join(topic_dir, f"{timestamp}.json")
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        log(f"OAuth callback recibido y guardado en {log_file}")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        log(f"Error en oauth_callback: {e}", "ERROR")
        traceback.print_exc()
        return jsonify({"error": "OAuth callback error"}), 500

@app.route("/meli/callback", methods=["POST"])
def callback():
    """Endpoint para recibir webhooks de Mercado Libre"""
    try:
        # 1. Obtener timestamp seguro para el nombre del archivo
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")
        
        # 2. Recopilar datos de la petición
        body_json = request.get_json(silent=True)
        request_data = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "headers": dict(request.headers),
            "args": request.args.to_dict(flat=True),
            "json": body_json,
            "data": request.get_data(as_text=True),
        }

        # 3. Adaptación a payloads de Mercado Libre (topic/resource)
        topic = None
        resource = None
        user_id = None
        application_id = None
        if isinstance(body_json, dict):
            topic = body_json.get("topic")
            resource = body_json.get("resource")
            user_id = body_json.get("user_id")
            application_id = body_json.get("application_id")

        # 3.1 Mensaje de depuración en consola con JSON bonito
        kind = None
        if topic == "orders_v2":
            kind = "ORDER"
        elif topic == "shipments":
            kind = "SHIPMENT"
        else:
            kind = "UNKNOWN"

        log(f"=== ML {kind} RECEIVED ===")
        log(f"topic={topic} resource={resource} user_id={user_id}")
        try:
            pretty = json.dumps(body_json, ensure_ascii=False, indent=2)
        except Exception:
            pretty = str(body_json)
        # Imprimir el JSON del webhook para debug
        print(pretty, file=sys.stderr)
        
        # 4. Respuesta amigable (siempre 200)
        ack = {
            "status": "ok",
            "topic": topic,
            "resource": resource,
            "user_id": user_id,
            "application_id": application_id,
        }
        
        # 5. Guardar en archivo (no bloquear la respuesta si falla)
        try:
            # Guardar por carpeta según topic para más orden
            topic_dir = os.path.join(LOG_DIR, topic or "unknown")
            os.makedirs(topic_dir, exist_ok=True)
            log_file = os.path.join(topic_dir, f"{timestamp}.json")
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump({"request": request_data, "ack": ack}, f, ensure_ascii=False, indent=2)
            log(f"Webhook recibido y guardado en {log_file}")
        except Exception as fe:
            log(f"No se pudo escribir el archivo de log: {fe}", "ERROR")
            traceback.print_exc()
        
        # 6. Procesamiento: síncrono (espera) u asíncrono
        if SYNC_PROCESSING:
            proc_result = _process_sync_with_retries(topic, resource, body_json)
            ack["processing"] = proc_result
            return jsonify(ack), 200
        else:
            try:
                submit_background_processing(topic, resource, body_json)
            except Exception as be:
                log(f"No se pudo encolar background job: {be}", "ERROR")
                traceback.print_exc()
            return jsonify(ack), 200
        
    except Exception as e:
        error_msg = f"Error procesando webhook: {str(e)}"
        log(error_msg, "ERROR")
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor"}), 500

###########################
# Procesamiento en background
###########################

# Un pool simple para tareas asíncronas
EXECUTOR = ThreadPoolExecutor(max_workers=4)

def submit_background_processing(topic: str, resource: str, payload: dict):
    """Envía una tarea al pool con reintentos"""
    EXECUTOR.submit(_process_with_retries, topic, resource, payload)

def _process_with_retries(topic: str, resource: str, payload: dict, max_retries: int = 3):
    for attempt in range(1, max_retries + 1):
        try:
            _process_event(topic, resource, payload)
            log(f"Background OK (intent {attempt}) topic={topic} resource={resource}")
            return
        except NonRetriableError as e:
            log(f"No-retry error: {e}", "ERROR")
            _write_error_log(topic, resource, payload, e, attempt, retriable=False)
            return
        except Exception as e:
            log(f"Error intento {attempt}/{max_retries}: {e}", "ERROR")
            traceback.print_exc()
            _write_error_log(topic, resource, payload, e, attempt, retriable=True)
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # backoff exponencial
            else:
                log("Max reintentos alcanzado", "ERROR")

class NonRetriableError(Exception):
    pass

def _process_event(topic: str, resource: str, payload: dict):
    """Procesa orders_v2/shipments y arma estructura MovimientoDetalle con Articulo/Color/Talle.
    No bloquea respuesta; solo loguea y guarda archivos para debug.
    """

    # Extraer ID desde resource, p.ej. "/orders/2000012722971284" o "/shipments/45367316224"
    res_id = _extract_id_from_resource(resource)
    if not res_id:
        raise NonRetriableError(f"No pude extraer ID de resource: {resource}")

    # Intentar enriquecer desde Mercado Libre si hay token
    token = os.getenv("ML_ACCESS_TOKEN")
    details = None
    if token:
        try:
            details = _fetch_ml_details(topic, res_id, token)
        except NonRetriableError:
            raise
        except Exception as e:
            # Podría ser transitorio; permitimos retry
            raise e
    else:
        log("ML_ACCESS_TOKEN no configurado; se omite enriquecimiento ML", "ERROR")

    # Construir campos Articulo/Color/Talle si es posible
    movimiento = _build_movimiento_stub()
    if details:
        try:
            _fill_articulo_color_talle(movimiento, details, topic)
        except Exception as e:
            # No crítico: log y continuar
            log(f"No se pudo extraer Articulo/Color/Talle: {e}", "ERROR")

    # Guardar un archivo de salida de debug con el movimiento armado
    out_dir = os.path.join(LOG_DIR, "processed", topic or "unknown")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")
    out_path = os.path.join(out_dir, f"{ts}-{res_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "resource": resource,
            "id": res_id,
            "topic": topic,
            "payload": payload,
            "enriched_movimiento": movimiento,
            "fetched_details": details,
        }, f, ensure_ascii=False, indent=2)
    log(f"Movimiento enriquecido guardado en {out_path}")

def _extract_id_from_resource(resource: str) -> str:
    if not resource:
        return ""
    m = re.search(r"/(\d+)$", str(resource))
    return m.group(1) if m else ""

def _fetch_ml_details(topic: str, res_id: str, token: str):
    """Obtiene detalles desde la API de ML.
    Nota: import lazy de requests para no romper si no está instalado.
    """
    try:
        import requests  # lazy import
    except Exception:
        raise NonRetriableError("Falta instalar 'requests' (pip install requests)")

    headers = {"Authorization": f"Bearer {token}"}

    if topic == "orders_v2":
        url = f"https://api.mercadolibre.com/orders/{res_id}"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 401:
            raise NonRetriableError("Token inválido o expirado (401)")
        r.raise_for_status()
        order = r.json()
        # Enriquecer con item y variación
        try:
            enriched_items = []
            for it in order.get("order_items", []):
                item_id = (it.get("item") or {}).get("id")
                variation_id = (it.get("item") or {}).get("variation_id")
                item_data = None
                if item_id:
                    iu = f"https://api.mercadolibre.com/items/{item_id}"
                    ir = requests.get(iu, headers=headers, timeout=15)
                    ir.raise_for_status()
                    item_data = ir.json()
                enriched_items.append({
                    "title": (it.get("item") or {}).get("title"),
                    "item_id": item_id,
                    "variation_id": variation_id,
                    "item": item_data,
                })
            order["enriched_items"] = enriched_items
        except Exception:
            # No crítico, continuar
            pass
        return {"type": "order", "data": order}

    elif topic == "shipments":
        url = f"https://api.mercadolibre.com/shipments/{res_id}"
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 401:
            raise NonRetriableError("Token inválido o expirado (401)")
        r.raise_for_status()
        shipment = r.json()
        return {"type": "shipment", "data": shipment}

    else:
        # Desconocido: no error
        return {"type": "unknown", "data": None}

def _build_movimiento_stub():
    """Crea estructura base del Movimiento con los campos requeridos por tu esquema."""
    return {
        "Codigo": "",
        "OrigenDestino": "",
        "Tipo": 0,
        "Motivo": "",
        "vendedor": "",
        "Remito": "",
        "CompAfec": [],
        "Numero": 0,
        "Fecha": datetime.datetime.utcnow().isoformat(),
        "Observacion": "",
        "MovimientoDetalle": [
            {
                "Codigo": "",
                "Articulo": "",       # a completar
                "ArticuloDetalle": "",
                "Color": "",          # a completar
                "ColorDetalle": "",
                "Talle": "",          # a completar
                "Cantidad": 0,
                "NroItem": 0,
            }
        ],
        "InformacionAdicional": {}
    }

def _fill_articulo_color_talle(movimiento: dict, details: dict, topic: str):
    """Extrae Articulo/Color/Talle desde detalles de ML cuando sea posible.
    Heurística básica para orders_v2 con variaciones.
    """
    det = movimiento["MovimientoDetalle"][0]
    if details.get("type") == "order":
        order = details.get("data") or {}
        it = (order.get("enriched_items") or [{}])[0]
        title = it.get("title") or ""
        det["Articulo"] = title
        item_json = it.get("item") or {}
        # Buscar atributos de variación si existen
        var_id = it.get("variation_id")
        variations = item_json.get("variations") or []
        var = next((v for v in variations if str(v.get("id")) == str(var_id)), None)
        attrs = (var or {}).get("attribute_combinations") or []
        # Fallback a attributes si no hay attribute_combinations
        if not attrs:
            attrs = (var or {}).get("attributes") or []
        # Mapear COLOR / TALLE
        for a in attrs:
            aid = (a.get("id") or a.get("name") or "").upper()
            val = (a.get("value_name") or a.get("value_id") or "")
            if "COLOR" in aid:
                det["Color"] = val
            if "TALLE" in aid or "SIZE" in aid:
                det["Talle"] = val
    elif details.get("type") == "shipment":
        ship = details.get("data") or {}
        det["Articulo"] = ship.get("id") and f"Shipment {ship.get('id')}"
    # Si quedó algo vacío, se puede completar luego desde DB propia

def _write_error_log(topic: str, resource: str, payload: dict, exc: Exception, attempt: int, retriable: bool):
    err_dir = os.path.join(LOG_DIR, "errors", topic or "unknown")
    os.makedirs(err_dir, exist_ok=True)
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")
    path = os.path.join(err_dir, f"{ts}-attempt{attempt}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "topic": topic,
            "resource": resource,
            "attempt": attempt,
            "retriable": retriable,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "payload": payload,
        }, f, ensure_ascii=False, indent=2)
    log(f"Error guardado en {path}", "ERROR")

def _process_sync_with_retries(topic: str, resource: str, payload: dict, max_retries: int = 3):
    """Versión síncrona para usar desde el request: espera a terminar y devuelve resumen."""
    summary = {"ok": False, "attempts": 0, "errors": []}
    for attempt in range(1, max_retries + 1):
        summary["attempts"] = attempt
        try:
            _process_event(topic, resource, payload)
            summary["ok"] = True
            return summary
        except NonRetriableError as e:
            _write_error_log(topic, resource, payload, e, attempt, retriable=False)
            summary["errors"].append(str(e))
            return summary
        except Exception as e:
            traceback.print_exc()
            _write_error_log(topic, resource, payload, e, attempt, retriable=True)
            summary["errors"].append(str(e))
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return summary
