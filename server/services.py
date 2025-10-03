from typing import List, Optional, Tuple, Dict, Any
import os
import pyodbc
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests
from urllib.parse import quote_plus
import time

from .schemas import get_allowed_update_fields

load_dotenv()

ODBC_DRIVER = os.getenv("ODBC_DRIVER", "ODBC Driver 17 for SQL Server")

# Primary (acc1) pieces or full connection string
SQL_SERVER = os.getenv("SQL_SERVER", ".\\SQLEXPRESS")
SQL_DB = os.getenv("SQL_DB", "meli_stock")
SQL_TRUSTED = os.getenv("SQL_TRUSTED", "yes").lower() in ("1", "true", "yes")
SQL_USER = os.getenv("SQL_USER")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")
ORDERS_CONN_STR = os.getenv("ORDERS_CONN_STR")  # optional full conn string override for acc1

# Secondary (acc2) pieces or full connection string
SQL_SERVER2 = os.getenv("SQL_SERVER2")
SQL_DB2 = os.getenv("SQL_DB2")
SQL_TRUSTED2 = (os.getenv("SQL_TRUSTED2") or os.getenv("SQL2_TRUSTED") or "yes").lower() in ("1", "true", "yes")
SQL_USER2 = os.getenv("SQL_USER2")
SQL_PASSWORD2 = os.getenv("SQL_PASSWORD2")
ORDERS2_CONN_STR = os.getenv("ORDERS2_CONN_STR")  # optional full conn string for acc2

TABLE = "orders_meli"

# CallMeBot credentials (optional)
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE")  # e.g., 5492915163952
CALLMEBOT_APIKEY = os.getenv("CALLMEBOT_APIKEY")  # e.g., 4950672
_NOTIF_TABLE = "split_notifications_sent"
# track readiness per account ("acc1"/"acc2")
_notif_table_ready: Dict[str, bool] = {"acc1": False, "acc2": False}

# Cache for column max lengths, per account
_COL_MAXLEN_CACHE: Dict[str, Dict[str, Optional[int]]] = {"acc1": {}, "acc2": {}}


def _build_conn_str(acc: str) -> str:
    if acc == "acc2":
        # acc2: prefer full conn string override if present
        if ORDERS2_CONN_STR:
            return ORDERS2_CONN_STR
        server = SQL_SERVER2 or SQL_SERVER
        db = SQL_DB2 or (SQL_DB + "_acc2" if SQL_DB else None)
        if (os.getenv("SQL_USER2") or os.getenv("SQL_PASSWORD2")) and not SQL_TRUSTED2:
            return f"DRIVER={{{ODBC_DRIVER}}};SERVER={server};DATABASE={db};UID={SQL_USER2};PWD={SQL_PASSWORD2};"
        # default trusted for acc2
        return f"DRIVER={{{ODBC_DRIVER}}};SERVER={server};DATABASE={db};Trusted_Connection={'yes' if SQL_TRUSTED2 else 'no'};"
    # acc1 (default)
    if ORDERS_CONN_STR:
        return ORDERS_CONN_STR
    if SQL_TRUSTED:
        return f"DRIVER={{{ODBC_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DB};Trusted_Connection=yes;"
    return f"DRIVER={{{ODBC_DRIVER}}};SERVER={SQL_SERVER};DATABASE={SQL_DB};UID={SQL_USER};PWD={SQL_PASSWORD};"


def _get_conn(acc: str = "acc1"):
    return pyodbc.connect(_build_conn_str(acc))


def _ensure_notif_table(acc: str = "acc1"):
    if _notif_table_ready.get(acc):
        return
    with _get_conn(acc) as cn:
        cur = cn.cursor()
        cur.execute(
            f"""
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{_NOTIF_TABLE}' AND xtype='U')
BEGIN
    CREATE TABLE {_NOTIF_TABLE} (
        order_id NVARCHAR(50) NOT NULL PRIMARY KEY,
        notified_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
END
            """
        )
        cn.commit()
    _notif_table_ready[acc] = True


