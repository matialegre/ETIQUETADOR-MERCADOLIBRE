"""
Módulo 07: Dragon API - Consulta de stock por depósito
=====================================================

Consulta stock en API Dragonfish y maneja timeouts/errores.
"""

import logging
import requests
from typing import Dict, Optional
import re
from modules.config import (
    DRAGON_API_BASE,
    DRAGON_API_BASES,
    DRAGON_API_KEY,
    DRAGON_ID_CLIENTE,
    DRAGON_ALT_API_BASES,
    DRAGON_ALT_API_KEY,
    DRAGON_ALT_ID_CLIENTE,
    DRAGON_DEPOT_CANDIDATES,
)

logger = logging.getLogger(__name__)

# Track last method used to feed GUI/assigners (API|SQL)
_LAST_METHOD = "API"

def get_last_method() -> str:
    return _LAST_METHOD


def _norm(s: Optional[str]) -> str:
    s2 = str(s or '').strip().upper()
    return re.sub(r"[^A-Z0-9]", "", s2)


def _eq_talle(a: str, b: str) -> bool:
    # Igualar '3', '03', '003', etc. y variantes con letras
    a_n = a.lstrip('0') or '0'
    b_n = b.lstrip('0') or '0'
    return a == b or a_n == b_n


def get_stock_per_deposit(sku: str, timeout: int = 30) -> Dict[str, Dict[str, int]]:
    """
    Consulta stock por depósito en API Dragonfish.
    
    Args:
        sku: SKU a consultar
        timeout: Timeout en segundos
        
    Returns:
        Dict con formato: {'DEP1': {'total': 10, 'reserved': 2}, ...}
        
    Raises:
        requests.Timeout: Si la consulta supera el timeout
        requests.HTTPError: Si hay error HTTP
    """
    # Construir listas de bases/credenciales en orden de preferencia (primaria → alternativa)
    global _LAST_METHOD
    bases_all = []
    if DRAGON_API_BASES:
        bases_all.extend(DRAGON_API_BASES)
    if DRAGON_ALT_API_BASES:
        for b in DRAGON_ALT_API_BASES:
            if b and b not in bases_all:
                bases_all.append(b)

    cred_options = [
        {
            "IdCliente": DRAGON_ID_CLIENTE or "",
            "Authorization": DRAGON_API_KEY or "",
        },
    ]
    if DRAGON_ALT_ID_CLIENTE or DRAGON_ALT_API_KEY:
        cred_options.append({
            "IdCliente": DRAGON_ALT_ID_CLIENTE or DRAGON_ID_CLIENTE or "",
            "Authorization": DRAGON_ALT_API_KEY or DRAGON_API_KEY or "",
        })

    # Derivar ARTÍCULO BASE para la consulta (antes del primer '-')
    # Ej: 'NWQRDHBRDV-VCF-04' -> 'NWQRDHBRDV'
    s_in = (sku or '').strip()
    if s_in.upper().startswith('TDRK20'):
        query_val = 'TDRK20'
    else:
        query_val = s_in.split('-')[0] if '-' in s_in else s_in
    # Intentar extraer color/talle de SKU completo (ART-COLOR-TALLE)
    parts = s_in.split('-')
    color_q = parts[1].strip() if len(parts) >= 3 else None
    talle_q = parts[2].strip() if len(parts) >= 3 else None

    # La base debe apuntar a .../ConsultaStockYPreciosEntreLocales
    # 1) Intento principal: ConsultaStockYPreciosEntreLocales (sin BaseDeDatos)
    last_exc: Optional[Exception] = None
    data = None
    entre_locales_worked = False
    for base in bases_all or ([DRAGON_API_BASE] if DRAGON_API_BASE else []):
        if not base:
            continue
        url = base.rstrip("/")
        # Asegurar que el path apunte al recurso EntreLocales si la base termina en ConsultaStockYPrecios
        if url.lower().endswith('/consultastockyprecios'):
            url = url + 'EntreLocales'
        logger.debug(f"Consultando Dragonfish EntreLocales: url={url} params={{'query': '{query_val}', 'page': 1, 'limit': 100}}")
        params = {"query": query_val, "page": 1, "limit": 100}
        for cred in cred_options:
            headers = {
                "accept": "application/json",
                "IdCliente": cred["IdCliente"],
                "Authorization": cred["Authorization"],
            }
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=timeout, allow_redirects=True)
                if resp.status_code in (400, 401, 404, 405):
                    safe_auth = (headers.get("Authorization") or "")[0:6] + "..."
                    logger.warning(f"Dragonfish {resp.status_code} en {url} query={query_val} IdCliente={headers.get('IdCliente')} Auth={safe_auth}")
                    last_exc = requests.HTTPError(f"HTTP {resp.status_code}")
                    continue
                resp.raise_for_status()
                data = resp.json()
                entre_locales_worked = True
                break
            except requests.Timeout as e:
                last_exc = e
                logger.error(f"Timeout consultando stock EntreLocales para {sku} en {url}")
                continue
            except requests.HTTPError as e:
                last_exc = e
                logger.error(f"HTTP error consultando stock EntreLocales para {sku} en {url}: {e}")
                continue
            except Exception as e:
                last_exc = e
                logger.error(f"Error inesperado consultando stock EntreLocales en {url}: {e}")
                continue
        if entre_locales_worked:
            break

    # Si EntreLocales no funcionó, fallback a SQL directo (pyodbc)
    if not entre_locales_worked:
        try:
            res_sql = _get_stock_per_deposit_sql(sku)
            if res_sql:
                _LAST_METHOD = "SQL"
                logger.info("Stock por SQL para %s: %s", sku, res_sql)
                return res_sql
        except Exception as e:
            logger.warning("Fallback SQL falló para %s: %s", sku, e)
        # Si no, propagar el último error si existió
        if last_exc:
            raise last_exc
        raise requests.HTTPError("Dragonfish EntreLocales y SQL sin resultados")

    # Parsear estructura Dragonfish: Resultados[...].Stock[{ BaseDeDatos, Stock }]
    result: Dict[str, Dict[str, int]] = {}
    # Lista blanca de bases permitidas (nombres crudos tal como vienen en JSON)
    allowed_raw = {
        'DEPOSITO',
        'MONBAHIA',
        'MTGBBPS',
        'BBPS',  # alias histórico, se mapea a MTGBBPS
        'MTGROCA',
        'MUNDOAL',
        'MUNDOCAB',
        'MUNDOROC',
        'NQNALB',
    }
    try:
        resultados = data.get("Resultados") if isinstance(data, dict) else None
        if not isinstance(resultados, list):
            # Si no viene en el formato esperado, registrar y devolver vacío
            logger.debug("Respuesta Dragonfish sin 'Resultados' lista")
            return result
        # Filtrar por artículo exacto y, si se provee, por Color/Talle
        query_art = (query_val or '').strip().upper()
        color_norm = _norm(color_q) if color_q else None
        talle_norm = _norm(talle_q) if talle_q else None
        for item in resultados:
            if not isinstance(item, dict):
                continue
            art = str(item.get('Articulo', '')).strip().upper()
            if art != query_art:
                # Ignorar otros artículos para evitar contaminar el stock
                continue
            # Si se especificó variante, filtrar por Color/Talle
            if color_norm or talle_norm:
                it_color = _norm(item.get('Color') or item.get('COLOR') or item.get('color'))
                it_talle = _norm(item.get('Talle') or item.get('TALLE') or item.get('talle'))
                color_ok = (color_norm is None) or (it_color == color_norm)
                talle_ok = (talle_norm is None) or _eq_talle(it_talle, talle_norm)
                if not (color_ok and talle_ok):
                    continue
            stocks = item.get("Stock", []) if isinstance(item, dict) else []
            for s in stocks:
                depot_raw = str(s.get("BaseDeDatos", "")).strip().upper()
                if not depot_raw:
                    continue
                # Ignorar bases no permitidas
                if depot_raw not in allowed_raw:
                    continue
                # Mapear nombre interno: DEPOSITO -> DEP, BBPS -> MTGBBPS
                if depot_raw == 'DEPOSITO':
                    depot = 'DEP'
                elif depot_raw == 'BBPS':
                    depot = 'MTGBBPS'
                else:
                    depot = depot_raw
                total = int(s.get("Stock") or 0)
                cur = result.get(depot, {"total": 0, "reserved": 0})
                # Usar el mayor total reportado por seguridad (si vinieran múltiples líneas por depósito)
                cur["total"] = max(cur["total"], total)
                result[depot] = cur
    except Exception as e:
        logger.error(f"Error parseando respuesta Dragonfish para {sku}: {e}")
        return {}

    logger.debug(f"Stock por depósito obtenido para {sku}: {result}")
    _LAST_METHOD = "API"
    return result

