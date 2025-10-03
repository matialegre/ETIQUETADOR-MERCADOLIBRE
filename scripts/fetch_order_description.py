import argparse
import json
import os
import sys
from typing import Dict, List, Optional, Tuple, Any

import requests
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
DEFAULT_TOKEN_PATH = os.path.join(ROOT, "config", "token.json")


def load_tokens(token_path: Optional[str] = None) -> Tuple[Dict[str, str], List[str]]:
    """
    Lee un archivo de tokens y devuelve (tokens_by_user, tokens).
    Formatos soportados en JSON:
    - {"user_tokens": {"<user_id>": {"access_token": "..."}, ...}}
    - {"<user_id>": {"access_token": "..."}, ...}
    - {"access_token": "...", "user_id": <id_opcional>}
    Si el archivo no existe, intenta ML_ACCESS_TOKEN del entorno.
    """
    tokens: List[str] = []
    tokens_by_user: Dict[str, str] = {}
    path = token_path or DEFAULT_TOKEN_PATH
    if not os.path.isfile(path):
        tok = os.getenv("ML_ACCESS_TOKEN")
        if tok:
            tokens.append(tok)
        return tokens_by_user, tokens
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"No se pudo leer {path}: {e}", file=sys.stderr)
        return tokens_by_user, tokens

    if isinstance(data, dict):
        # 1) Bloque user_tokens
        ut = data.get("user_tokens")
        if isinstance(ut, dict):
            for _uid, obj in ut.items():
                if isinstance(obj, dict):
                    tok = obj.get("access_token")
                    if tok:
                        tokens.append(tok)
                        tokens_by_user[str(_uid)] = tok
        # 2) Mapping directo user_id -> {access_token}
        for k, v in data.items():
            if k == "user_tokens":
                continue
            if isinstance(v, dict):
                tok = v.get("access_token")
                if tok and tok not in tokens:
                    tokens.append(tok)
                    tokens_by_user[str(k)] = tok
        # 3) Token a nivel raíz
        root_tok = data.get("access_token")
        if root_tok and root_tok not in tokens:
            tokens.append(root_tok)
            root_uid = data.get("user_id")
            if root_uid is not None:
                tokens_by_user[str(root_uid)] = root_tok
    return tokens_by_user, tokens

def _collect_date_fields(obj: Any, out: Dict[str, Any], prefix: str = "") -> None:
    try:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}{k}" if prefix else str(k)
                lk = str(k).lower()
                if isinstance(v, (str, int, float)):
                    sv = str(v)
                    if (
                        "date" in lk
                        or "deadline" in lk
                        or "limit" in lk
                        or lk.endswith("_at")
                        or lk.endswith("_by")
                    ):
                        # Guardar candidato
                        out[key] = sv
                elif isinstance(v, (dict, list)):
                    _collect_date_fields(v, out, prefix=key + ".")
        elif isinstance(obj, list):
            for idx, it in enumerate(obj):
                _collect_date_fields(it, out, prefix=f"{prefix}[{idx}].")
    except Exception:
        pass

def _parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Python 3.11+ soporta fromisoformat con offset
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        try:
            # fallback aproximado (sin offset)
            return datetime.fromisoformat(dt_str.split(".")[0])
        except Exception:
            return None

def _weekday_es(dt: datetime) -> str:
    # 0=Lunes ... 6=Domingo
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    try:
        return dias[dt.weekday()]
    except Exception:
        return ""