def _get_col_maxlen(col_name: str, acc: str = "acc1") -> Optional[int]:
    """Return CHARACTER_MAXIMUM_LENGTH for NVARCHAR/VARCHAR columns, or None.
    Caches results per process to avoid repeated queries.
    """
    key = col_name.lower()
    cache = _COL_MAXLEN_CACHE.setdefault(acc, {})
    if key in cache:
        return cache[key]
    try:
        with _get_conn(acc) as cn:
            cur = cn.cursor()
            cur.execute(
                """
SELECT CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
                """,
                TABLE,
                col_name,
            )
            row = cur.fetchone()
            maxlen = row[0] if row else None
            # SQL Server uses -1 for MAX types; interpret as unlimited (None)
            if isinstance(maxlen, int) and maxlen < 0:
                maxlen = None
            cache[key] = maxlen
            return maxlen
    except Exception:
        cache[key] = None
        return None


def _truncate_to_column(col_name: str, value: Any, acc: str = "acc1") -> Any:
    """If value is a string and the column has a max length, truncate safely."""
    try:
        if isinstance(value, str):
            maxlen = _get_col_maxlen(col_name, acc)
            if isinstance(maxlen, int) and maxlen >= 0 and len(value) > maxlen:
                return value[:maxlen]
    except Exception:
        pass
    return value


def _was_split_notified(order_id: str, acc: str = "acc1") -> bool:
    _ensure_notif_table(acc)
    with _get_conn(acc) as cn:
        cur = cn.cursor()
        cur.execute(f"SELECT 1 FROM {_NOTIF_TABLE} WHERE order_id = ?", order_id)
        return cur.fetchone() is not None


def _mark_split_notified(order_id: str, acc: str = "acc1"):
    _ensure_notif_table(acc)
    with _get_conn(acc) as cn:
        cur = cn.cursor()
        try:
            cur.execute(f"INSERT INTO {_NOTIF_TABLE} (order_id) VALUES (?)", order_id)
            cn.commit()
        except Exception:
            # ignore duplicates/races
            pass


def _send_callmebot_message(text: str) -> bool:
    if not CALLMEBOT_PHONE or not CALLMEBOT_APIKEY:
        return False
    try:
        url = (
            f"https://api.callmebot.com/whatsapp.php?phone={CALLMEBOT_PHONE}"
            f"&text={quote_plus(text)}&apikey={CALLMEBOT_APIKEY}"
        )
        r = requests.get(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def list_orders_columns(acc: str = "acc1") -> List[str]:
    """Return all column names of orders_meli from INFORMATION_SCHEMA."""
    with _get_conn(acc) as cn:
        cur = cn.cursor()
        cur.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
            TABLE,
        )
        return [r[0] for r in cur.fetchall()]


_ALL_COLUMNS_CACHE: Dict[str, Optional[List[str]]] = {"acc1": None, "acc2": None}


def _all_columns(acc: str = "acc1") -> List[str]:
    if _ALL_COLUMNS_CACHE.get(acc) is None:
        _ALL_COLUMNS_CACHE[acc] = list_orders_columns(acc)
    # mypy: we're sure it's set now
    return _ALL_COLUMNS_CACHE[acc] or []


def get_default_fields() -> List[str]:
    # Fallback si el cliente no pide fields
    return [
        "order_id",
        "pack_id",
        "sku",
        "seller_sku",
        "barcode",
        "barcode_all",
        "nombre",
        "onombre",
        "ARTICULO",
        "COLOR",
        "TALLE",
        "display_color",
        "qty",
        "date_created",
        "date_closed",
        "_estado",
        # Shipping
        "shipping_status",
        "shipping_substatus",
        "shipping_estado",
        "shipping_subestado",
        "venta_tipo",
        "meli_ad",
        "agotamiento_flag",
        "COMENTARIO",
        "note",
        "deposito_asignado",
        "ready_to_print",
        "printed",
        # Buyer & amounts
        "buyer_id",
        "unit_price",
        "total_amount",
        "currency_id",
        # Extras útiles
        "asignacion_detalle",
        "mov_depo_hecho",
        "mov_depo_numero",
        "mov_depo_obs",
        "numero_movimiento",
        "tracking_number",
        # Movimiento LOCAL (nuevo)
        "MOV_LOCAL_HECHO",
        "MOV_LOCAL_NUMERO",
        "MOV_LOCAL_OBS",
        "MOV_LOCAL_TS",
        "pack_orders_json",
    ]


