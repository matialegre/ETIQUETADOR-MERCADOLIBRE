import os
import sys
import argparse
import json
from typing import Any, Dict, Optional, Tuple

import pyodbc

# Reusar misma config que 02_dragon_db.py
try:
    from .config import SQLSERVER_CONN_STR
except Exception:  # ejecución directa
    sys.path.append(os.path.dirname(__file__))
    from config import SQLSERVER_CONN_STR  # type: ignore


def _connect() -> pyodbc.Connection:
    conn_str = SQLSERVER_CONN_STR
    if not conn_str:
        raise RuntimeError("SQLSERVER_CONN_STR no configurado en modules/config.py o .env")
    return pyodbc.connect(conn_str)


SCHEMA_CANDIDATES = ("ZooLogic", "zoologic", "dbo")

def _pick_schema_for_table(conn: pyodbc.Connection, table: str) -> str:
    """Devuelve un esquema válido que contenga la tabla dada. Fallback: 'ZooLogic'."""
    table_u = (table or '').strip()
    try:
        cur = conn.cursor()
        # Buscar cualquier esquema donde exista la tabla (case-insensitive)
        cur.execute(
            "SELECT TOP 1 TABLE_SCHEMA FROM INFORMATION_SCHEMA.TABLES WHERE UPPER(TABLE_NAME) = UPPER(?)",
            table_u,
        )
        row = cur.fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception:
        pass
    # Probar candidatos comunes como fallback
    for sch in SCHEMA_CANDIDATES:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA=? AND UPPER(TABLE_NAME)=UPPER(?)",
                sch,
                table_u,
            )
            if cur.fetchone():
                return sch
        except Exception:
            continue
    return "ZooLogic"


def _query_article_by_components(conn: pyodbc.Connection, art: str, col: str, tal: str) -> Optional[Dict[str, Any]]:
    sch_equi = _pick_schema_for_table(conn, "EQUI")
    sch_art = _pick_schema_for_table(conn, "ART")
    sql = (
        "SELECT RTRIM(equi.CCOLOR) AS CODIGO_COLOR, RTRIM(equi.CTALLE) AS CODIGO_TALLE, "
        "RTRIM(equi.CARTICUL) AS CODIGO_ARTICULO, RTRIM(equi.CCODIGO) AS CODIGO_BARRA, "
        "RTRIM(c_art.ARTDES) AS ARTDES "
        f"FROM {sch_equi}.EQUI AS equi "
        f"LEFT JOIN {sch_art}.ART AS c_art ON equi.CARTICUL = c_art.ARTCOD "
        "WHERE RTRIM(equi.CARTICUL) = ? AND RTRIM(equi.CCOLOR) = ? AND RTRIM(equi.CTALLE) = ?"
    )
    cur = conn.cursor()
    cur.execute(sql, (art, col, tal))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "CODIGO_COLOR": (row[0].strip() if row[0] is not None else ""),
        "CODIGO_TALLE": (row[1].strip() if row[1] is not None else ""),
        "CODIGO_ARTICULO": (row[2].strip() if row[2] is not None else ""),
        "CODIGO_BARRA": (row[3].strip() if row[3] is not None else ""),
        "ARTDES": (row[4].strip() if row[4] is not None else ""),
    }


def _query_article_by_barcode(conn: pyodbc.Connection, barcode: str) -> Optional[Dict[str, Any]]:
    sch_equi = _pick_schema_for_table(conn, "EQUI")
    sch_art = _pick_schema_for_table(conn, "ART")
    sql = (
        "SELECT RTRIM(equi.CCOLOR) AS CODIGO_COLOR, RTRIM(equi.CTALLE) AS CODIGO_TALLE, "
        "RTRIM(equi.CARTICUL) AS CODIGO_ARTICULO, RTRIM(equi.CCODIGO) AS CODIGO_BARRA, "
        "RTRIM(c_art.ARTDES) AS ARTDES "
        f"FROM {sch_equi}.EQUI AS equi "
        f"LEFT JOIN {sch_art}.ART AS c_art ON equi.CARTICUL = c_art.ARTCOD "
        "WHERE RTRIM(equi.CCODIGO) = ?"
    )
    cur = conn.cursor()
    cur.execute(sql, (barcode.strip(),))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "CODIGO_COLOR": (row[0].strip() if row[0] is not None else ""),
        "CODIGO_TALLE": (row[1].strip() if row[1] is not None else ""),
        "CODIGO_ARTICULO": (row[2].strip() if row[2] is not None else ""),
        "CODIGO_BARRA": (row[3].strip() if row[3] is not None else ""),
        "ARTDES": (row[4].strip() if row[4] is not None else ""),
    }


def _query_stock_by_components(conn: pyodbc.Connection, art: str, col: str, tal: str) -> Dict[str, Any]:
    """Devuelve disponibilidad por depósito desde STOCKS."""
    out: Dict[str, Any] = {"depositos": []}
    sch_stk = _pick_schema_for_table(conn, "STOCKS")
    sql = (
        "SELECT RTRIM(CDEPOSIT) AS deposito, ISNULL(NSTOCK,0) AS stock, ISNULL(NRESERVA,0) AS reserva, DFECHA "
        f"FROM {sch_stk}.STOCKS "
        "WHERE RTRIM(CARTICUL) = ? AND RTRIM(CCOLOR) = ? AND RTRIM(CTALLE) = ?"
    )
    cur = conn.cursor()
    cur.execute(sql, (art, col, tal))
    rows = cur.fetchall() or []
    for r in rows:
        out["depositos"].append({
            "deposito": (r[0].strip() if r[0] is not None else ""),
            "stock_actual": int(r[1] or 0),
            "stock_reservado": int(r[2] or 0),
            "fecha_actualizacion": r[3].isoformat() if r[3] is not None else None,
        })
    out["stock_total"] = sum(d["stock_actual"] for d in out["depositos"]) if out["depositos"] else 0
    return out


