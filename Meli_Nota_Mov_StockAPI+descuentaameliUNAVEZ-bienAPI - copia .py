#!/usr/bin/env python3
# ================================================================
#  server_daemon.py  –  Notas ML + API + Descuento de stock WOO
#  v2025-07-08  –  paso-a-paso con código de barras
# ================================================================
from __future__ import annotations
import json, re, time, requests, pyodbc, threading, sys
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, Tuple, Iterable
from requests import HTTPError
from flask import Flask, request
# ───────── GUI ttkbootstrap ────────────────────────────────────
import queue, sys, tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.scrolled import ScrolledText


# ───────── CONFIG ───────────────────────────────────────────────
CLIENT_ID      = "4958133826813354"
CLIENT_SECRET  = "6lsMIpFhzw4s77sKpcQuXXtqgHCbKD2o"
TOKEN_URL      = "https://api.mercadolibre.com/oauth/token"

# ───────── API DRAGONFISH (stock online) ───────────────────────
API_STOCK_URL  = "http://deposito_2:8009/api.Dragonfish/ConsultaStockYPreciosEntreLocales/"
API_IDCLIENTE  = "PRUEBA-WEB"
API_TOKEN      = (
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9."
    "eyJleHAiOjE4MTQzNzg3MDYsInVzdWFyaW8iOiJBRE1JTiIsInBhc3N3b3JkIjoiMDE5NGRk"
    "MGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4"
    "MWQwMyJ9.foX4tqZf_tXfwGVtOC-tY4iDy9ebPtTSKePJ8a1nZWQ"
)
# ─── CONFIG Dragonfish ───────────────────────────
API_TIMEOUT_S = None      # espera ilimitada
API_RETRIES   = 1         # 1 intento → sin reintentos
API_RETRY_DELAY_S = 0     # ya no se usa
NOTE_RETRIES       = 5      # intentos para grabar la nota ML
NOTE_RETRY_DELAY_S = 5      # seg. entre intentos
# --- límites para debug_stock_snapshot --------------------------
SNAPSHOT_RETRIES       = 10     # máx. 3 intentos
SNAPSHOT_RETRY_DELAY_S = 10     # 3 s entre intentos

# Movimientos de stock
MOVE_TIMEOUT_S  = None    # espera ilimitada
MOVE_RETRIES    = 1       # 1 solo intento
MOVE_RETRY_WAIT = 0       # sin espera extra