def _col_exists(name: str, acc: str = "acc1") -> bool:
    try:
        return name in _all_columns(acc)
    except Exception:
        return False


def _poll_split_required_since(since_utc: datetime, acc: str = "acc1") -> List[Dict[str, Any]]:
    """Fetch orders with DEBE_PARTIRSE=1 updated since 'since_utc', with minimal fields.
    Falls back to recent IDs if timestamp columns are missing.
    """
    cols = ["order_id", "DEBE_PARTIRSE", "sku", "seller_sku", "nombre", "ARTICULO"]
    timestamp_filters = []
    args: List[Any] = []
    if _col_exists("fecha_actualizacion", acc):
        timestamp_filters.append("[fecha_actualizacion] >= ?")
        args.append(since_utc)
    if _col_exists("last_update", acc):
        timestamp_filters.append("[last_update] >= ?")
        args.append(since_utc)

    where_parts = ["[DEBE_PARTIRSE] = 1"]
    if timestamp_filters:
        where_parts.append("(" + " OR ".join(timestamp_filters) + ")")

    where_sql = " WHERE " + " AND ".join(where_parts)
    select_cols = ", ".join(f"[{c}]" for c in cols if _col_exists(c, acc))
    order_clause = " ORDER BY [id] DESC" if _col_exists("id", acc) else ""
    sql = f"SELECT {select_cols} FROM {TABLE}{where_sql}{order_clause}"

    items: List[Dict[str, Any]] = []
    with _get_conn(acc) as cn:
        cur = cn.cursor()
        try:
            cur.execute(sql, *args)
            rows = cur.fetchall()
            col_names = [c[0] for c in cur.description]
            for r in rows:
                obj = {col_names[i]: r[i] for i in range(len(col_names))}
                items.append(obj)
        except Exception:
            # Fallback: last 200 by id, no time filter
            try:
                sql2 = f"SELECT TOP 200 {select_cols} FROM {TABLE} WHERE [DEBE_PARTIRSE] = 1{order_clause}"
                cur.execute(sql2)
                rows = cur.fetchall()
                col_names = [c[0] for c in cur.description]
                for r in rows:
                    obj = {col_names[i]: r[i] for i in range(len(col_names))}
                    items.append(obj)
            except Exception:
                pass
    return items


def run_split_notifier_loop(interval_secs: int = 60, acc: str = "acc1"):
    """Background loop to notify once via CallMeBot for split-required orders.
    Runs forever in a daemon thread.
    """
    # Start with a small lookback window to catch recent events on first run
    last_seen = datetime.utcnow() - timedelta(minutes=10)
    while True:
        start = datetime.utcnow()
        try:
            candidates = _poll_split_required_since(last_seen, acc)
            for obj in candidates:
                order_id = obj.get("order_id")
                debe = obj.get("DEBE_PARTIRSE")
                if not order_id or debe != 1:
                    continue
                if _was_split_notified(str(order_id), acc):
                    continue
                sku = str(obj.get("sku") or obj.get("seller_sku") or "")
                nombre = str(obj.get("nombre") or obj.get("ARTICULO") or "")
                msg = f"ALERTA: Orden {order_id} requiere PARTIRSE. SKU {sku}. {nombre[:100]}"
                ok = _send_callmebot_message(msg)
                if ok:
                    _mark_split_notified(str(order_id), acc)
        except Exception:
            # swallow and continue
            pass
        # Update last_seen to now, so next loop only sees fresh changes
        last_seen = start
        time.sleep(max(5, int(interval_secs)))


def _validate_fields(selected_fields: Optional[List[str]], acc: str = "acc1") -> List[str]:
    cols = _all_columns(acc)
    if not selected_fields or len(selected_fields) == 0:
        # default subset si no piden nada
        fields = [c for c in get_default_fields() if c in cols]
        return fields
    lowered = [f.lower() for f in selected_fields]
    if "*" in selected_fields or "all" in lowered:
        return cols
    # filtrar solo columnas válidas
    valid = [f for f in selected_fields if f in cols]
    if not valid:
        # evitar select vacío
        valid = [c for c in get_default_fields() if c in cols]
    return valid


