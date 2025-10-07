# meli_token_helper.py
# Centralized ML token manager for ML1, using token.json and daemon app credentials
import os, sys, json, time, requests
import threading
import secrets, hashlib, base64, urllib.parse, webbrowser
from typing import Dict

# Default/fallback absolute path kept for backwards-compatibility
FALLBACK_TOKEN_PATH = r"C:\Users\Mundo Outdoor\Desktop\Develop_Mati\Escritor Meli\token.json"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

# Daemon app defaults (used if not present in token.json or env)
DEFAULT_CLIENT_ID = "5057564940459485"
DEFAULT_CLIENT_SECRET = "NM0wSta1bSNSt4CxSEOeSwRC2p9eHQD7"

# Logger opcional (no falla si no existe utils.logger)
try:
    from utils.logger import get_logger  # type: ignore
    _log = get_logger(__name__)
except Exception:  # pragma: no cover
    class _Null:
        def info(self, *a, **k): pass
        def warning(self, *a, **k): pass
        def error(self, *a, **k): pass
    _log = _Null()

def _candidate_paths() -> list[str]:
    """Return candidate paths in priority order for reading existing token.json."""
    cands: list[str] = []
    env_path = os.environ.get("ML_TOKEN_PATH")
    if env_path:
        cands.append(env_path)
    # Next to executable (frozen) or this file (dev utils folder)
    try:
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        cands.append(os.path.join(base_dir, "token.json"))
    except Exception:
        pass
    # LOCALAPPDATA default location
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        cands.append(os.path.join(local_app, "ClienteMatias", "token.json"))
    # Legacy fallback
    cands.append(FALLBACK_TOKEN_PATH)
    return cands

def _preferred_write_path() -> str:
    """Return preferred path where we should create/update token.json."""
    env_path = os.environ.get("ML_TOKEN_PATH")
    if env_path:
        return env_path
    try:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_dir, "token.json")
    except Exception:
        pass
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        return os.path.join(local_app, "ClienteMatias", "token.json")
    return FALLBACK_TOKEN_PATH