def _get_stock_per_deposit_sql(sku: str) -> Dict[str, Dict[str, int]]:
    """Consulta stock por depósito usando SQL Server (pyodbc), sumando todas las bases DRAGONFISH_*
    que estén ONLINE, excluyendo las bases especiales comunes.
    Retorna {'DEPOT': {'total': X, 'reserved': 0}, ...}
    """
    try:
        import os, pyodbc
        conn_str = os.getenv('DRAGON_SQL_CONN_STR')
        if not conn_str:
            raise RuntimeError('DRAGON_SQL_CONN_STR no configurado')
        art, col, tal = sku.split('-', 2) if '-' in sku else (sku, '', '')
        sql_tpl = (
            "SELECT RTRIM(BDALTAFW) AS dep, SUM(COCANT) "
            "FROM   [{base}].[ZooLogic].[COMB] "
            "WHERE  RTRIM(COART)=? AND RTRIM(COCOL)=? AND RTRIM(TALLE)=? "
            "GROUP BY BDALTAFW HAVING SUM(COCANT)<>0"
        )
        exclude = {'MELI','ADMIN','WOO','TN'}
        res: Dict[str, Dict[str, int]] = {}
        with pyodbc.connect(conn_str, autocommit=True) as con:
            cur = con.cursor()
            bases = [
                n for (n,) in cur.execute(
                    "SELECT name FROM sys.databases WHERE name LIKE 'DRAGONFISH_%' AND state_desc='ONLINE'"
                )
                if not any(bad in n.upper() for bad in exclude)
            ]
            for base in bases:
                try:
                    rows = cur.execute(sql_tpl.format(base=base), art, col, tal).fetchall()
                    for dep, qty in rows:
                        dep_up = str(dep).strip().upper()
                        total_prev = int((res.get(dep_up) or {}).get('total') or 0)
                        res[dep_up] = {'total': total_prev + int(qty), 'reserved': 0}
                except Exception:
                    continue
        return res
    except Exception as e:
        logger.warning(f"SQL fallback error para {sku}: {e}")
        return {}