# --- límites para sincronizar_post_venta ------------------------
POST_SALE_RETRIES       = 3     # cantidad de intentos Dragonfish
POST_SALE_RETRY_DELAY_S = 5     # segundos entre intentos
def _app_dir() -> Path:
    """Directorio base de la app.
    - En .py: carpeta del archivo
    - En PyInstaller: carpeta donde está el .exe (no _MEIPASS)
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

APP_DIR = _app_dir()
TOKEN_PATH      = APP_DIR / "token_unavez.json"
PRIORIDADES_TXT = APP_DIR / "prioridades_depositos.txt"

CONN_STR = (
    r"DRIVER={ODBC Driver 17 for SQL Server};"
    r"SERVER=ranchoaspen\zoo2025;"
    r"DATABASE=master;"
    r"Trusted_Connection=yes;"
)


BASES_EXCLUIDAS = {"MELI", "ADMIN","WOO","TN","OUTLET","MTGCBA","MDQ","MTGJBJ", "MTGBBPS"}
RANGO_DIAS   = 3
INTERVALO_S  = 60
VERBOSE      = True
STEP_BY_STEP = False         # ← pausa con Enter luego de cada pack
TEST_ONE_CYCLE = False       # ← ejecuta sólo un ciclo y corta

MAX_LEN      = 240
CONNECT_RETRIES = 99
RETRY_DELAY_S   = 10

# ─── Mapeo depósito → sucursal (para cancelar) ──────────────────
DEPOS_MAP = {
    "DEP":"BBLANCADE","MDQ":"MARDELGUEM","MONBAHIA":"BBLANCA",
    "MTGBBPS":"BBLANCA","MTGCBA":"CORDOBA","MTGCOM":"NEUQUENCOMAHUE",
    "MTGJBJ":"MARDELJUAN","MTGROCA":"RIONEGROMT","MUNDOAL":"BBLANCAMUN",
    "MUNDOCAB":"PALERMO","MUNDOROC":"RIONEGROMD","NQNALB":"NEUQUENCENTRO",
    "NQNSHOP":"NEUQUENANONIMA",
}

# ─── Etiquetas y patrones ───────────────────────────────────────
API_BLOCK_RE = re.compile(r"\[API:[^\]]*(?:\]|$)", re.I)
TRAIL_RE     = re.compile(r"(?:\b[A-Z0-9]{2,}|NO)(?:,\s*\d+|\s+\d+)?\]\s*$")
HEAD         = lambda t: {"Authorization": f"Bearer {t}"}
# ───────── colas GUI ───────────────────────────────────────────
log_q      = queue.Queue()   # texto plano (stdout/stderr)
GUI_EVENTS = queue.Queue()   # eventos estructurados (dict serializado JSON)

def gui_event(ts, orden, sku, qty, estado):
    GUI_EVENTS.put({"ts": ts, "orden": orden, "sku": sku, "qty": qty, "estado": estado})

# ───────── duplicar salida consola + GUI ───────────────────────
class _TeeStream:
    """
    Envía a la consola original y a la cola de la GUI.
    Acepta str o bytes (decodifica utf-8 con reemplazo).
    """
    def __init__(self, original, q: queue.Queue):
        self._orig = original
        self._q    = q
    def write(self, s):
        if not s:
            return
        if isinstance(s, bytes):
            s = s.decode("utf-8", errors="replace")
        self._orig.write(s)
        self._orig.flush()
        self._q.put(s)
    def flush(self):
        self._orig.flush()

class LogWindow(tb.Window):
    def __init__(self):
        super().__init__(title="Monitor MELI-Dragonfish")
        self.geometry("1200x600")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # lista de eventos
        cols = ("hora", "orden", "sku", "qty", "estado")
        self.tree = tb.Treeview(self, columns=cols, show="headings",
                                bootstyle="info")
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=90 if c!="sku" else 160, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # log crudo
        self.txt = ScrolledText(self, height=8, bootstyle="dark",
                                font=("Consolas", 9))
        self.txt.grid(row=1, column=0, sticky="nsew")

        self.after(100, self._poll)

    def _poll(self):
        # eventos estructurados
        try:
            while True:
                ev = GUI_EVENTS.get_nowait()        # ← ev es dict
                d  = ev                             # ← quita json.loads
                self.tree.insert(
                    "", "end",
                    values=(d["ts"], d["orden"], d["sku"], d["qty"], d["estado"])
                )
        except queue.Empty:
            pass

        # texto plano
        try:
            while True:
                self.txt.insert("end", log_q.get_nowait())
                self.txt.see("end")
        except queue.Empty:
            pass

        self.after(100, self._poll)

# ───────── TOKEN ────────────────────────────────────────────────
def _nota_primera(j: object) -> dict:
    """
    Normaliza la respuesta de /orders/{id}/notes y devuelve
    • un dict {'id':…, 'note':…}      o
    • {'id':None,'note':''} si no hay notas.
    Tolera las tres formas que devuelve ML:
        a) [{'results':[ {...}, {...}] , ...}]
        b) {'results':[ {...}, {...}]}
        c) [{'results':[]}]  -> sin notas
    """
    if isinstance(j, list):
        # caso a)   – [{'results':[...]}]
        if j and isinstance(j[0], dict):
            j = j[0]
        else:
            return {"id": None, "note": ""}

    if isinstance(j, dict):
        # ¿hay array de resultados?
        if "results" in j:
            resultados = j.get("results") or []
            return resultados[0] if resultados else {"id": None, "note": ""}
        # respuesta “vieja” con la nota directamente
        if j.get("id"):
            return j

    return {"id": None, "note": ""}

def refresh_token(old:dict)->dict:
    cid  = str(old.get("client_id") or CLIENT_ID)
    csec = str(old.get("client_secret") or CLIENT_SECRET)
    r = requests.post(TOKEN_URL, timeout=10, data={
        "grant_type":"refresh_token",
        "client_id": cid,
        "client_secret": csec,
        "refresh_token": old["refresh_token"]})
    r.raise_for_status()
    new = r.json(); new["created_at"] = int(time.time())
    # Persistir client_id/secret para futuros refresh si existían
    new.setdefault("client_id", cid)
    new.setdefault("client_secret", csec)
    new.setdefault("refresh_token", old["refresh_token"])
    TOKEN_PATH.write_text(json.dumps(new, indent=2), encoding="utf-8")
    print("🔄  Token renovado")
    return new

def token(force: bool = False) -> Tuple[str, str]:
    # Cargar token.json de forma segura
    try:
        t = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RuntimeError(f"Falta token.json en {TOKEN_PATH}")
    except json.JSONDecodeError:
        raise RuntimeError("token.json inválido")

    # Si falta created_at, forzar refresh inmediato (si hay refresh_token)
    if "created_at" not in t:
        if "refresh_token" in t:
            t = refresh_token(t)  # refresh_token() setea created_at y persiste
        else:
            # Fallback: inventar created_at para forzar refresh en esta llamada
            t["created_at"] = int(time.time()) - int(t.get("expires_in", 0)) - 1
            TOKEN_PATH.write_text(json.dumps(t, indent=2), encoding="utf-8")

    # Expiración segura (usa get por si expires_in no está)
    expires_in = int(t.get("expires_in", 0))
    created_at = int(t.get("created_at", 0))

    if force or (expires_in and time.time() > created_at + expires_in - 120):
        if "refresh_token" not in t:
            raise RuntimeError("No hay refresh_token para renovar el acceso")
        t = refresh_token(t)  # también persiste

    access = t.get("access_token")
    if not access:
        raise RuntimeError("token.json no tiene access_token")

    # user_id puede faltar en el refresh; devolver string vacío si no está
    uid = str(t.get("user_id", ""))

    return access, uid

# ───────── PUNTOS / MULTIPLICADORES ─────────────────────────────
PUNTOS: Dict[str,float] = {}; MULT: Dict[str,float] = {}
if PRIORIDADES_TXT.is_file():
    bloc=None
    for ln in PRIORIDADES_TXT.read_text("utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            if ln.upper().startswith("#PUNTOS"):   bloc="P"
            elif ln.upper().startswith("#MULTIP"): bloc="M"
            continue
        dep,val = re.split(r"[ \t]+", ln, 1); val = float(val.replace(",","."))
        (PUNTOS if bloc=="P" else MULT)[dep.upper()] = val

def val_for(dep, tab, default=0.0):
    return tab.get(dep.upper(), tab.get(dep[:3].upper(), default))

# ───────── UTILIDADES ML ────────────────────────────────────────
def url_item(ml_id: str) -> str:
    """Devuelve la URL visible de una publicación MLA…"""
    return f"https://articulo.mercadolibre.com.ar/{ml_id}"


def api_get(url:str, tok:str, tries:int=2):
    for _ in range(tries):
        r = requests.get(url, headers=HEAD(tok), timeout=10)
        if r.status_code != 401:
            r.raise_for_status()
            return r
        tok,_ = token(True)
    r.raise_for_status()

def pedidos_desde(tok:str, seller:str, desde_iso:str)->list[dict]:
    url = ("https://api.mercadolibre.com/orders/search?"
           f"seller={seller}&order.date_created.from={desde_iso}T00:00:00.000-00:00"
           "&sort=date_desc&limit=50")
    return api_get(url, tok).json().get("results", [])

def sku_item(it:dict)->str:
    return (it.get("seller_sku") or it.get("seller_custom_field") or
            it["item"].get("seller_sku") or it["item"].get("seller_custom_field") or "").strip()

# ───────── ESTADO DEL ENVÍO ─────────────────────────────────────
from dateutil import parser as dt_parser

# ───────── NOTAS ML (leer / upsert) ─────────────────────────────
def leer_nota(oid: int, tok: str) -> dict:
    """Devuelve la primera nota o {'id':None,'note':''}."""
    try:
        raw = api_get(f"https://api.mercadolibre.com/orders/{oid}/notes",
                      tok).json()
        return _nota_primera(raw)
    except HTTPError as e:
        if e.response.status_code in (403, 404):
            return {"id": None, "note": ""}
        raise


# ───────── NOTAS ML · upsert REEMPLAZANDO bloque [API:] ─────────
MAX_LEN = 240       # ya lo tenés arriba; asegurate de tenerlo definido


def upsert_replace_api(oid: int, tok: str, linea: str) -> bool:
    """
    Reemplaza cualquier bloque [API:] en la nota con «linea».
    Realiza NOTE_RETRIES intentos (con NOTE_RETRY_DELAY_S) ante errores
    de red, 4xx transitorios o 5xx.
    """
    for intento in range(NOTE_RETRIES):
        try:
            nota = leer_nota(oid, tok)
            txt = nota.get("note") or nota.get("plain_text", "") or ""
            txt_clean = API_BLOCK_RE.sub("", txt)
            txt_clean = TRAIL_RE.sub("", txt_clean).strip()
            nuevo = f"{txt_clean} {linea}".strip() if txt_clean else linea
            if len(nuevo) > MAX_LEN:
                nuevo = nuevo[:MAX_LEN - 3] + "..."
            payload = json.dumps({"note": nuevo})
            url = f"https://api.mercadolibre.com/orders/{oid}/notes"

            for _ in range(2):  # manejo 401 / id inválido
                if nota.get("id"):
                    resp = requests.put(
                        f"{url}/{nota['id']}",
                        headers=HEAD(tok),
                        data=payload,
                        timeout=10,
                    )
                else:
                    resp = requests.post(
                        url,
                        headers=HEAD(tok),
                        data=payload,
                        timeout=10,
                    )
                if resp.status_code in (403, 404):
                    return False
                if resp.status_code == 400 and nota.get("id"):
                    nota["id"] = None
                    continue
                if resp.status_code == 401:
                    tok, _ = token(True)
                    continue
                resp.raise_for_status()
                return True

        except requests.RequestException:
            pass  # se reintentará

        time.sleep(NOTE_RETRY_DELAY_S)

    return False


# ───────── DESCONTAR STOCK WOO + NOTA [Stock -N] ───────────────
STOCK_TAG_RE = re.compile(r"\[STOCK[^\]]*\]", re.I)
# ───────── UTILIDADES ML (nuevas) ───────────────────────────────
def _ml_items_by_sku(seller: str, sku: str, tok: str) -> list[str]:
    url = f"https://api.mercadolibre.com/users/{seller}/items/search?sku={sku}"
    r   = requests.get(url, headers=HEAD(tok), timeout=10); r.raise_for_status()
    return r.json().get("results", [])

def _ml_item_data(item_id: str, tok: str) -> dict:
    url = f"https://api.mercadolibre.com/items/{item_id}"
    r   = requests.get(url, headers=HEAD(tok), timeout=10); r.raise_for_status()
    return r.json()

def _ml_put(url: str, payload: dict, tok: str) -> None:
    h = {**HEAD(tok), "Content-Type": "application/json"}
    r = requests.put(url, headers=h, data=json.dumps(payload), timeout=10)
    r.raise_for_status()

def actualizar_stock_meli(sku: str, vendido: int, tok: str) -> None:
    tok2, seller = tok, token()[1]

    for item_id in _ml_items_by_sku(seller, sku, tok2):
        data = _ml_item_data(item_id, tok2)

        if data.get("variations"):
            for v in data["variations"]:
                sku_var = (v.get("seller_sku") or v.get("seller_custom_field") or "").strip()
                if sku_var != sku:
                    continue
                antes = v["available_quantity"]
                despues = max(antes - vendido, 0)
                if despues == antes:
                    continue
                url = f"https://api.mercadolibre.com/items/{item_id}/variations/{v['id']}"
                _ml_put(url, {"available_quantity": despues}, tok2)
                print(f"[MELI] SKU {sku} – item {item_id} var {v['id']}: {antes} → {despues}")
        else:
            antes = data["available_quantity"]
            despues = max(antes - vendido, 0)
            if despues != antes:
                url = f"https://api.mercadolibre.com/items/{item_id}"
                _ml_put(url, {"available_quantity": despues}, tok2)
                print(f"[MELI] SKU {sku} – item {item_id}: {antes} → {despues}")

# ───────── DESCONTAR STOCK WOO + MELI (reemplazar completo) ────

# ───────── NOTAS ML · helper seguro ─────────────────────────────



def debug_stock_snapshot(sku: str, tok: str) -> None:
    """
    Imprime un resumen comparando stock API vs. Mercado Libre.

    Limita las llamadas a Dragonfish a pocos intentos para no
    bloquear el daemon en casos de timeout.
    """
    total_api = total_stock_online(
        sku,
        retries=SNAPSHOT_RETRIES,
        delay_s=SNAPSHOT_RETRY_DELAY_S,
    )
    por_depot = stock_por_deposito(
        sku,
        retries=SNAPSHOT_RETRIES,
        delay_s=SNAPSHOT_RETRY_DELAY_S,
    )

    tok2, seller = tok, token()[1]

    ml_detalle: list[tuple[str, str | None, int]] = []
    total_ml = 0
    for item_id in _ml_items_by_sku(seller, sku, tok2):
        data = _ml_item_data(item_id, tok2)
        if data.get("variations"):
            for v in data["variations"]:
                s = (
                    v.get("seller_sku")
                    or v.get("seller_custom_field")
                    or ""
                ).strip()
                if s != sku:
                    continue
                qty = v["available_quantity"]
                ml_detalle.append((item_id, str(v["id"]), qty))
                total_ml += qty
        else:
            qty = data["available_quantity"]
            ml_detalle.append((item_id, None, qty))
            total_ml += qty

    delta = total_ml - total_api
    print(f"\n🔎  {sku}")
    print(f"   API total ..... {total_api}")
    print(f"   ML  total ..... {total_ml}   Δ {delta:+d}")

    print("   ▸ Detalle API (depósito)")
    for dep, qty in sorted(por_depot.items()):
        print(f"     {dep:<10} {qty}")

    print("   ▸ Detalle ML  (item / variación)")
    for item_id, var_id, qty in ml_detalle:
        link = url_item(item_id)
        print(
            f"     {item_id} / {var_id or '–':>10}   {qty}   {link}"
        )
def total_stock_online(
    sku: str,
    retries: int = API_RETRIES,
    delay_s: int = API_RETRY_DELAY_S,
) -> int:
    """
    Suma de unidades en todas las bases no excluidas.

    • `retries`, `delay_s` se pasan a `stock_por_deposito`.
    """
    return sum(
        stock_por_deposito(
            sku, retries=retries, delay_s=delay_s
        ).values()
    )


def set_stock_en_todas(sku: str, nuevo: int, tok: str) -> None:
    """
    Sobrescribe el stock de TODAS las publicaciones que usen `sku`
    dejándolo exactamente en `nuevo`.
    """
    tok2, seller = tok, token()[1]

    for item_id in _ml_items_by_sku(seller, sku, tok2):
        data = _ml_item_data(item_id, tok2)

        if data.get("variations"):
            for v in data["variations"]:
                s = (v.get("seller_sku") or v.get("seller_custom_field") or "").strip()
                if s != sku:
                    continue
                if v["available_quantity"] != nuevo:
                    url = f"https://api.mercadolibre.com/items/{item_id}/variations/{v['id']}"
                    _ml_put(url, {"available_quantity": nuevo}, tok2)
                    print(f"[SYNC-FORCE] {sku} – {item_id}/{v['id']}: "
                          f"{v['available_quantity']} → {nuevo}")
        else:
            if data["available_quantity"] != nuevo:
                url = f"https://api.mercadolibre.com/items/{item_id}"
                _ml_put(url, {"available_quantity": nuevo}, tok2)
                print(f"[SYNC-FORCE] {sku} – {item_id}: "
                      f"{data['available_quantity']} → {nuevo}")

# ───────── SINCRONIZAR STOCK DESPUÉS DE CADA VENTA ──────────
def sincronizar_post_venta(sku: str, vendido: int, tok: str) -> None:
    """
    Calcula ‘nuevo = stock_físico – vendido’ y deja esa cantidad
    en TODAS las publicaciones con ese SKU.

    Si Dragonfish no responde tras POST_SALE_RETRIES ⇒ no toca ML.
    """
    fisico = total_stock_online(
        sku,
        retries=POST_SALE_RETRIES,
        delay_s=POST_SALE_RETRY_DELAY_S,
    )

    if fisico is None or fisico == 0 and not stock_por_deposito(
        sku,
        retries=POST_SALE_RETRIES,
        delay_s=POST_SALE_RETRY_DELAY_S,
    ):
        print(f"⚠️  Dragonfish sin respuesta: se pospone {sku}")
        return

    nuevo = max(fisico - vendido, 0)
    set_stock_en_todas(sku, nuevo, tok)
def sincronizar_stock_ml(sku: str, tok: str) -> None:
    """
    Alinea la cantidad disponible en TODAS las publicaciones que contengan
    el SKU con el stock real (API Dragonfish excluyendo las bases filtradas).
    """
    total_online = total_stock_online(sku)
    tok2, seller = tok, token()[1]

    for item_id in _ml_items_by_sku(seller, sku, tok2):
        data = _ml_item_data(item_id, tok2)

        if data.get("variations"):
            for v in data["variations"]:
                s = (v.get("seller_sku") or v.get("seller_custom_field") or "").strip()
                if s != sku:
                    continue
                if v["available_quantity"] == total_online:
                    continue
                url = f"https://api.mercadolibre.com/items/{item_id}/variations/{v['id']}"
                _ml_put(url, {"available_quantity": total_online}, tok2)
                print(f"[SYNC] {sku} – item {item_id} var {v['id']}: {v['available_quantity']} → {total_online}")
        else:
            if data["available_quantity"] == total_online:
                continue
            url = f"https://api.mercadolibre.com/items/{item_id}"
            _ml_put(url, {"available_quantity": total_online}, tok2)
            print(f"[SYNC] {sku} – item {item_id}: {data['available_quantity']} → {total_online}")

# ───────── MOVIMIENTO + NOTA [STOCK -N] ─────────────────────────
# helper: pausa de depuración
def pausa_opcional():
    if STEP_BY_STEP:
        try:
            input("\n⏸  <Enter> para seguir…")
        except EOFError:
            pass

# mueve stock + nota [STOCK -N]  (reemplaza descontar_stock)

# ───────── FUNCIÓN COMPLETA `mover_stock()` ─────────────────────
def mover_stock(oid: int,
                req: dict[str, int],
                tok: str,
                nota_prev: str) -> bool:
    """
    Envía el movimiento y agrega nota [STOCK -N].  
    Trazas detalladas para identificar cuelgues.
    """
    print(f"   mover_stock({oid}) start"); sys.stdout.flush()

    if STOCK_TAG_RE.search(nota_prev):
        print("   mover_stock: ya había [STOCK] — skip"); sys.stdout.flush()
        return False

    ok_global, total_desc = True, 0

    for sku, qty in req.items():
        print(f"      SKU {sku} qty {qty} …"); sys.stdout.flush()

        codb = codigo_barra_por_sku(sku)
        print(f"         → código barra: {codb}"); sys.stdout.flush()

        info = datos_articulo(codb) if codb else None
        if not codb or not info:
            ok_global = False
            print(f"⚠️  Datos faltantes para {sku}")
            continue

        print("         → POST Dragonfish"); sys.stdout.flush()
        ok_env = enviar_movimiento_stock(oid, codb, qty, info)
        print(f"         ← POST ok={ok_env}"); sys.stdout.flush()
        gui_event(ts=time.strftime("%H:%M:%S"),
                  orden=oid,
                  sku=sku,
                  qty=qty,
                  estado="OK" if ok_env else "FAIL")

        if not ok_env:
            ok_global = False
        total_desc += qty

    if ok_global and total_desc:
        append_stock_note(oid, tok, total_desc)
        print(f"   mover_stock({oid}) end OK"); sys.stdout.flush()
        return True

    print(f"⚠️  Movimiento incompleto, orden {oid}")
    print(f"   mover_stock({oid}) end FAIL"); sys.stdout.flush()
    return False
def _shipping_id_from(order:dict)->int|None:
    ship = order.get("shipping")
    if isinstance(ship, dict): return ship.get("id")
    if isinstance(ship, (int,str)):
        try: return int(ship)
        except ValueError: pass
    return order.get("shipping_id")

def get_shipment_info(sid: int | None, tok: str) -> tuple[list[str], str, str, str]:
    """
    Devuelve (tags, status, created_iso, substatus) del shipment.
    Soporta respuestas dict *o* list (algunas cuentas devuelven un array).
    """
    if not sid:
        return [], "", "", ""

    url = f"https://api.mercadolibre.com/shipments/{sid}"
    try:
        r = requests.get(
            url,
            headers={**HEAD(tok), "x-format-new": "true"},
            timeout=10,
        )
        r.raise_for_status()
        j = r.json()

        # --- ML a veces responde una lista -------------
        if isinstance(j, list):
            j = j[0] if j else {}

        return (
            j.get("tags", []) or [],
            j.get("status", "") or "",
            j.get("date_created", "") or "",
            j.get("substatus", "") or "",
        )
    except Exception:
        # cualquier error → valores vacíos
        return [], "", "", ""

def estado_envio(tags:list[str], status:str, created:str, sub:str)->str:
    tags = {t.lower() for t in tags}
    status = (status or "").lower()
    sub    = (sub or "").lower()

    if sub=="printed" or "label_printed" in tags: return "Etiqueta impresa"
    if sub=="ready_to_print" or "ready_to_print" in tags or "ready_to_ship" in tags:
        return "Etiqueta lista para imprimir"
    if status in {"shipped","delivered"}: return status.capitalize()
    if status=="cancelled":               return "Cancelado"

    try:
        dc = dt_parser.isoparse(created)
        if (datetime.now(timezone.utc)-dc).total_seconds()>86_400:
            return "Demorado 1 día"
    except Exception:
        pass
    return "error"

def estado_envio_orden(order:dict, tok:str)->str:
    sid = _shipping_id_from(order)
    tags, st, created, sub = get_shipment_info(sid, tok)
    if not tags: tags = order.get("tags",[])
    return estado_envio(tags, st, created, sub)

# ───────── STOCK POR DEPÓSITO · vía API Dragonfish ─────────────


def stock_por_deposito(
    sku: str,
    excluidas: set[str] | None = None,
    retries: int = API_RETRIES,
    delay_s: int = API_RETRY_DELAY_S,
) -> dict[str, int]:
    """
    Devuelve {base: unidades} sumando positivos y RESTANDO negativos,
    ignorando las bases de `excluidas`.

    • `retries`, `delay_s` permiten limitar la espera en llamadas puntuales
      (p. ej. debug_snapshot) sin modificar la lógica global.
    """
    if excluidas is None:
        excluidas = BASES_EXCLUIDAS

    art, col, tal = sku.split("-", 2)
    hdr = {
        "accept": "application/json",
        "IdCliente": API_IDCLIENTE,
        "Authorization": API_TOKEN,
    }

    try:
        r = requests.get(
            API_STOCK_URL,
            params={"query": art},
            headers=hdr,
            timeout=API_TIMEOUT_S   # None
        )
        r.raise_for_status()        # cualquier 4xx/5xx lanza excepción
    except requests.RequestException as e:
        print(f"❌  Error API Dragonfish: {e}")
        return {}                   # sin reintentos

    stock_map: dict[str, int] = {}
    for fila in r.json().get("Resultados", []):
        if f"{fila['Articulo']}-{fila['Color']}-{fila['Talle']}" != sku:
            continue
        for st in fila.get("Stock", []):
            base = st["BaseDeDatos"].strip().upper()
            if base in excluidas:
                continue
            cant = int(st["Stock"])          # puede ser negativo
            if cant == 0:
                continue
            stock_map[base] = stock_map.get(base, 0) + cant
    return stock_map

def ajustar_stock_variacion(item_id: str,
                             variation_id: int | None,
                             vendido: int,
                             tok: str) -> None:
    """
    Resta `vendido` unidades SOLO en (item_id, variation_id).
    """
    if variation_id:
        url = f"https://api.mercadolibre.com/items/{item_id}/variations/{variation_id}"
        nuevo = None
        data = _ml_item_data(item_id, tok)
        for v in data["variations"]:
            if v["id"] == variation_id:
                nuevo = max(v["available_quantity"] - vendido, 0)
                break
        if nuevo is None:
            print(f"⚠️  variación {variation_id} no encontrada en {item_id}")
            return
        _ml_put(url, {"available_quantity": nuevo}, tok)
        print(f"[MELI] item {item_id} var {variation_id}: → {nuevo}")

    else:  # publicación sin variaciones
        data  = _ml_item_data(item_id, tok)
        nuevo = max(data["available_quantity"] - vendido, 0)
        url   = f"https://api.mercadolibre.com/items/{item_id}"
        _ml_put(url, {"available_quantity": nuevo}, tok)
        print(f"[MELI] item {item_id}: → {nuevo}")



def codigo_barra_por_sku(sku:str)->str|None:
    art,col,tal = sku.split("-",2)
    q = (
        "SELECT TOP 1 RTRIM(CCODIGO) "
        "FROM DRAGONFISH_DEPOSITO.ZooLogic.EQUI "
        "WHERE CARTICUL=? AND CCOLOR=? AND CTALLE=?"
    )
    with pyodbc.connect(CONN_STR, autocommit=True) as con:
        cur = con.cursor()
        row = cur.execute(q, art, col, tal).fetchone()
        return row[0] if row else None

# ───────── MOVIMIENTO DRAGONFISH (WOO) ──────────────────────────
def fecha_dragonfish()->str:
    zona = timezone(timedelta(hours=-3))
    ms   = int(datetime.now(zona).timestamp()*1000)
    return f"/Date({ms}-0300)/"

def hora_dragonfish()->str:
    zona = timezone(timedelta(hours=-3))
    return datetime.now(zona).strftime("%H:%M:%S")

def datos_articulo(codb:str)->dict|None:
    q = (
        "SELECT TOP 1 "
        "RTRIM(CARTICUL), RTRIM(CCOLOR), RTRIM(CTALLE), RTRIM(ARTDES) "
        "FROM DRAGONFISH_DEPOSITO.ZooLogic.EQUI e "
        "LEFT JOIN DRAGONFISH_DEPOSITO.ZooLogic.ART a "
        "ON e.CARTICUL=a.ARTCOD "
        "WHERE RTRIM(CCODIGO)=?"
    )
    with pyodbc.connect(CONN_STR, autocommit=True) as con:
        cur=con.cursor(); row=cur.execute(q,codb).fetchone()
        if row:
            return dict(CODIGO_ARTICULO=row[0],CODIGO_COLOR=row[1],
                        CODIGO_TALLE=row[2],ARTDES=row[3])
    return None

# ───── FUNCIÓN COMPLETA enviar_movimiento_stock() ─────────────────────────
def enviar_movimiento_stock(pedido: int, codb: str, cant: int,
                            info: dict) -> bool:
    url = "http://190.211.201.217:8009/api.Dragonfish/Movimientodestock/"
    hdr = {
        "accept": "application/json",
        "IdCliente": API_IDCLIENTE,
        "Authorization": API_TOKEN,
        "Content-Type": "application/json",
        "BaseDeDatos": "MELI",
    }
    fecha = fecha_dragonfish()
    hora  = hora_dragonfish()
    body  = {
        "OrigenDestino": "MELI", "Tipo": 2, "Motivo": "API",
        "vendedor": "API", "Remito": "-", "CompAfec": [], "Fecha": fecha,
        "Observacion": f"MELI API {pedido}",          # idempotencia
        "MovimientoDetalle": [{
            "Articulo": codb,
            "ArticuloDetalle": info["ARTDES"],
            "Color": info["CODIGO_COLOR"],
            "Talle": info["CODIGO_TALLE"],
            "Cantidad": cant,
            "NroItem": 1,
        }],
        "InformacionAdicional": {
            "FechaAltaFW": fecha, "HoraAltaFW": hora,
            "EstadoTransferencia": "PENDIENTE",
            "BaseDeDatosAltaFW": "MELI",
            "BaseDeDatosModificacionFW": "MELI",
            "SerieAltaFW": "901224", "SerieModificacionFW": "901224",
            "UsuarioAltaFW": "API", "UsuarioModificacionFW": "API",
        },
    }

    try:
        r = requests.post(url, headers=hdr,
                          data=json.dumps(body),
                          timeout=MOVE_TIMEOUT_S)  # None
    except requests.RequestException as e:
        print(f"[DF] EXC {e}")      # caídas de red
        return False

    # Éxito
    if r.status_code == 201:
        if VERBOSE:
            print(f"[DF] OK 201: {r.text[:300]}")
        return True

    # Duplicado
    if r.status_code == 409:
        print("[DF] 409 Ya existía → lo doy por válido")
        return True

    # Cualquier otro código
    print(f"[DF] ERROR {r.status_code}: {r.text[:300]}")
    return False


# ───────── MANEJO DE NOTAS STOCK ────────────────────────────────
STOCK_TAG_RE = re.compile(r"\[STOCK[^\]]*\]", re.I)
def append_stock_note(oid: int, tok: str, qty: int) -> None:
    nota = _nota_primera(
        api_get(f"https://api.mercadolibre.com/orders/{oid}/notes", tok).json()
    )
    txt = nota.get("note") or nota.get("plain_text", "") or ""

    if STOCK_TAG_RE.search(txt):          # ya había [STOCK -…]
        return

    nuevo = f"{txt.strip()} [STOCK -{qty}]"
    if len(nuevo) > MAX_LEN:
        nuevo = nuevo[:MAX_LEN-3] + "..."

    payload = json.dumps({"note": nuevo})
    url     = f"https://api.mercadolibre.com/orders/{oid}/notes"

    if nota.get("id"):
        requests.put(f"{url}/{nota['id']}", headers=HEAD(tok),
                     data=payload, timeout=10)
    else:
        requests.post(url, headers=HEAD(tok),
                      data=payload, timeout=10)


# ───────── COMBOS Y GANADOR ─────────────────────────────────────
def combo_score(req, combo:Iterable[str], mat:dict)->float:
    s=0.0
    for sku,need in req.items():
        rem=need
        for dep in combo:
            q = mat.get(dep,{}).get(sku,0)
            if q<=0 or rem==0: continue
            take=min(q,rem)
            s += val_for(dep,PUNTOS)+take*val_for(dep,MULT,1)
            rem-=take
    return s

def mejores_combos(req, mat, n=3):
    deps=list(mat); cmb=[(d,) for d in deps]+list(combinations(deps,2))
    return sorted(cmb,key=lambda c:combo_score(req,c,mat),reverse=True)[:n]

# ───────── DAEMON PRINCIPAL ─────────────────────────────────────
def procesar_stock_si_corresponde(oid:int, req:dict[str,int], tok:str, nota_prev:str)->None:
    if STOCK_TAG_RE.search(nota_prev):      # ya descontado
        return
    total=0
    for sku,qty in req.items():
        codb=codigo_barra_por_sku(sku)
        if not codb:
            print(f"⚠️  Sin código de barras para {sku}")
            continue
        if VERBOSE:
            print(f"[STOCK] Orden {oid} – SKU {sku} → Código barra: {codb}")
        info=datos_articulo(codb)
        if not info: continue
        if enviar_movimiento_stock(oid, codb, qty, info):
            total+=qty
    if total:
        append_stock_note(oid,tok,total)


def ciclo() -> None:
    """
    • Agrupa órdenes por pack_id (o id individual).
    • Si un pack ya tiene [API:] y [STOCK ...] ⇒ salta directo.
    • Maneja trazas begin/end de cada pack para detectar cuelgues.
    """
    print(f"[{time.strftime('%H:%M:%S')}] ► ciclo start"); sys.stdout.flush()

    tok, seller = token()
    desde = (datetime.now(timezone.utc) - timedelta(days=RANGO_DIAS))\
            .strftime("%Y-%m-%d")

    # 1) Pedidos recientes ---------------------------------------------------
    packs: dict[str, list] = defaultdict(list)
    for o in pedidos_desde(tok, seller, desde):
        packs[str(o.get("pack_id") or o["id"])].append(o)

    procesados = 0

    # 2) Procesar cada pack ---------------------------------------------------
    for pid, lote in packs.items():
        print(f"·· pack {pid} begin"); sys.stdout.flush()            # BEGIN
        try:
            # ---------- 2.1 multiventa / multi-orden ------------------------
            is_multi_order = len(lote) > 1
            items_total    = sum(len(o["order_items"]) for o in lote)
            is_multiventa  = is_multi_order or items_total > 1

            # ---------- 2.2 SKUs y cantidades ------------------------------
            req: dict[str, int] = defaultdict(int)               # SKU → cant
            ventas_var: dict[tuple[str, int | None], int] = {}   # (item, var)→cant

            for o in lote:
                for it in o["order_items"]:
                    sku = sku_item(it)
                    if sku.count("-") != 2:
                        continue
                    qty      = it.get("quantity", 1)
                    item_id  = str(it["item"]["id"])
                    var_id   = it["item"].get("variation_id")    # None si no hay
                    req[sku] += qty
                    ventas_var[(item_id, var_id)] = ventas_var.get(
                        (item_id, var_id), 0
                    ) + qty

            # ---------- 2.3 datos de la orden ------------------------------
            real_id   = lote[0]["id"]
            hdr       = lote[0]
            nota_prev = leer_nota(real_id, tok).get("note", "")
            estado    = estado_envio_orden(hdr, tok)

            if VERBOSE:
                prev = (nota_prev.replace("\n", " ")[:80] + "…") \
                       if len(nota_prev) > 80 else nota_prev
                print(f"Pack {pid} (orden {real_id}) → {sum(req.values())} ítems | "
                      f"Estado: {estado} | Nota previa: {prev or '(vacía)'}")

            # ---------- 2.3.a MULTIVENTA -----------------------------------
            if is_multiventa:
                if "[API: MULTIVENTA]" not in nota_prev:
                    if not upsert_replace_api(real_id, tok, "[API: MULTIVENTA]"):
                        print(f"⚠️  Nota MULTIVENTA no grabada (orden {real_id})")
                        continue
                pausa_opcional()
                procesados += 1
                if TEST_ONE_CYCLE and procesados >= 1:
                    break
                continue

            # ---------- 2.4 pack ya marcado con [API:] ----------------------
            if "[API:" in nota_prev.upper():
                if "[STOCK" in nota_prev.upper():
                    # Todo terminado → siguiente pack
                    continue

                # ⚠️ NO descontar stock si es MULTIVENTA
                if "MULTIVENTA" in nota_prev.upper():
                    print("   ⚠️ MULTIVENTA detectada → NO se descuenta stock individual")
                    continue

                print("   → llamo mover_stock"); sys.stdout.flush()
                ok = mover_stock(real_id, req, tok, nota_prev)
                print("   ← mover_stock terminado"); sys.stdout.flush()

                if ok:
                    for sku, cant in req.items():
                        sincronizar_post_venta(sku, cant, tok)
                continue

            # ---------- 2.5 pack “normal” ----------------------------------
            if not req:
                continue

            sku_base = next(iter(req))
            matriz: dict[str, dict[str, int]] = defaultdict(dict)
            for dep, q in stock_por_deposito(sku_base).items():
                if q > 0:
                    matriz[dep][sku_base] = q

            dep_gan = mejores_combos(req, matriz, 1)[0][0] if matriz else "NO"

            if not upsert_replace_api(real_id, tok,
                                      f"[API: 1) {dep_gan} {req[sku_base]}]"):
                print(f"⚠️  Nota [API:] no grabada (orden {real_id}) – se reintentará")
                continue

            ok = mover_stock(real_id, req, tok, nota_prev)
            if ok:
                for sku, cant in req.items():
                    sincronizar_post_venta(sku, cant, tok)

            pausa_opcional()
            procesados += 1
            if TEST_ONE_CYCLE and procesados >= 1:
                break

        except Exception as e:
            # capturamos cualquier falla para no detener todo el daemon
            print(f"‼️  Excepción en pack {pid}: {e}", file=sys.stderr)
        finally:
            print(f"·· pack {pid} end"); sys.stdout.flush()          # END

    print(f"[{time.strftime('%H:%M:%S')}] ◄ ciclo end"); sys.stdout.flush()


# ───────── FLASK & LOOP ─────────────────────────────────────────
app = Flask(__name__)

@app.route("/ping")
def ping():
    return "OK"


# ───────── LOOP DEL DAEMON ─────────────────────────────────────
def loop_daemon() -> None:
    print("⏳  Hilo daemon iniciado")

    if TEST_ONE_CYCLE:          # ––– modo prueba: UNA sola pasada
        ciclo()
        print("✔️  Prueba terminada – poné TEST_ONE_CYCLE=False para modo continuo")
        return

    # ––– modo normal: vuelve a correr cada INTERVALO_S segundos
    while True:
        try:
            ciclo()
        except Exception as e:
            print("❌", e, file=sys.stderr)
        time.sleep(INTERVALO_S)
# ───────── FIN loop_daemon ─────────────────────────────────────


if __name__ == "__main__":
    # redirección en TEE
    sys.stdout = _TeeStream(sys.__stdout__, log_q)
    sys.stderr = _TeeStream(sys.__stderr__, log_q)

    threading.Thread(target=loop_daemon, daemon=True).start()
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, threaded=True),
        daemon=True
    ).start()

    LogWindow().mainloop()