def _build_filters(params: Dict[str, Any], acc: str = "acc1") -> Tuple[str, List[Any]]:
    where = []
    args: List[Any] = []

    # Aliases: permitir que shipping_estado=ready_to_print/printed funcionen aunque
    # la base no tenga aún los flags poblados. Traducimos a condiciones sobre flags OR subestado.
    se = params.get("shipping_estado")
    if se in ("ready_to_print", "printed"):
        # Evitar que también caiga en mapping_exact como igualdad simple
        params = dict(params)  # clonar para no mutar el original fuera
        params.pop("shipping_estado", None)
        # Construir OR sobre flag y subestado
        if se == "ready_to_print":
            # ISNULL(ready_to_print,0)=1 OR shipping_subestado='ready_to_print'
            if _col_exists("ready_to_print", acc):
                where.append("(ISNULL([ready_to_print], 0) = 1 OR [shipping_subestado] = ?)")
                args.append("ready_to_print")
                # Además, forzar printed=0 si existe la columna (evita impresas)
                if _col_exists("printed", acc):
                    where.append("ISNULL([printed], 0) = 0")
            else:
                # Sin columna de flag: filtrar sólo por subestado
                where.append("[shipping_subestado] = ?")
                args.append("ready_to_print")
        elif se == "printed":
            if _col_exists("printed", acc):
                where.append("(ISNULL([printed], 0) = 1 OR [shipping_subestado] = ?)")
                args.append("printed")
            else:
                where.append("[shipping_subestado] = ?")
                args.append("printed")

    mapping_exact = [
        "order_id",
        "pack_id",
        "sku",
        "seller_sku",
        "barcode",
        "ARTICULO",
        "COLOR",
        "TALLE",
        "display_color",
        "deposito_asignado",
        "_estado",
        "meli_ad",
        "venta_tipo",
        "shipping_estado",
        "shipping_subestado",
        "agotamiento_flag",
        # ready_to_print/printed se tratan aparte para considerar NULL como 0
        "qty",
    ]

    for k in mapping_exact:
        v = params.get(k)
        if v is not None:
            where.append(f"[{k}] = ?")
            args.append(v)

    # Flags con NULL tratado como 0, y alias a subestado cuando piden =1
    for flag in ("ready_to_print", "printed"):
        v = params.get(flag)
        if v is None:
            continue
        if str(v) not in ("0", "1"):
            continue
        # Normalizar a 0/1
        try:
            val = 1 if int(v) == 1 else 0
        except Exception:
            val = 1 if str(v).lower() in ("1","true","yes") else 0

        target_sub = "ready_to_print" if flag == "ready_to_print" else "printed"
        flag_exists = _col_exists(flag, acc)
        sub_exists = _col_exists("shipping_subestado", acc)

        if val == 1:
            if flag_exists and sub_exists:
                where.append(f"(ISNULL([{flag}], 0) = 1 OR [shipping_subestado] = ?)")
                args.append(target_sub)
            elif flag_exists:
                where.append(f"ISNULL([{flag}], 0) = 1")
            elif sub_exists:
                where.append("[shipping_subestado] = ?")
                args.append(target_sub)
            else:
                # Sin columnas, no podemos filtrar útilmente
                where.append("1=1")
        else:  # val == 0
            if flag_exists:
                where.append(f"ISNULL([{flag}], 0) = 0")
            elif sub_exists:
                # Equivalente aproximado a flag=0: subestado distinto o NULL
                where.append("([shipping_subestado] IS NULL OR [shipping_subestado] <> ?)")
                args.append(target_sub)
            else:
                where.append("1=1")

    # Si piden ready_to_print=1 y no especifican printed, forzar printed=0 (NULL como 0)
    if str(params.get("ready_to_print")) == "1" and params.get("printed") is None and _col_exists("printed", acc):
        where.append("ISNULL([printed], 0) = 0")

    # deposito_asignado_in: CSV -> WHERE deposito_asignado IN (...)
    depo_in = params.get("deposito_asignado_in")
    if depo_in:
        # Permite valores separados por coma, ignorando vacíos y espacios
        values = [x.strip() for x in str(depo_in).split(",") if x and x.strip()]
        if values:
            placeholders = ", ".join(["?"] * len(values))
            where.append(f"[deposito_asignado] IN ({placeholders})")
            args.extend(values)

    # rango de fecha en date_created
    desde = params.get("desde")
    hasta = params.get("hasta")
    if desde:
        try:
            dt = datetime.fromisoformat(desde)
            where.append("[date_created] >= ?")
            args.append(dt)
        except Exception:
            pass
    if hasta:
        try:
            dt = datetime.fromisoformat(hasta)
            # Si es solo fecha (YYYY-MM-DD), incluir todo el día
            if len(hasta) == 10 and dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
                dt = dt + timedelta(days=1) - timedelta(microseconds=1)
            where.append("[date_created] <= ?")
            args.append(dt)
        except Exception:
            pass

    # rango de fecha en date_closed
    cerrado_desde = params.get("cerrado_desde")
    cerrado_hasta = params.get("cerrado_hasta")
    if cerrado_desde:
        try:
            dt = datetime.fromisoformat(cerrado_desde)
            where.append("[date_closed] >= ?")
            args.append(dt)
        except Exception:
            pass
    if cerrado_hasta:
        try:
            dt = datetime.fromisoformat(cerrado_hasta)
            if len(cerrado_hasta) == 10 and dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
                dt = dt + timedelta(days=1) - timedelta(microseconds=1)
            where.append("[date_closed] <= ?")
            args.append(dt)
        except Exception:
            pass

    # LIKEs (si existen columnas)
    cols = set(_all_columns(acc))
    q_sku = params.get("q_sku")
    if q_sku and "sku" in cols:
        where.append("[sku] LIKE ?")
        args.append(f"%{q_sku}%")
    q_barcode = params.get("q_barcode")
    if q_barcode and "barcode" in cols:
        where.append("[barcode] LIKE ?")
        args.append(f"%{q_barcode}%")
    q_comentario = params.get("q_comentario")
    if q_comentario and "COMENTARIO" in cols:
        where.append("[COMENTARIO] LIKE ?")
        args.append(f"%{q_comentario}%")
    q_title = params.get("q_title")
    if q_title and "nombre" in cols:
        where.append("[nombre] LIKE ?")
        args.append(f"%{q_title}%")

    # deposito_keywords: CSV de términos para contains (case-insensitive por collation)
    deposito_keywords = params.get("deposito_keywords")
    if deposito_keywords and "deposito_asignado" in cols:
        terms = [t.strip() for t in str(deposito_keywords).split(",") if t.strip()]
        term_wheres: List[str] = []
        for t in terms:
            term_wheres.append("[deposito_asignado] LIKE ?")
            args.append(f"%{t}%")
        if term_wheres:
            where.append("(" + " OR ".join(term_wheres) + ")")

    # include_printed: si 0, filtrar impresas (printed=1); si 1, no filtrar
    include_printed = params.get("include_printed")
    if include_printed is not None and str(include_printed) in ("0", "1") and "printed" in cols:
        if str(include_printed) == "0":
            # printed NULL o 0
            where.append("(ISNULL([printed], 0) = 0)")

    if where:
        return " WHERE " + " AND ".join(where), args
    return "", args