def resolve_details(sku: Optional[str], barcode: Optional[str]) -> Dict[str, Any]:
    if not sku and not barcode:
        raise ValueError("Debe proporcionar --sku o --barcode")

    # Normalizar SKU con dashes: permitir variantes como NMIDKUDEVD-MTP-T39 o NMIDKUDEVD-MTP-39
    def _norm_sku(s: str) -> str:
        s = (s or "").strip()
        return s

    with _connect() as cn:
        base: Optional[Dict[str, Any]] = None
        used = None
        art = col = tal = None

        if sku and '-' in sku and len(sku.split('-', 2)) >= 3:
            sku_n = _norm_sku(sku)
            parts = sku_n.split('-', 2)
            art, col, tal = parts[0].strip(), parts[1].strip(), parts[2].strip()
            base = _query_article_by_components(cn, art, col, tal)
            used = {"mode": "by_components", "sku": sku_n}
        elif barcode:
            base = _query_article_by_barcode(cn, barcode)
            used = {"mode": "by_barcode", "barcode": barcode}
        else:
            # SKU sin guiones: intentar como barcode directo
            base = _query_article_by_barcode(cn, sku or "")
            used = {"mode": "by_barcode_from_sku", "barcode": sku}

        if not base:
            return {"found": False, "used": used}

        # Completar componentes si no vinieron
        art = art or base.get("CODIGO_ARTICULO")
        col = col or base.get("CODIGO_COLOR")
        tal = tal or base.get("CODIGO_TALLE")

        stock = _query_stock_by_components(cn, art or "", col or "", tal or "")

        result = {
            "found": True,
            "used": used,
            "CODIGO_BARRA": base.get("CODIGO_BARRA"),
            "CODIGO_ARTICULO": art,
            "CODIGO_COLOR": col,
            "CODIGO_TALLE": tal,
            "ARTDES": base.get("ARTDES"),
            "SKU_FORMADO": f"{art}-{col}-{tal}",
            "stock": stock,
        }
        return result


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Resolver detalles de artículo por SKU o barcode (Dragonfish SQL)")
    parser.add_argument("--sku", type=str, help="SKU en formato ART-COLOR-TALLE (o SKU ML)")
    parser.add_argument("--barcode", type=str, help="Código de barras físico")
    parser.add_argument("--json", action="store_true", help="Salida JSON limpia")
    parser.add_argument("--inspect", action="store_true", help="Inspeccionar conexión y ubicar tablas EQUI/ART/STOCKS")

    args = parser.parse_args(argv)
    try:
        if args.inspect:
            with _connect() as cn:
                cur = cn.cursor()
                # Mostrar DB y servidor actual
                try:
                    cur.execute("SELECT DB_NAME() AS db, @@SERVERNAME AS server")
                    row = cur.fetchone()
                    print(json.dumps({"db": row[0], "server": row[1]}, ensure_ascii=False))
                except Exception:
                    pass
                # Listar schemas
                try:
                    cur.execute("SELECT name FROM sys.schemas ORDER BY name")
                    schemas = [r[0] for r in cur.fetchall()]
                except Exception:
                    schemas = []
                # Buscar tablas candidatas
                try:
                    cur.execute(
                        "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE UPPER(TABLE_NAME) IN ('EQUI','ART','STOCKS') ORDER BY TABLE_SCHEMA, TABLE_NAME"
                    )
                    exact = [{"schema": r[0], "table": r[1]} for r in cur.fetchall()]
                except Exception:
                    exact = []
                try:
                    cur.execute(
                        "SELECT TOP 50 TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%EQ%' OR TABLE_NAME LIKE '%EQUI%' OR TABLE_NAME LIKE '%ART%' OR TABLE_NAME LIKE '%STOCK%' ORDER BY TABLE_SCHEMA, TABLE_NAME"
                    )
                    fuzzy = [{"schema": r[0], "table": r[1]} for r in cur.fetchall()]
                except Exception:
                    fuzzy = []
                out = {"schemas": schemas, "exact_tables": exact, "fuzzy_tables": fuzzy}
                print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0

        data = resolve_details(args.sku, args.barcode)
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            if not data.get("found"):
                print("❌ No encontrado", json.dumps(data, ensure_ascii=False))
                return 1
            print("✅ Encontrado")
            print(f"  SKU_FORMADO: {data['SKU_FORMADO']}")
            print(f"  CODIGO_BARRA: {data['CODIGO_BARRA']}")
            print(f"  ARTDES: {data.get('ARTDES','')}")
            print("  STOCK POR DEPÓSITO:")
            for d in data["stock"].get("depositos", []):
                print(f"    - {d['deposito']}: disp={d['stock_actual']} res={d['stock_reservado']} fecha={d['fecha_actualizacion']}")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