def _derive_dispatch_by(cand_dates: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Elige una fecha objetivo (ISO) para despacho basándose en lead_time.* de shipment.
    Prioridad: estimated_delivery_limit.date > estimated_delivery_time.date > final > extended.
    Devuelve (dispatch_by_iso, dispatch_by_label_es)
    """
    keys = [
        # Preferir SLA cuando esté disponible
        "sla.expected_date",
        "lead_time.estimated_delivery_limit.date",
        "lead_time.estimated_delivery_time.date",
        "lead_time.estimated_delivery_final.date",
        "lead_time.estimated_delivery_extended.date",
    ]
    pick: Optional[str] = None
    for k in keys:
        if k in cand_dates and cand_dates.get(k):
            pick = str(cand_dates.get(k))
            break
    if not pick:
        return None, None
    dt = _parse_iso(pick)
    if not dt:
        return pick, None
    # Construir etiqueta humana: "Despachar <weekday dd/mm>"
    wd = _weekday_es(dt)
    label = f"Despachar {wd} {dt.day:02d}/{dt.month:02d}"
    return dt.isoformat(), label


def fetch_order(order_id: int, token: str) -> requests.Response:
    url = f"https://api.mercadolibre.com/orders/{order_id}"
    headers = {"Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers, timeout=20)

def fetch_shipment_lead_time(shipment_id: int, token: str) -> requests.Response:
    """Endpoint específico que devuelve solo el bloque lead_time del shipment."""
    url = f"https://api.mercadolibre.com/shipments/{shipment_id}/lead_time"
    headers = {"Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers, timeout=20)

def fetch_shipment(shipment_id: int, token: str, x_format_new: bool = True) -> requests.Response:
    url = f"https://api.mercadolibre.com/shipments/{shipment_id}"
    headers = {"Authorization": f"Bearer {token}"}
    if x_format_new:
        headers["x-format-new"] = "true"
    return requests.get(url, headers=headers, timeout=20)

def fetch_shipment_sla(shipment_id: int, token: str) -> requests.Response:
    url = f"https://api.mercadolibre.com/shipments/{shipment_id}/sla"
    headers = {"Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers, timeout=20)
def _collect_descriptions(obj: Any, out: List[str]) -> None:
    """Recorre un JSON y agrega textos de interés: description, subtitle, title, primaryAction.text."""
    try:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k).lower()
                if key in ("description", "subtitle") and isinstance(v, str):
                    s = v.strip()
                    if s and s not in out:
                        out.append(s)
                if key in ("title",) and isinstance(v, str):
                    s = v.strip()
                    # evitar titulos super genéricos repetidos
                    if s and s.lower() not in ("documentación", "primeros pasos") and s not in out:
                        out.append(s)
                if key == "primaryaction" and isinstance(v, dict):
                    t = v.get("text")
                    if isinstance(t, str):
                        s = t.strip()
                        if s and s not in out:
                            out.append(s)
                _collect_descriptions(v, out)
        elif isinstance(obj, list):
            for it in obj:
                _collect_descriptions(it, out)
    except Exception:
        pass


def _refresh_token_file(path: str) -> Optional[str]:
    """
    Usa refresh_token en el archivo para pedir un nuevo access_token.
    Actualiza el JSON en disco si tiene éxito y devuelve el nuevo access_token.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")
        refresh_tok = data.get("refresh_token")
        if not (client_id and client_secret and refresh_tok):
            print("El archivo de token no tiene client_id/client_secret/refresh_token para refrescar.", file=sys.stderr)
            return None
        resp = requests.post(
            "https://api.mercadolibre.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": str(client_id),
                "client_secret": str(client_secret),
                "refresh_token": str(refresh_tok),
            },
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"Fallo al refrescar token ({resp.status_code}): {resp.text[:300]}", file=sys.stderr)
            return None
        j = resp.json()
        new_access = j.get("access_token")
        new_refresh = j.get("refresh_token") or refresh_tok
        expires_in = j.get("expires_in")
        # Actualizar archivo
        data["access_token"] = new_access
        data["refresh_token"] = new_refresh
        if expires_in is not None:
            data["expires_in"] = expires_in
        # sello de actualización
        try:
            data["created_at"] = int(__import__("time").time())
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✓ access_token refrescado y guardado en archivo.")
        return new_access
    except Exception as e:
        print(f"Error refrescando token: {e}", file=sys.stderr)
        return None