def get_orders_service(
    selected_fields: Optional[List[str]],
    params: Dict[str, Any],
    acc: str = "acc1",
) -> Tuple[List[Dict[str, Any]], int]:
    fields = _validate_fields(selected_fields, acc)
    page = int(params.get("page", 1))
    limit = int(params.get("limit", 200))
    offset = (page - 1) * limit

    where_sql, where_args = _build_filters(params, acc)

    select_cols = ", ".join(f"[{c}]" for c in fields)

    # Ordenamiento seguro
    sort_by = params.get("sort_by") or "id"
    sort_dir = (params.get("sort_dir") or "DESC").upper()
    if sort_dir not in ("ASC", "DESC"):
        sort_dir = "DESC"
    # validar columna
    if sort_by not in _all_columns(acc) and sort_by != "id":
        sort_by = "id"

    sql = f"SELECT {select_cols} FROM {TABLE} WITH (NOLOCK){where_sql} ORDER BY [{sort_by}] {sort_dir} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    count_sql = f"SELECT COUNT(*) FROM {TABLE} WITH (NOLOCK){where_sql}"

    with _get_conn(acc) as cn:
        cur = cn.cursor()
        # Reducir bloqueos y colas de espera por escrituras concurrentes
        try:
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        except Exception:
            pass
        # Timeout opcional para consultas largas
        try:
            cur.timeout = int(os.getenv("DB_QUERY_TIMEOUT", "20"))
        except Exception:
            pass
        # total
        cur.execute(count_sql, *where_args)
        total = cur.fetchone()[0]
        # page
        cur.execute(sql, *where_args, offset, limit)
        rows = cur.fetchall()
        col_names = [c[0] for c in cur.description]

    items: List[Dict[str, Any]] = []
    for r in rows:
        obj = {}
        for i, col in enumerate(col_names):
            obj[col] = r[i]
        # Hardcode/fix: if SKU ends with '--' and barcode is missing/empty, derive barcode from SKU without trailing '--'
        try:
            sku_val = str(obj.get("sku") or "")
            bc_val = obj.get("barcode")
            if (bc_val is None or str(bc_val).strip() == "") and sku_val.endswith("--"):
                obj["barcode"] = sku_val[:-2]
        except Exception:
            pass

        # Computed recommendation: deposito_recomendado (single/split/impossible)
        try:
            # Quantity required
            qty_req = obj.get("qty") if obj.get("qty") is not None else obj.get("quantity")
            qty = int(qty_req) if qty_req is not None else 1
            if qty < 1:
                qty = 1

            # Build availability map from known stock_* columns
            candidates: List[Tuple[str, int]] = []
            def add(code: str, field: str):
                if field in obj:
                    try:
                        v = int(obj.get(field) or 0)
                        if v > 0:
                            candidates.append((code, v))
                    except Exception:
                        pass

            # Priority order (customizable)
            add("DEPO", "stock_dep")
            add("MTGBBPS", "stock_mtgbbps")
            add("MONBAHIA", "stock_monbahia")
            add("MUNDOAL", "stock_mundoal")
            add("MUNDOROC", "stock_mundoroc")
            # EXCLUIDO: MTGCBA no debe usarse para asignación/recomendación
            # add("MTGCBA", "stock_mtgcba")
            add("MTGJBJ", "stock_mtgjbj")
            # NQNSHOP: usar nombre completo (antes se etiquetaba como "NQN")
            add("NQNSHOP", "stock_nqnshop")
            # NQNALB: incluir si existe la columna
            add("NQNALB", "stock_nqnalb")
            add("MTGROCA", "stock_mtgroca")
            add("MTGCOM", "stock_mtgcom")
            add("MUNDOCAB", "stock_mundocab")
            # EXCLUIDO: MDQ no debe usarse para asignación/recomendación
            # add("MDQ", "stock_mdq")

            # Prefer single-depo that can fulfill qty
            single = next(((code, avail) for code, avail in candidates if avail >= qty), None)
            if single:
                obj["deposito_recomendado_tipo"] = "single"
                obj["deposito_recomendado"] = single[0]
                obj["deposito_recomendado_detalle"] = f"{single[0]}: {qty}"
            else:
                # Try split between two depos
                split_found = False
                for i1 in range(len(candidates)):
                    for i2 in range(i1 + 1, len(candidates)):
                        c1, a1 = candidates[i1]
                        c2, a2 = candidates[i2]
                        if a1 + a2 >= qty:
                            n1 = min(a1, qty)
                            n2 = qty - n1
                            obj["deposito_recomendado_tipo"] = "split"
                            obj["deposito_recomendado"] = f"{c1}+{c2}"
                            obj["deposito_recomendado_detalle"] = f"{c1}: {n1}, {c2}: {n2}"
                            split_found = True
                            break
                    if split_found:
                        break
                if not split_found:
                    obj["deposito_recomendado_tipo"] = "impossible"
                    obj["deposito_recomendado"] = "IMPOSSIBLE"
                    obj["deposito_recomendado_detalle"] = "sin stock suficiente"
        except Exception:
            # Do not block listing if computation fails
            pass

        # One-time notification when DEBE_PARTIRSE == 1
        try:
            debe = obj.get("DEBE_PARTIRSE")
            order_id = obj.get("order_id")
            if debe == 1 and order_id:
                if not _was_split_notified(str(order_id), acc):
                    sku = str(obj.get("sku") or obj.get("seller_sku") or "")
                    nombre = str(obj.get("nombre") or obj.get("ARTICULO") or "")
                    msg = f"ALERTA: Orden {order_id} requiere PARTIRSE. SKU {sku}. {nombre[:100]}"
                    ok = _send_callmebot_message(msg)
                    if ok:
                        _mark_split_notified(str(order_id), acc)
        except Exception:
            # never break the listing
            pass
        # Add computed account indicator for UI
        try:
            obj["meli_account"] = acc
        except Exception:
            pass
        items.append(obj)

    return items, total