def get_stock_per_deposit_paged(sku: str, timeout: int = 30, max_pages: int = 10) -> Dict[str, Dict[str, int]]:
    """
    Variante paginada: itera páginas si la API lo indica.

    Detecta indicadores comunes de "siguiente" en JSON o headers y agrega resultados
    de todas las páginas hasta completar o alcanzar max_pages.

    No modifica el contrato: retorna el mismo dict que get_stock_per_deposit.
    """
    url = f"{DRAGON_API_BASE}/stock/{sku}"
    headers = {"Authorization": f"Bearer {DRAGON_API_KEY}"}

    aggregated: Dict[str, Dict[str, int]] = {}
    page = 1
    next_url: Optional[str] = None

    for _ in range(max_pages):
        params = None
        request_url = next_url or url
        if next_url is None:
            params = {"page": page}
        try:
            resp = requests.get(request_url, headers=headers, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()

            # Unificar depósitos de esta página
            if isinstance(data, dict):
                page_items = data
            else:
                # Si la API devuelve una lista, convertir al formato esperado si es posible
                page_items = {}
                for item in data:
                    depot = item.get('deposito') or item.get('BaseDeDatos') or item.get('depot')
                    total = item.get('total') or item.get('Total') or item.get('stock') or 0
                    reserved = item.get('reserved') or item.get('Reservado') or 0
                    if depot:
                        depot_up = str(depot).strip().upper()
                        cur = aggregated.get(depot_up, {"total": 0, "reserved": 0})
                        cur["total"] += int(total or 0)
                        cur["reserved"] += int(reserved or 0)
                        aggregated[depot_up] = cur

            # Si vino dict del mismo contrato estándar, agregar por clave
            if isinstance(data, dict):
                for depot, vals in data.items():
                    cur = aggregated.get(depot, {"total": 0, "reserved": 0})
                    cur["total"] += int(vals.get("total", 0))
                    cur["reserved"] += int(vals.get("reserved", 0))
                    aggregated[depot] = cur

            # Heurística de paginación
            has_next = False
            # 1) En JSON
            if isinstance(data, dict):
                # Caso explícito Dragonfish: 'Siguiente' trae URL absoluta
                siguiente = data.get('Siguiente') or data.get('siguiente')
                if isinstance(siguiente, str) and siguiente.strip():
                    has_next = True
                    next_url = siguiente.strip()
                else:
                    next_url = None
                if data.get('next') or data.get('has_next') or data.get('PaginaSiguiente') or data.get('pagina_siguiente'):
                    has_next = True
                # Links estilo RFC5988
                links = data.get('links') or {}
                if isinstance(links, dict) and (links.get('next') or links.get('siguiente')):
                    has_next = True
            # 2) En headers
            if resp.headers.get('X-Next-Page') or resp.headers.get('Link', '').find('rel="next"') != -1:
                has_next = True

            if not has_next:
                break

            # Si no vino URL en 'Siguiente', avanzar por page param
            if not next_url:
                page += 1

        except requests.Timeout as e:
            logger.error(f"Timeout consultando stock paginado para {sku} page={page}: {e}")
            raise
        except requests.HTTPError as e:
            logger.error(f"HTTPError en paginado stock {sku} page={page}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado en paginado stock {sku} page={page}: {e}")
            raise

    return aggregated

if __name__ == "__main__":
    # Test básico
    import sys
    logging.basicConfig(level=logging.DEBUG)
    
    test_sku = "2027201-CC089-C10"  # SKU de prueba
    
    try:
        stock = get_stock_per_deposit(test_sku, timeout=60)
        print(f"✅ Stock obtenido para {test_sku}:")
        
        for depot, data in stock.items():
            total = data.get('total', 0)
            reserved = data.get('reserved', 0)
            available = total - reserved
            print(f"   🏪 {depot}: Total={total}, Reservado={reserved}, Disponible={available}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
