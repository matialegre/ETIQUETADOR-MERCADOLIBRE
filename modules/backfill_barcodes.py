"""
Backfill de barcodes (preferido + todos los alias) sin migraciones grandes.

- Lee órdenes recientes de orders_meli que no tienen barcode_all o barcode vacío
- Para cada SKU en formato ART-COLOR-TALLE, consulta Dragonfish (ZooLogic.EQUI)
  y arma:
    * preferred: primer CCODIGO que empiece con dígito; si no hay, el más largo
    * barcode_all: JSON array con todos los CCODIGO en el orden de preferencia
- Actualiza orders_meli (barcode, barcode_all)

Config requerida:
- modules.config.SQLSERVER_CONN_STR: conexión a Dragonfish (DB con schema ZooLogic)
- PIPELINE_5_CONSOLIDADO.database_utils.get_connection_for_meli(): conexión app (orders_meli)
"""
from __future__ import annotations
import json
import os
from typing import Optional, Tuple, List

import pyodbc

# Conexión Dragonfish
try:
    from .config import SQLSERVER_CONN_STR
except Exception:
    SQLSERVER_CONN_STR = None  # type: ignore

# Conexión App (orders_meli)
try:
    from PIPELINE_5_CONSOLIDADO.database_utils import get_connection_for_meli
except Exception as e:  # pragma: no cover
    raise RuntimeError(f"No se pudo importar get_connection_for_meli: {e}")


def _dragon_connect() -> pyodbc.Connection:
    conn_str = SQLSERVER_CONN_STR
    if not conn_str:
        raise RuntimeError("SQLSERVER_CONN_STR no configurado (modules/config.py o .env)")
    return pyodbc.connect(conn_str)


def _prefer_order_sql() -> str:
    # Orden: primero los que inician con dígito, luego más largo
    return "CASE WHEN equi.CCODIGO LIKE '[0-9]%' THEN 0 ELSE 1 END, LEN(RTRIM(equi.CCODIGO)) DESC"


def _split_sku(sku: str) -> Optional[Tuple[str, str, str]]:
    if not sku or sku.count('-') < 2:
        return None
    try:
        p = sku.split('-', 2)
        art = p[0].strip()
        col = p[1].strip()
        tal = p[2].strip()
        if not art or not col or not tal:
            return None
        return art, col, tal
    except Exception:
        return None


def _fetch_barcodes_for_sku(art: str, col: str, tal: str) -> Tuple[Optional[str], List[str]]:
    """Consulta Dragonfish.EQUI y devuelve (preferred, all_list)."""
    sql = (
        "SELECT RTRIM(equi.CCODIGO) AS cc "
        "FROM ZooLogic.EQUI AS equi "
        "WHERE RTRIM(equi.CARTICUL)=? AND RTRIM(equi.CCOLOR)=? AND RTRIM(equi.CTALLE)=? "
        f"ORDER BY {_prefer_order_sql()}"
    )
    all_codes: List[str] = []
    preferred: Optional[str] = None
    with _dragon_connect() as cn:
        cur = cn.cursor()
        cur.execute(sql, (art, col, tal))
        rows = cur.fetchall() or []
        for r in rows:
            c = (r[0] or "").strip()
            if not c:
                continue
            all_codes.append(c)
        if all_codes:
            preferred = all_codes[0]
    return preferred, all_codes


def backfill_barcode_all(max_rows: int = 100, days_window: int = 60, account: Optional[str] = None) -> int:
    """Completa barcode_all y barcode preferido para órdenes recientes.

    Args:
        max_rows: tope de órdenes a actualizar por ejecución
        days_window: ventana de días hacia atrás para buscar órdenes
        account: id de cuenta ML (routeo opcional). Si None, usa default del helper.

    Returns:
        cantidad de órdenes actualizadas
    """
    updated = 0
    # 1) Seleccionar candidatos desde la app
    with get_connection_for_meli(account) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT TOP (?) id, sku
            FROM orders_meli WITH (NOLOCK)
            WHERE sku LIKE '%-%-%' -- ART-COLOR-TALLE
              AND (barcode_all IS NULL OR LTRIM(RTRIM(COALESCE(barcode_all,''))) = '')
              AND (date_created IS NULL OR date_created >= DATEADD(day, -?, GETDATE()))
            ORDER BY id DESC
            """,
            (int(max_rows), int(days_window)),
        )
        rows = cur.fetchall() or []
        for rid, sku in rows:
            try:
                parts = _split_sku(str(sku or ""))
                if not parts:
                    continue
                art, col, tal = parts
                preferred, all_codes = _fetch_barcodes_for_sku(art, col, tal)
                if not all_codes:
                    continue
                barcode_all_json = json.dumps(all_codes, ensure_ascii=False)
                # Actualizar registro
                cur.execute(
                    "UPDATE orders_meli SET barcode = COALESCE(?, barcode), barcode_all = ?, fecha_actualizacion = GETDATE() WHERE id = ?",
                    (preferred, barcode_all_json, int(rid)),
                )
                conn.commit()
                updated += 1
            except Exception:
                # no interrumpir por una orden fallida
                continue
    return updated


if __name__ == "__main__":
    # Ejecución manual rápida
    n = backfill_barcode_all(max_rows=50, days_window=90)
    print(f"Actualizadas: {n}")