def update_order_service(order_id: int, update, acc: str = "acc1") -> int:
    allowed = set(get_allowed_update_fields())
    updates: Dict[str, Any] = {}

    for field, value in update.dict().items():
        # aplicar solo si viene valor y la columna existe en la base (evita errores 207)
        if value is not None and field in allowed and _col_exists(field, acc):
            # normalizar valores booleanos a 0/1 para columnas int
            if field in ("printed", "ready_to_print", "CAMBIO_ESTADO", "MOV_LOCAL_HECHO"):
                try:
                    iv = int(value)
                    updates[field] = 1 if iv == 1 else 0
                except Exception:
                    updates[field] = 1 if str(value).lower() in ("1","true","yes") else 0
            elif field == "deposito_asignado":
                # Bloquear asignación a MTGCBA
                try:
                    if str(value).strip().upper() == "MTGCBA":
                        continue  # no aplicar este cambio
                except Exception:
                    pass
                updates[field] = _truncate_to_column(field, value, acc)
            else:
                # Truncar strings a tamaño de columna cuando corresponda (evita 2628)
                updates[field] = _truncate_to_column(field, value, acc)

    if not updates:
        return 0

    # Regla de exclusión: printed y ready_to_print no pueden ser 1 a la vez
    if "printed" in updates and updates["printed"] == 1:
        updates["ready_to_print"] = 0
        # Liberar stock_reservado cuando se marca como printed
        updates["stock_reservado"] = 0
    if "ready_to_print" in updates and updates["ready_to_print"] == 1:
        updates["printed"] = 0

    set_parts = [f"[{k}] = ?" for k in updates.keys()]
    args = list(updates.values()) + [order_id]

    # Si se marcó movimiento de depósito y existe la columna mov_depo_ts, sellar timestamp una sola vez (idempotente)
    mov_flag = None
    try:
        if "mov_depo_hecho" in updates and _col_exists("mov_depo_ts", acc):
            mov_flag = 1 if int(updates.get("mov_depo_hecho") or 0) == 1 else 0
    except Exception:
        mov_flag = 1 if str(updates.get("mov_depo_hecho")).lower() in ("1","true","yes") else 0 if "mov_depo_hecho" in updates else None
    if mov_flag is not None and _col_exists("mov_depo_ts", acc):
        set_parts.append("[mov_depo_ts] = CASE WHEN (?=1) AND ([mov_depo_ts] IS NULL) THEN SYSUTCDATETIME() ELSE [mov_depo_ts] END")
        args = list(updates.values()) + [mov_flag, order_id]

    # Timestamp para MOV_LOCAL_TS si existe y se marca MOV_LOCAL_HECHO
    local_flag = None
    try:
        if "MOV_LOCAL_HECHO" in updates and _col_exists("MOV_LOCAL_TS", acc):
            local_flag = 1 if int(updates.get("MOV_LOCAL_HECHO") or 0) == 1 else 0
    except Exception:
        local_flag = 1 if str(updates.get("MOV_LOCAL_HECHO")).lower() in ("1","true","yes") else 0 if "MOV_LOCAL_HECHO" in updates else None
    if local_flag is not None and _col_exists("MOV_LOCAL_TS", acc):
        set_parts.append("[MOV_LOCAL_TS] = CASE WHEN (?=1) AND ([MOV_LOCAL_TS] IS NULL) THEN SYSUTCDATETIME() ELSE [MOV_LOCAL_TS] END")
        args = list(updates.values()) + [local_flag, order_id]

    # Usar clave primaria [id] como target del WHERE: los endpoints resuelven a id numérico
    sql = f"UPDATE {TABLE} SET {', '.join(set_parts)} WHERE [id] = ?"

    with _get_conn(acc) as cn:
        cur = cn.cursor()
        # Intento 1: actualizar por order_id
        cur.execute(sql, *args)
        cn.commit()
        affected = cur.rowcount
        # Fallback anterior por pack_id se deshabilita para evitar conversiones implícitas problemáticas
        # ya que el parámetro proviene como id numérico.
        if affected == 0:
            return 0
        return affected