def main():
    ap = argparse.ArgumentParser(description="Fetch ML order and print description field")
    ap.add_argument("--order", type=int, required=True, help="Order ID")
    ap.add_argument("--user-id", type=str, default=None, help="Forzar token del vendedor (user_id) a usar")
    ap.add_argument("--token-file", type=str, default=None, help="Ruta a un token.json específico (p.ej., config/token_02.json)")
    ap.add_argument("--refresh-now", action="store_true", help="Refrescar el token del --token-file antes de llamar")
    ap.add_argument("--only-texts", action="store_true", help="Imprimir solo los textos de UI extraídos (uno por línea)")
    ap.add_argument("--compare-schemas", action="store_true", help="Comparar shipment legacy vs new (x-format-new) y SLA, si hay shipping_id")
    args = ap.parse_args()

    tokens_by_user, tokens = load_tokens(args.token_file)
    if not tokens:
        print("No se encontraron tokens en config/token.json ni ML_ACCESS_TOKEN.", file=sys.stderr)
        sys.exit(2)

    # Si pidieron refrescar explícitamente y tenemos token-file, hacerlo ahora
    if args.refresh_now and args.token_file:
        new_tok = _refresh_token_file(args.token_file)
        if new_tok:
            tokens = [new_tok]
            tokens_by_user = {**tokens_by_user}

    last_error: Optional[str] = None
    # Si especificaron un user_id, priorizar ese token
    if args.user_id:
        tok = tokens_by_user.get(str(args.user_id))
        if not tok:
            print(
                (
                    "No encontré token para user_id={} en config/token.json. Disponible: {}"
                ).format(args.user_id, ",".join(sorted(tokens_by_user.keys())) or "<ninguno>"),
                file=sys.stderr,
            )
            sys.exit(3)
        tokens_to_try = [tok]
    else:
        tokens_to_try = tokens

    tried_refresh = False
    for tok in tokens_to_try:
        try:
            r = fetch_order(args.order, tok)
            if r.status_code == 200:
                j = r.json()
                # Campos útiles
                oid = j.get("id")
                status = j.get("status")
                description = j.get("description")
                date_created = j.get("date_created")
                date_closed = j.get("date_closed")
                shipping = (j.get("shipping") or {}).get("id") if isinstance(j.get("shipping"), dict) else None
                texts: List[str] = []
                _collect_descriptions(j, texts)
                cand_dates: Dict[str, Any] = {}
                _collect_date_fields(j, cand_dates)
                shipment_extra: Dict[str, Any] = {}
                sla_extra: Dict[str, Any] = {}
                if shipping:
                    try:
                        rs = fetch_shipment(int(shipping), tok)
                        if rs.status_code == 200:
                            sj = rs.json()
                            _collect_descriptions(sj, texts)
                            _collect_date_fields(sj, cand_dates)
                            # Extraer campos estándar de estado/envío
                            try:
                                shipment_extra = {
                                    "shipment_status": sj.get("status"),
                                    "shipment_substatus": sj.get("substatus"),
                                    "shipment_logistic_type": sj.get("logistic_type"),
                                    "shipment_shipping_mode": sj.get("shipping_mode"),
                                    "shipment_service_id": sj.get("service_id"),
                                    "shipment_tags": sj.get("tags"),
                                }
                            except Exception:
                                pass
                        # SLA: plazo máximo de despacho
                        try:
                            rsla = fetch_shipment_sla(int(shipping), tok)
                            if rsla.status_code == 200:
                                sj_sla = rsla.json() or {}
                                sla_extra = {
                                    "sla_status": sj_sla.get("status"),
                                    "sla_service": sj_sla.get("service"),
                                    "sla_expected_date": sj_sla.get("expected_date"),
                                    "sla_last_updated": sj_sla.get("last_updated"),
                                }
                                if sj_sla.get("expected_date"):
                                    cand_dates["sla.expected_date"] = sj_sla.get("expected_date")
                        except Exception:
                            pass
                        # LEAD TIME endpoint dedicado
                        try:
                            rlt = fetch_shipment_lead_time(int(shipping), tok)
                            if rlt.status_code == 200:
                                lt = rlt.json() or {}
                                # Unir sus fechas explícitas
                                _collect_date_fields(lt, cand_dates)
                        except Exception:
                            pass
                    except Exception:
                        pass
                # Heurística simple: detectar si los textos mencionan despachar/entregar
                hints: List[str] = []
                for t in texts:
                    lt = t.lower()
                    if "despach" in lt or "entreg" in lt:
                        hints.append(t)
                if args.only_texts:
                    for t in texts:
                        print(t)
                    return
                # Derivar dispatch_by a partir de lead_time
                dispatch_by_iso, dispatch_label = _derive_dispatch_by(cand_dates)
                comparison: Optional[Dict[str, Any]] = None
                if args.compare_schemas and shipping:
                    try:
                        # Legacy (sin x-format-new)
                        r_leg = fetch_shipment(int(shipping), tok, x_format_new=False)
                        legacy = r_leg.json() if r_leg.status_code == 200 else None
                        # New (con x-format-new)
                        r_new = fetch_shipment(int(shipping), tok, x_format_new=True)
                        newj = r_new.json() if r_new.status_code == 200 else None
                        # SLA
                        r_sla = fetch_shipment_sla(int(shipping), tok)
                        sla = r_sla.json() if r_sla.status_code == 200 else None
                        # Lead Time endpoint dedicado
                        r_lt = fetch_shipment_lead_time(int(shipping), tok)
                        ltj = r_lt.json() if r_lt.status_code == 200 else None
                        comparison = {
                            "legacy": {
                                "shipping_option.estimated_delivery_final.date": ((legacy or {}).get("shipping_option") or {}).get("estimated_delivery_final", {}).get("date") if isinstance(legacy, dict) else None,
                                "shipping_option.estimated_delivery_time.date": ((legacy or {}).get("shipping_option") or {}).get("estimated_delivery_time", {}).get("date") if isinstance(legacy, dict) else None,
                                "shipping_option.estimated_delivery_limit.date": ((legacy or {}).get("shipping_option") or {}).get("estimated_delivery_limit", {}).get("date") if isinstance(legacy, dict) else None,
                            },
                            "new": {
                                "lead_time.estimated_delivery_final.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_final") or {}).get("date") if isinstance(newj, dict) else None,
                                "lead_time.estimated_delivery_time.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_time") or {}).get("date") if isinstance(newj, dict) else None,
                                "lead_time.estimated_delivery_limit.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_limit") or {}).get("date") if isinstance(newj, dict) else None,
                                "lead_time.estimated_delivery_extended.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_extended") or {}).get("date") if isinstance(newj, dict) else None,
                            },
                            "sla": {
                                "status": (sla or {}).get("status") if isinstance(sla, dict) else None,
                                "service": (sla or {}).get("service") if isinstance(sla, dict) else None,
                                "expected_date": (sla or {}).get("expected_date") if isinstance(sla, dict) else None,
                                "last_updated": (sla or {}).get("last_updated") if isinstance(sla, dict) else None,
                            },
                            "lead_time_endpoint": {
                                "estimated_delivery_final.date": (((ltj or {}).get("estimated_delivery_final") or {}).get("date") if isinstance(ltj, dict) else None),
                                "estimated_delivery_time.date": (((ltj or {}).get("estimated_delivery_time") or {}).get("date") if isinstance(ltj, dict) else None),
                                "estimated_delivery_limit.date": (((ltj or {}).get("estimated_delivery_limit") or {}).get("date") if isinstance(ltj, dict) else None),
                                "estimated_delivery_extended.date": (((ltj or {}).get("estimated_delivery_extended") or {}).get("date") if isinstance(ltj, dict) else None),
                            },
                        }
                    except Exception:
                        comparison = {"error": "No se pudo comparar schemas"}
                print(json.dumps({
                    "id": oid,
                    "status": status,
                    "description": description,
                    "date_created": date_created,
                    "date_closed": date_closed,
                    "shipping_id": shipping,
                    "ui_texts": texts,
                    "candidate_dates": cand_dates,
                    "dispatch_hints": hints,
                    "dispatch_by": dispatch_by_iso,
                    "dispatch_label": dispatch_label,
                    **({} if not shipment_extra else shipment_extra),
                    **({} if not sla_extra else sla_extra),
                    **({} if comparison is None else {"comparison": comparison}),
                }, ensure_ascii=False, indent=2))
                return
            else:
                # Capturar mensaje de error para diagnóstico
                try:
                    errj = r.json()
                except Exception:
                    errj = None
                if isinstance(errj, dict) and errj.get("error") == "not_owned_order":
                    # Sugerir cambiar de token
                    print(
                        (
                            "403 not_owned_order: el token no pertenece al vendedor de la orden. "
                            "Probá especificar --user-id=<seller_id> de ACC1. Disponibles en token.json: {}"
                        ).format(",".join(sorted(tokens_by_user.keys())) or "<desconocidos>"),
                        file=sys.stderr,
                    )
                # Intentar refresh automático si 401 y tenemos --token-file
                if r.status_code == 401 and args.token_file and not tried_refresh:
                    tried_refresh = True
                    print("Token inválido/expirado. Intentando refresh...", file=sys.stderr)
                    new_tok = _refresh_token_file(args.token_file)
                    if new_tok:
                        r2 = fetch_order(args.order, new_tok)
                        if r2.status_code == 200:
                            j = r2.json()
                            oid = j.get("id")
                            status = j.get("status")
                            description = j.get("description")
                            date_created = j.get("date_created")
                            date_closed = j.get("date_closed")
                            shipping = (j.get("shipping") or {}).get("id") if isinstance(j.get("shipping"), dict) else None
                            texts: List[str] = []
                            _collect_descriptions(j, texts)
                            cand_dates: Dict[str, Any] = {}
                            _collect_date_fields(j, cand_dates)
                            shipment_extra: Dict[str, Any] = {}
                            sla_extra: Dict[str, Any] = {}
                            if shipping:
                                try:
                                    rs = fetch_shipment(int(shipping), new_tok)
                                    if rs.status_code == 200:
                                        sj = rs.json()
                                        _collect_descriptions(sj, texts)
                                        _collect_date_fields(sj, cand_dates)
                                        try:
                                            shipment_extra = {
                                                "shipment_status": sj.get("status"),
                                                "shipment_substatus": sj.get("substatus"),
                                                "shipment_logistic_type": sj.get("logistic_type"),
                                                "shipment_shipping_mode": sj.get("shipping_mode"),
                                                "shipment_service_id": sj.get("service_id"),
                                                "shipment_tags": sj.get("tags"),
                                            }
                                        except Exception:
                                            pass
                                    # SLA con token refrescado
                                    try:
                                        rsla = fetch_shipment_sla(int(shipping), new_tok)
                                        if rsla.status_code == 200:
                                            sj_sla = rsla.json() or {}
                                            sla_extra = {
                                                "sla_status": sj_sla.get("status"),
                                                "sla_service": sj_sla.get("service"),
                                                "sla_expected_date": sj_sla.get("expected_date"),
                                                "sla_last_updated": sj_sla.get("last_updated"),
                                            }
                                            if sj_sla.get("expected_date"):
                                                cand_dates["sla.expected_date"] = sj_sla.get("expected_date")
                                    except Exception:
                                        pass
                                    # LEAD TIME endpoint dedicado (token refrescado)
                                    try:
                                        rlt = fetch_shipment_lead_time(int(shipping), new_tok)
                                        if rlt.status_code == 200:
                                            lt = rlt.json() or {}
                                            _collect_date_fields(lt, cand_dates)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                            hints: List[str] = []
                            for t in texts:
                                lt = t.lower()
                                if "despach" in lt or "entreg" in lt:
                                    hints.append(t)
                            if args.only_texts:
                                for t in texts:
                                    print(t)
                                return
                            dispatch_by_iso, dispatch_label = _derive_dispatch_by(cand_dates)
                            comparison: Optional[Dict[str, Any]] = None
                            if args.compare_schemas and shipping:
                                try:
                                    r_leg = fetch_shipment(int(shipping), new_tok, x_format_new=False)
                                    legacy = r_leg.json() if r_leg.status_code == 200 else None
                                    r_new = fetch_shipment(int(shipping), new_tok, x_format_new=True)
                                    newj = r_new.json() if r_new.status_code == 200 else None
                                    r_sla = fetch_shipment_sla(int(shipping), new_tok)
                                    sla = r_sla.json() if r_sla.status_code == 200 else None
                                    r_lt = fetch_shipment_lead_time(int(shipping), new_tok)
                                    ltj = r_lt.json() if r_lt.status_code == 200 else None
                                    comparison = {
                                        "legacy": {
                                            "shipping_option.estimated_delivery_final.date": ((legacy or {}).get("shipping_option") or {}).get("estimated_delivery_final", {}).get("date") if isinstance(legacy, dict) else None,
                                            "shipping_option.estimated_delivery_time.date": ((legacy or {}).get("shipping_option") or {}).get("estimated_delivery_time", {}).get("date") if isinstance(legacy, dict) else None,
                                            "shipping_option.estimated_delivery_limit.date": ((legacy or {}).get("shipping_option") or {}).get("estimated_delivery_limit", {}).get("date") if isinstance(legacy, dict) else None,
                                        },
                                        "new": {
                                            "lead_time.estimated_delivery_final.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_final") or {}).get("date") if isinstance(newj, dict) else None,
                                            "lead_time.estimated_delivery_time.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_time") or {}).get("date") if isinstance(newj, dict) else None,
                                            "lead_time.estimated_delivery_limit.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_limit") or {}).get("date") if isinstance(newj, dict) else None,
                                            "lead_time.estimated_delivery_extended.date": (((newj or {}).get("lead_time") or {}).get("estimated_delivery_extended") or {}).get("date") if isinstance(newj, dict) else None,
                                        },
                                        "sla": {
                                            "status": (sla or {}).get("status") if isinstance(sla, dict) else None,
                                            "service": (sla or {}).get("service") if isinstance(sla, dict) else None,
                                            "expected_date": (sla or {}).get("expected_date") if isinstance(sla, dict) else None,
                                            "last_updated": (sla or {}).get("last_updated") if isinstance(sla, dict) else None,
                                        },
                                        "lead_time_endpoint": {
                                            "estimated_delivery_final.date": (((ltj or {}).get("estimated_delivery_final") or {}).get("date") if isinstance(ltj, dict) else None),
                                            "estimated_delivery_time.date": (((ltj or {}).get("estimated_delivery_time") or {}).get("date") if isinstance(ltj, dict) else None),
                                            "estimated_delivery_limit.date": (((ltj or {}).get("estimated_delivery_limit") or {}).get("date") if isinstance(ltj, dict) else None),
                                            "estimated_delivery_extended.date": (((ltj or {}).get("estimated_delivery_extended") or {}).get("date") if isinstance(ltj, dict) else None),
                                        },
                                    }
                                except Exception:
                                    comparison = {"error": "No se pudo comparar schemas"}
                            print(json.dumps({
                                "id": oid,
                                "status": status,
                                "description": description,
                                "date_created": date_created,
                                "date_closed": date_closed,
                                "shipping_id": shipping,
                                "ui_texts": texts,
                                "candidate_dates": cand_dates,
                                "dispatch_hints": hints,
                                "dispatch_by": dispatch_by_iso,
                                "dispatch_label": dispatch_label,
                                **({} if not shipment_extra else shipment_extra),
                                **({} if not sla_extra else sla_extra),
                                **({} if comparison is None else {"comparison": comparison}),
                            }, ensure_ascii=False, indent=2))
                            return
                        else:
                            try:
                                errj2 = r2.json()
                            except Exception:
                                errj2 = None
                            print(f"Refresh hecho pero la llamada devolvió {r2.status_code}: {str(errj2)[:300] if errj2 else r2.text[:300]}", file=sys.stderr)
                last_error = f"HTTP {r.status_code}: {r.text[:300]}"
        except Exception as e:
            last_error = str(e)
            continue

    print(f"No se pudo obtener la orden con los tokens disponibles. Último error: {last_error}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