def _load() -> Dict:
    # Find first existing token.json among candidates
    token_path = None
    for p in _candidate_paths():
        if os.path.isfile(p):
            token_path = p
            break
    if not token_path:
        # Try seeding from bundled file (when running as exe)
        seeded = False
        try:
            base_dir = getattr(sys, "_MEIPASS", None) or (os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else None)
            if base_dir:
                # Prefer explicit token_depo.json; fallback to token.json if embedded
                for name in ("token_depo.json", "token.json"):
                    cand = os.path.join(base_dir, name)
                    if os.path.isfile(cand):
                        with open(cand, "r", encoding="utf-8") as f:
                            cfg_seed = json.load(f)
                        # Persist to preferred write path
                        _save(cfg_seed)
                        token_path = _preferred_write_path()
                        seeded = True
                        _log.info(f"🔐 token.json inicializado desde recurso embebido: {name}")
                        break
        except Exception as e:
            _log.warning(f"No se pudo inicializar token.json desde recurso embebido: {e}")
        if not seeded or not token_path:
            # Not found anywhere and no bundle: instruct where to place it
            expected = _preferred_write_path()
            raise FileNotFoundError(
                f"No se encontró token.json. Colóquelo en: {expected} o defina ML_TOKEN_PATH"
            )
    with open(token_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    try:
        _log.info(f"🔎 Usando token.json en: {token_path}")
    except Exception:
        pass
    # Normalize
    cfg["access_token"] = (cfg.get("access_token", "") or "").replace("\n", "").replace("\r", "").strip()
    cfg["refresh_token"] = cfg.get("refresh_token", "") or ""
    cfg["client_id"] = (
        cfg.get("client_id")
        or os.getenv("ML_CLIENT_ID")
        or DEFAULT_CLIENT_ID
    )
    cfg["client_secret"] = (
        cfg.get("client_secret")
        or os.getenv("ML_CLIENT_SECRET")
        or DEFAULT_CLIENT_SECRET
    )
    cfg["user_id"] = cfg.get("user_id") or os.getenv("ML_USER_ID", "")
    try:
        cfg["expires_in"] = int(cfg.get("expires_in", 0) or 0)
    except Exception:
        cfg["expires_in"] = 0
    try:
        cfg["created_at"] = int(cfg.get("created_at", 0) or 0)
    except Exception:
        cfg["created_at"] = 0
    try:
        _log.info(f"🔑 client_id detectado para refresh: {cfg['client_id']}")
    except Exception:
        pass
    return cfg

def _save(cfg: Dict) -> None:
    token_path = _preferred_write_path()
    # Ensure parent dir exists
    try:
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
    except Exception:
        pass
    tmp_path = token_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "access_token": cfg.get("access_token", ""),
                "refresh_token": cfg.get("refresh_token", ""),
                "client_id": cfg.get("client_id", ""),
                "client_secret": cfg.get("client_secret", ""),
                "user_id": cfg.get("user_id", ""),
                "expires_in": int(cfg.get("expires_in", 0) or 0),
                "created_at": int(cfg.get("created_at", 0) or 0),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    # atomic replace
    os.replace(tmp_path, token_path)


def _env_creds() -> tuple[str, str, str]:
    """Lee credenciales/redirect_uri desde entorno o defaults.
    Retorna (client_id, client_secret, redirect_uri).
    """
    cid = os.getenv("ML_CLIENT_ID") or DEFAULT_CLIENT_ID
    csec = os.getenv("ML_CLIENT_SECRET") or DEFAULT_CLIENT_SECRET
    ruri = os.getenv("ML_REDIRECT_URI") or "https://www.mundooutdoor.ar/"
    return str(cid), str(csec), str(ruri)


def _authorize_interactive() -> Dict:
    """Flujo OAuth de primera vez (PKCE): abre navegador y pide pegar el code.
    Devuelve el cfg y además lo persiste en token.json.
    """
    client_id, client_secret, redirect_uri = _env_creds()

    # 1) PKCE
    code_verifier = secrets.token_urlsafe(64)
    sha256 = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(sha256).rstrip(b"=").decode()

    # 2) URL de autorización
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = "https://auth.mercadolibre.com.ar/authorization?" + urllib.parse.urlencode(params)

    # Intentar abrir navegador
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    # 3) Pedir code al usuario: intentar GUI; fallback a input() si hay consola
    code = ""
    try:
        import tkinter as tk
        from tkinter import simpledialog, messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showinfo("Autorizar Mercado Libre", f"1) Abrí esta URL y autorizá la app:\n\n{auth_url}\n\n2) Copiá el parámetro 'code' de la URL de redirección y pegalo a continuación.")
        code = simpledialog.askstring("Código de autorización", "Pega aquí el valor de 'code':", parent=root) or ""
        root.destroy()
    except Exception:
        # Fallback consola
        print("1) Abre esta URL y autoriza:")
        print(auth_url)
        code = input("\n2) Pega aquí el code: ").strip()

    code = (code or "").strip()
    if not code:
        raise RuntimeError("Autorización cancelada: no se ingresó 'code'.")

    # 4) Intercambio por tokens
    data = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    r = requests.post(TOKEN_URL, data=data, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Intercambio de token falló: {r.status_code} {r.text[:200]}")

    tok = r.json()
    cfg = {
        "access_token": (tok.get("access_token", "") or "").strip(),
        "refresh_token": tok.get("refresh_token", ""),
        "client_id": client_id,
        "client_secret": client_secret,
        "user_id": str(tok.get("user_id", "")),
        "expires_in": int(tok.get("expires_in", 21600) or 21600),
        "created_at": int(tok.get("created_at", int(time.time()))),
    }
    _save(cfg)
    return cfg


def _is_expired(cfg: Dict, skew: int = 60) -> bool:
    if not cfg.get("expires_in") or not cfg.get("created_at"):
        return False
    return (cfg["created_at"] + cfg["expires_in"] - skew) <= int(time.time())


def refresh_if_needed(force: bool = False) -> Dict:
    """
    Loads token.json, refreshes only if needed, persists updates, and returns the cfg dict.
    Required keys in result: access_token, refresh_token (if provided by ML), user_id (if known).
    """
    try:
        cfg = _load()
    except FileNotFoundError:
        # Primera vez: intentar flujo interactivo solo si está habilitado
        if os.getenv("ML_INTERACTIVE_BOOTSTRAP") == "1":
            _log.info("token.json no encontrado: iniciando autorización interactiva de ML...")
            cfg = _authorize_interactive()
        else:
            raise
    if not force and not _is_expired(cfg):
        return cfg

    if not (cfg.get("refresh_token") and cfg.get("client_id") and cfg.get("client_secret")):
        raise RuntimeError(
            "Faltan client_id/client_secret o refresh_token para refrescar token."
        )

    data = {
        "grant_type": "refresh_token",
        "client_id": cfg["client_id"],
        "client_secret": cfg["client_secret"],
        "refresh_token": cfg["refresh_token"],
    }
    r = requests.post(TOKEN_URL, data=data, timeout=15)
    if r.status_code != 200:
        txt = r.text[:300]
        # Si el refresh_token no corresponde al client_id actual o está inválido
        if r.status_code == 400 and ("invalid_grant" in txt or "client_id does not match" in txt or "does not match the original" in txt):
            if os.getenv("ML_INTERACTIVE_BOOTSTRAP") == "1":
                _log.warning("Refresh falló por invalid_grant/mismatch; iniciando autorización interactiva para regenerar token.json...")
                cfg = _authorize_interactive()
                return cfg
            else:
                raise RuntimeError(
                    "Refresh falló por invalid_grant/mismatch y ML_INTERACTIVE_BOOTSTRAP!=1. "
                    "Genere token.json en una PC con acceso y empaquételo o colóquelo junto al exe."
                )
        raise RuntimeError(f"Refresh falló: {r.status_code} {txt}")

    tok = r.json()
    cfg["access_token"] = (tok.get("access_token", "") or "").replace("\n", "").replace("\r", "").strip()
    # ML sometimes returns a new refresh_token
    if tok.get("refresh_token"):
        cfg["refresh_token"] = tok["refresh_token"]
    # Persist timing info for proactive refresh
    try:
        cfg["expires_in"] = int(tok.get("expires_in", cfg.get("expires_in", 0)) or 0)
    except Exception:
        cfg["expires_in"] = cfg.get("expires_in", 0) or 0
    cfg["created_at"] = int(tok.get("created_at", int(time.time())))
    # Ensure user_id if present
    if tok.get("user_id"):
        cfg["user_id"] = str(tok["user_id"])

    _save(cfg)
    return cfg


# ---------------------------
# Auto-refresh en background
# ---------------------------
_auto_thread: threading.Thread | None = None

def _auto_refresh_loop(interval_seconds: int) -> None:
    """Hilo daemon que fuerza refresh periódico del token.
    Hace un refresh inmediato al iniciar y luego cada intervalo.
    """
    while True:
        try:
            cfg = refresh_if_needed(force=True)
            uid = cfg.get("user_id", "?")
            _log.info(f"🔄 Token ML refrescado automáticamente (user_id={uid})")
        except Exception as e:
            _log.warning(f"No se pudo refrescar token automáticamente: {e}")
        # 5h50m por defecto (se define al invocar start_auto_refresh)
        time.sleep(max(60, interval_seconds))


def start_auto_refresh(interval_seconds: int = 21000) -> None:
    """Inicia el hilo daemon de auto-refresh si no está corriendo.
    interval_seconds: intervalo entre intentos (por defecto ~5h50m).
    """
    global _auto_thread
    if _auto_thread and _auto_thread.is_alive():
        return
    _auto_thread = threading.Thread(target=_auto_refresh_loop, args=(interval_seconds,), daemon=True)
    _auto_thread.start()
    _log.info(f"🕒 Auto-refresh de token ML iniciado (cada {interval_seconds//3600}h{(interval_seconds%3600)//60}m)")