def update_order_by_order_or_pack(order_or_pack: str, update, acc: str = "acc1") -> int:
    """Fallback updater: applies the same whitelist/column-exists logic as update_order_service,
    but targets rows by textual [order_id] OR [pack_id]. Useful when the caller only has the ML order id
    and internal id resolution is unreliable.
    """
    allowed = set(get_allowed_update_fields())
    updates: Dict[str, Any] = {}

    for field, value in update.dict().items():
        if value is not None and field in allowed and _col_exists(field, acc):
            if field in ("printed", "ready_to_print", "CAMBIO_ESTADO", "MOV_LOCAL_HECHO"):
                try:
                    iv = int(value)
                    updates[field] = 1 if iv == 1 else 0
                except Exception:
                    updates[field] = 1 if str(value).lower() in ("1","true","yes") else 0
            elif field == "deposito_asignado":
                try:
                    if str(value).strip().upper() == "MTGCBA":
                        continue
                except Exception:
                    pass
                updates[field] = _truncate_to_column(field, value, acc)
            else:
                updates[field] = _truncate_to_column(field, value, acc)

    if not updates:
        return 0

    # Exclusión entre printed y ready_to_print
    if "printed" in updates and updates["printed"] == 1:
        updates["ready_to_print"] = 0
        updates["stock_reservado"] = 0
    if "ready_to_print" in updates and updates["ready_to_print"] == 1:
        updates["printed"] = 0

    set_parts = [f"[{k}] = ?" for k in updates.keys()]
    args = list(updates.values()) + [str(order_or_pack), str(order_or_pack)]

    # Sello de mov_depo_ts si corresponde
    mov_flag = None
    try:
        if "mov_depo_hecho" in updates and _col_exists("mov_depo_ts", acc):
            mov_flag = 1 if int(updates.get("mov_depo_hecho") or 0) == 1 else 0
    except Exception:
        mov_flag = 1 if str(updates.get("mov_depo_hecho")).lower() in ("1","true","yes") else 0 if "mov_depo_hecho" in updates else None
    if mov_flag is not None and _col_exists("mov_depo_ts", acc):
        set_parts.append("[mov_depo_ts] = CASE WHEN (?=1) AND ([mov_depo_ts] IS NULL) THEN SYSUTCDATETIME() ELSE [mov_depo_ts] END")
        args = list(updates.values()) + [mov_flag, str(order_or_pack), str(order_or_pack)]

    # Sello de MOV_LOCAL_TS si corresponde
    local_flag = None
    try:
        if "MOV_LOCAL_HECHO" in updates and _col_exists("MOV_LOCAL_TS", acc):
            local_flag = 1 if int(updates.get("MOV_LOCAL_HECHO") or 0) == 1 else 0
    except Exception:
        local_flag = 1 if str(updates.get("MOV_LOCAL_HECHO")).lower() in ("1","true","yes") else 0 if "MOV_LOCAL_HECHO" in updates else None
    if local_flag is not None and _col_exists("MOV_LOCAL_TS", acc):
        set_parts.append("[MOV_LOCAL_TS] = CASE WHEN (?=1) AND ([MOV_LOCAL_TS] IS NULL) THEN SYSUTCDATETIME() ELSE [MOV_LOCAL_TS] END")
        args = list(updates.values()) + [local_flag, str(order_or_pack), str(order_or_pack)]

    # Target por order_id o pack_id (texto)
    sql = f"UPDATE {TABLE} SET {', '.join(set_parts)} WHERE [order_id] = ? OR [pack_id] = ?"

    with _get_conn(acc) as cn:
        cur = cn.cursor()
        cur.execute(sql, *args)
        cn.commit()
        return cur.rowcount or 0
