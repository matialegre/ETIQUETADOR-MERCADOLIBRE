"""
PIPELINE 10 ESTABLE
===================

Loop estable que:
- Sincroniza últimas ventas reales desde MercadoLibre (PIPELINE 5).
- Asigna depósitos y ejecuta movimiento WOO→WOO (PASO 08), con idempotencia.
- Hace backfill de columnas de stock por depósito (visibilidad).

Config clave:
- MOVIMIENTO_TARGET (WOO|MELI) controla BaseDeDatos y OrigenDestino.
- SLEEP_BETWEEN_CYCLES (segundos) define el intervalo entre ciclos.

Uso:
  python PIPELINE_10_ESTABLE/main.py --limit 50 --interval 60

"""
from __future__ import annotations
import argparse
import importlib.util
import logging
import os
import sys
import time
from typing import Optional, Set, Iterable
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

# Rutas base
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../PIPELINE_7_FULL
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Imports de módulos existentes (reutilizados)
try:
    from PIPELINE_5_CONSOLIDADO.PIPELINE_5_MAIN import main_pipeline_5
except Exception as e:
    print("Error importando PIPELINE_5_MAIN:", e)
    raise

try:
    from modules.config import SLEEP_BETWEEN_CYCLES, MOVIMIENTO_TARGET
except Exception:
    # Defaults si config no está disponible
    SLEEP_BETWEEN_CYCLES = 60
    MOVIMIENTO_TARGET = os.getenv('MOVIMIENTO_TARGET', 'WOO')

try:
    # Cargar 08_assign_tx.py con importlib (el nombre comienza con dígitos)
    MODULES_DIR = os.path.join(BASE_DIR, 'modules')
    assign_path = os.path.join(MODULES_DIR, '08_assign_tx.py')
    spec8 = importlib.util.spec_from_file_location('modules.08_assign_tx', assign_path)
    if not spec8 or not spec8.loader:
        raise ImportError('No se pudo cargar 08_assign_tx.py')
    mod8 = importlib.util.module_from_spec(spec8)
    spec8.loader.exec_module(mod8)
    assign_pending = getattr(mod8, 'assign_pending')
    backfill_stock_columns = getattr(mod8, 'backfill_stock_columns')
except Exception as e:
    print("Error importando asignador PASO 08:", e)
    raise

# Backfill de barcodes (preferido + todos los alias)
try:
    from modules.backfill_barcodes import backfill_barcode_all  # type: ignore
except Exception:
    backfill_barcode_all = None  # type: ignore

try:
    # Importar ruteo de conexión multi-DB para notas, lecturas/escrituras
    from PIPELINE_5_CONSOLIDADO.database_utils import get_connection_for_meli
except Exception as e:
    print("Error importando get_connection_for_meli:", e)
    raise


logger = logging.getLogger("pipeline10")


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )


def _load_id_filters() -> tuple[Set[str], Set[str]]:
    """Devuelve (disabled_ids, only_ids) a partir de config/env.
    - Lee config/token.json -> disabled_user_ids: ["..."] si existe
    - Env DISABLED_ML_USER_IDS="id1,id2"
    - Env ONLY_ML_USER_IDS="id1,id2" (si se especifica, solo procesa esos)
    """
    disabled: Set[str] = set()
    only: Set[str] = set()
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_path = os.path.join(base_dir, 'config', 'token.json')
        if os.path.isfile(cfg_path):
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                dl = data.get('disabled_user_ids')
                if isinstance(dl, list):
                    disabled |= {str(x) for x in dl}
    except Exception:
        pass
    env_dis = os.getenv('DISABLED_ML_USER_IDS', '')
    if env_dis:
        disabled |= {x.strip() for x in env_dis.split(',') if x.strip()}
    env_only = os.getenv('ONLY_ML_USER_IDS', '')
    if env_only:
        only |= {x.strip() for x in env_only.split(',') if x.strip()}
    return disabled, only


def _file_user_ids(token_path: str) -> Set[str]:
    """Extrae posibles user_ids de un archivo de token.
    Soporta formatos:
      {"user_tokens": {"209611492": {"access_token": "..."}}}
      {"209611492": {"access_token": "..."}}
      {"user_id": 209611492, ...}
    """
    ids: Set[str] = set()
    try:
        with open(token_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            if 'user_tokens' in data and isinstance(data['user_tokens'], dict):
                ids |= {str(k) for k in data['user_tokens'].keys()}
            ids |= {str(k) for k in data.keys() if str(k).isdigit()}
            if 'user_id' in data:
                try:
                    ids.add(str(int(data['user_id'])))
                except Exception:
                    pass
    except Exception:
        pass
    return ids


def _should_process_token(token_path: str, disabled: Iterable[str], only: Iterable[str]) -> bool:
    ids = _file_user_ids(token_path)
    if not ids:
        # Si no se puede determinar, procesar por defecto salvo que haya ONLY
        return not set(only)
    ids = {str(x) for x in ids}
    if set(only):
        return bool(ids & set(only))
    return not bool(ids & set(disabled))


def _sync_multi_accounts(limit_acc1: int, limit_acc2: int, *, cycle_no: int = 0) -> None:
    """Sincroniza órdenes recientes por cada cuenta (si hay segundo token).
    Usa la lógica probada de scripts/process_last_sales_per_meli.py.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        script_path = os.path.join(base_dir, 'scripts', 'process_last_sales_per_meli.py')
        spec = importlib.util.spec_from_file_location('scripts.process_last_sales_per_meli', script_path)
        if not spec or not spec.loader:
            logger.info("Multi-cuenta: no se pudo cargar process_last_sales_per_meli.py; continuo con pipeline 5 estándar")
            return
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]

        token1 = os.path.join(base_dir, 'config', 'token.json')
        token2 = os.path.join(base_dir, 'config', 'token_02.json')
        disabled, only = _load_id_filters()

        logger.info(f"👥 Sync multi-cuenta: acc1={limit_acc1}, acc2={limit_acc2} (ciclo={cycle_no})")

        jobs = []
        max_workers = int(os.getenv("MAX_WORKERS_ACCOUNTS", "2"))

        # Política de frecuencia para user 756086955 (tráfico bajo)
        every_n = int(os.getenv("PROCESS_EVERY_N_CYCLES_756086955", "1"))
        def _skip_low_traffic(token_path: str) -> bool:
            try:
                ids = _file_user_ids(token_path)
                if "756086955" in ids and every_n > 1 and (cycle_no % every_n) != 0:
                    logger.info(f"Cuenta con user_id 756086955: salteada este ciclo (cada {every_n})")
                    return True
            except Exception:
                pass
            return False

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            # Cuenta 1
            if os.path.exists(token1):
                if _should_process_token(token1, disabled, only):
                    if (limit_acc1 is not None) and (int(limit_acc1) <= 0):
                        logger.info("Cuenta 1: deshabilitada por límite <= 0")
                    else:
                        logger.info("Cuenta 1: usando config/token.json")
                        jobs.append(ex.submit(mod.process_orders_from_token, token1, int(limit_acc1)))
                else:
                    logger.info("Cuenta 1: saltada por filtros (disabled/only)")
            else:
                logger.warning("Cuenta 1: config/token.json no encontrado")

            # Cuenta 2
            if os.path.exists(token2):
                if _should_process_token(token2, disabled, only) and not _skip_low_traffic(token2):
                    if (limit_acc2 is not None) and (int(limit_acc2) <= 0):
                        logger.info("Cuenta 2: deshabilitada por límite <= 0")
                    else:
                        logger.info("Cuenta 2: usando config/token_02.json")
                        jobs.append(ex.submit(mod.process_orders_from_token, token2, int(limit_acc2)))
                else:
                    logger.info("Cuenta 2: saltada (filtros o frecuencia)")
            else:
                logger.info("Cuenta 2: token_02.json no presente; si lo agregás se sincroniza también")

            # Esperar a todas las cuentas
            for f in as_completed(jobs):
                try:
                    f.result()
                except Exception as e:
                    logger.warning(f"Multi-cuenta: error en tarea: {e}")
    except Exception as e:
        logger.warning(f"Multi-cuenta: error durante sync por cuenta: {e}")


def update_notes_recent(limit: int) -> int:
    """Actualiza la columna 'nota' para las últimas N órdenes usando
    las mismas estrategias del script `backfill_notes_once.py`.

    Devuelve la cantidad de órdenes actualizadas.
    """
    try:
        # Cargar helpers de backfill_notes_once.py vía importlib
        base_dir = os.path.dirname(os.path.dirname(__file__))
        bf_path = os.path.join(base_dir, 'PIPELINE_5_CONSOLIDADO', 'backfill_notes_once.py')
        spec = importlib.util.spec_from_file_location('PIPELINE_5_CONSOLIDADO.backfill_notes_once', bf_path)
        if not spec or not spec.loader:
            logger.warning("Notas: no se pudo cargar backfill_notes_once.py")
            return 0
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]

        # Reutilizar las funciones internas ya probadas
        _fetch_notes = getattr(mod, '_fetch_notes')
        _fetch_comments_fallback = getattr(mod, '_fetch_comments_fallback')
        _fetch_merchant_comments_from_pack = getattr(mod, '_fetch_merchant_comments_from_pack')
        _fetch_messages_from_pack = getattr(mod, '_fetch_messages_from_pack')

        # Determinar los user_ids disponibles desde token.json y token_02.json
        base_dir = os.path.dirname(os.path.dirname(__file__))
        token1 = os.path.join(base_dir, 'config', 'token.json')
        token2 = os.path.join(base_dir, 'config', 'token_02.json')
        user_ids = set()
        try:
            user_ids |= _file_user_ids(token1)
        except Exception:
            pass
        try:
            user_ids |= _file_user_ids(token2)
        except Exception:
            pass

        # Si no pudimos determinar IDs, procesar contra base por defecto (None)
        if not user_ids:
            user_ids = {None}

        # Config de timeouts/caps por entorno
        try:
            per_order_timeout = float(os.getenv("PIPE10_NOTES_PER_ORDER_TIMEOUT", "12"))
        except Exception:
            per_order_timeout = 12.0
        try:
            max_per_account = int(os.getenv("PIPE10_NOTES_MAX_PER_ACCOUNT", str(limit)))
        except Exception:
            max_per_account = limit

        notes_debug = str(os.getenv("PIPE10_NOTES_DEBUG", "0")).strip().lower() in {"1", "true", "yes"}

        def _get_note_with_fallback(oid: str) -> str | None:
            # Ejecuta la cadena de fetchers en un hilo para poder aplicar timeout por orden
            def _runner():
                import time as _t
                if notes_debug:
                    logger.info(f"Notas[{oid}]: inicio fetch")
                # 1) notes
                t0 = _t.time()
                try:
                    n = _fetch_notes(oid)
                    if n:
                        if notes_debug:
                            logger.info(f"Notas[{oid}]: _fetch_notes OK en {(_t.time()-t0):.2f}s")
                        return n
                except Exception as e:
                    logger.warning(f"Notas[{oid}]: _fetch_notes error: {e}")
                # 2) comments fallback
                t1 = _t.time()
                try:
                    n = _fetch_comments_fallback(oid)
                    if n:
                        if notes_debug:
                            logger.info(f"Notas[{oid}]: _fetch_comments_fallback OK en {(_t.time()-t1):.2f}s")
                        return n
                except Exception as e:
                    logger.warning(f"Notas[{oid}]: _fetch_comments_fallback error: {e}")
                # 3) merchant comments by pack
                t2 = _t.time()
                try:
                    n = _fetch_merchant_comments_from_pack(oid)
                    if n:
                        if notes_debug:
                            logger.info(f"Notas[{oid}]: _fetch_merchant_comments_from_pack OK en {(_t.time()-t2):.2f}s")
                        return n
                except Exception as e:
                    logger.warning(f"Notas[{oid}]: _fetch_merchant_comments_from_pack error: {e}")
                # 4) messages by pack
                t3 = _t.time()
                try:
                    n = _fetch_messages_from_pack(oid)
                    if n:
                        if notes_debug:
                            logger.info(f"Notas[{oid}]: _fetch_messages_from_pack OK en {(_t.time()-t3):.2f}s")
                        return n
                except Exception as e:
                    logger.warning(f"Notas[{oid}]: _fetch_messages_from_pack error: {e}")
                if notes_debug:
                    logger.info(f"Notas[{oid}]: sin nota tras {(_t.time()-t0):.2f}s")
                return None
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout
            with ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_runner)
                try:
                    return fut.result(timeout=per_order_timeout)
                except FutTimeout:
                    logger.warning(f"Notas: timeout por orden {oid} (> {per_order_timeout}s). Se omite.")
                    return None
                except Exception as e:
                    logger.warning(f"Notas: error obteniendo nota para {oid}: {e}")
                    return None

        total_updated = 0
        for uid in user_ids:
            try:
                # Abrir conexión ruteada por cuenta
                with get_connection_for_meli(uid) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT TOP (?) order_id FROM orders_meli ORDER BY date_created DESC", (max_per_account,))
                    ids = [str(r[0]) for r in cur.fetchall()]
                    if not ids:
                        continue
                    if notes_debug:
                        logger.info(f"Notas[cta={uid}]: procesando {len(ids)} ids (TOP {max_per_account})")
                    for oid in ids:
                        nota = _get_note_with_fallback(oid)
                        cur.execute(
                            "UPDATE orders_meli SET nota = ?, fecha_actualizacion = GETDATE() WHERE order_id = ?",
                            (nota, oid),
                        )
                        conn.commit()
                        total_updated += 1
            except Exception as _e:
                logger.warning(f"Notas: error procesando notas para cuenta {uid}: {_e}")
                continue
        return total_updated
    except Exception as e:
        logger.warning(f"Notas: error en update_notes_recent: {e}")
        return 0


_CYCLE_NO = 0  # contador global de ciclos


def run_cycle(limit: Optional[int], limit_acc1: Optional[int] = None, limit_acc2: Optional[int] = None) -> None:
    """
    Ejecuta un ciclo completo:
    1) Sync de órdenes reales ML (PIPELINE 5): inserta/actualiza estados, shipping, notas, atributos.
    2) Asignación + movimiento WOO→WOO para ready_to_print no asignadas (PASO 08, idempotente).
    3) Backfill de columnas de stock por depósito para visibilidad.
    """
    # Recargar .env en cada ciclo para tomar cambios en caliente
    try:
        if load_dotenv is not None:
            base_dir = os.path.dirname(os.path.dirname(__file__))
            env_path = os.path.join(base_dir, 'config', '.env')
            if os.path.isfile(env_path):
                load_dotenv(env_path, override=True)
    except Exception:
        pass

    logger.info("🚀 PIPELINE 10 - Inicio de ciclo")

    # 0) Sync multi-cuenta (paralelo) para asegurar columna MELI de ambas cuentas
    try:
        lim_mc = limit if limit is not None else 20
        # Resolver límites por cuenta (CLI > ENV > global)
        lim1 = limit_acc1 if limit_acc1 is not None else int(os.getenv("LIMIT_ACC1", str(lim_mc)))
        lim2 = limit_acc2 if limit_acc2 is not None else int(os.getenv("LIMIT_ACC2", str(lim_mc)))
        global _CYCLE_NO
        _sync_multi_accounts(lim1, lim2, cycle_no=_CYCLE_NO)
    except Exception as e:
        logger.warning(f"Multi-cuenta: error previo al pipeline 5: {e}")

    # 1) Sync ML (PIPELINE 5). Reprocesa y actualiza si ya existen
    try:
        logger.info("📥 Sync ML: obteniendo/actualizando últimas órdenes...")

        # Aplicar filtros por cuenta también a Pipeline 5 usando ONLY_ML_USER_IDS
        # Detectar user_ids desde los archivos de token
        base_dir = os.path.dirname(os.path.dirname(__file__))
        token1 = os.path.join(base_dir, 'config', 'token.json')
        token2 = os.path.join(base_dir, 'config', 'token_02.json')

        ids_acc1 = _file_user_ids(token1) if os.path.exists(token1) else set()
        ids_acc2 = _file_user_ids(token2) if os.path.exists(token2) else set()
        id1 = next(iter(ids_acc1)) if ids_acc1 else '209611492'  # fallback conocido
        id2 = next(iter(ids_acc2)) if ids_acc2 else '756086955'  # fallback conocido

        # Resolver límites efectivos
        lim1_eff = limit_acc1 if limit_acc1 is not None else int(os.getenv("LIMIT_ACC1", str(limit if limit is not None else 20)))
        lim2_eff = limit_acc2 if limit_acc2 is not None else int(os.getenv("LIMIT_ACC2", str(limit if limit is not None else 20)))

        # Si el usuario provee límites por cuenta, damos prioridad y ejecutamos por cuenta
        per_account_cli = (limit_acc1 is not None) or (limit_acc2 is not None)

        # Guardar valor previo de ONLY_ML_USER_IDS y TOKEN_PATH para restaurar luego
        only_ids_env_before = os.environ.get('ONLY_ML_USER_IDS')
        token_path_before = os.environ.get('TOKEN_PATH')

        try:
            if lim1_eff <= 0 and lim2_eff <= 0:
                logger.info("📥 Pipeline 5 omitido: limit-acc1<=0 y limit-acc2<=0")
                # no ejecutamos pipeline 5
            else:
                if per_account_cli:
                    # Ejecutar por cuenta según límites efectivos
                    if lim1_eff > 0:
                        os.environ['ONLY_ML_USER_IDS'] = str(id1)
                        # Forzar token de cuenta 1
                        if os.path.exists(token1):
                            os.environ['TOKEN_PATH'] = token1
                            logger.info(f"Pipeline 5 (acc1): ONLY_ML_USER_IDS={id1} | TOKEN_PATH={token1} | limit={lim1_eff}")
                        else:
                            logger.warning(f"TOKEN cuenta 1 no encontrado en {token1}; se usará default")
                        main_pipeline_5(limit=lim1_eff)
                    if lim2_eff > 0:
                        os.environ['ONLY_ML_USER_IDS'] = str(id2)
                        # Forzar token de cuenta 2
                        if os.path.exists(token2):
                            os.environ['TOKEN_PATH'] = token2
                            logger.info(f"Pipeline 5 (acc2): ONLY_ML_USER_IDS={id2} | TOKEN_PATH={token2} | limit={lim2_eff}")
                        else:
                            logger.warning(f"TOKEN cuenta 2 no encontrado en {token2}; se usará default")
                        main_pipeline_5(limit=lim2_eff)
                else:
                    # Mantener comportamiento previo usando --limit global
                    if lim1_eff <= 0 and lim2_eff > 0:
                        os.environ['ONLY_ML_USER_IDS'] = str(id2)
                        # Si solo acc2 activa, preferir su token
                        if os.path.exists(token2):
                            os.environ['TOKEN_PATH'] = token2
                            logger.info(f"TOKEN_PATH forzado para acc2: {token2}")
                        logger.info(f"Filtro aplicado a Pipeline 5: ONLY_ML_USER_IDS={id2} (acc1 deshabilitada)")
                    elif lim2_eff <= 0 and lim1_eff > 0:
                        os.environ['ONLY_ML_USER_IDS'] = str(id1)
                        if os.path.exists(token1):
                            os.environ['TOKEN_PATH'] = token1
                            logger.info(f"TOKEN_PATH forzado para acc1: {token1}")
                        logger.info(f"Filtro aplicado a Pipeline 5: ONLY_ML_USER_IDS={id1} (acc2 deshabilitada)")
                    else:
                        # Ambas activas: limpiar filtro para que procese ambas
                        if 'ONLY_ML_USER_IDS' in os.environ:
                            os.environ.pop('ONLY_ML_USER_IDS', None)
                            logger.info("Filtro ONLY_ML_USER_IDS limpiado para Pipeline 5 (ambas cuentas activas)")

                    # Ejecutar Pipeline 5 una sola vez con el límite global
                    if limit is None:
                        main_pipeline_5()  # usa defaults internos
                    else:
                        main_pipeline_5(limit=limit)
        finally:
            # Restaurar ONLY_ML_USER_IDS/TOKEN_PATH previos si existían, si no, limpiar
            if only_ids_env_before is not None:
                os.environ['ONLY_ML_USER_IDS'] = only_ids_env_before
            else:
                if 'ONLY_ML_USER_IDS' in os.environ:
                    os.environ.pop('ONLY_ML_USER_IDS', None)
            if token_path_before is not None:
                os.environ['TOKEN_PATH'] = token_path_before
            else:
                if 'TOKEN_PATH' in os.environ:
                    os.environ.pop('TOKEN_PATH', None)
        logger.info("✅ Sync ML completado")
    except Exception as e:
        logger.error(f"❌ Error en sync ML: {e}")

    # 1.0) Backfill de BARCODES (preferido + todos los alias)
    try:
        if backfill_barcode_all:
            max_rows = int(os.getenv("PIPE10_BARCODE_MAX_ROWS", "100"))
            days_win = int(os.getenv("PIPE10_BARCODE_DAYS", "60"))
            logger.info(f"🧾 Barcodes: completando hasta {max_rows} órdenes (últimos {days_win} días)...")
            n = backfill_barcode_all(max_rows=max_rows, days_window=days_win, account=None)
            if n:
                logger.info(f"🧾 Barcodes: completadas {n} órdenes")
            else:
                logger.info("🧾 Barcodes: no había pendientes para completar")
        else:
            logger.debug("🧾 Barcodes: módulo no disponible; se omite")
    except Exception as e:
        logger.warning(f"🧾 Barcodes: error en backfill: {e}")

    # 1.1) Backfill de NOTAS para las últimas N órdenes sincronizadas
    try:
        lim = limit if limit is not None else 50
        skip_notes = str(os.getenv("PIPE10_SKIP_NOTES", "0")).strip().lower() in {"1", "true", "yes"}
        logger.debug(f"Notas: PIPE10_SKIP_NOTES efectivo = {os.getenv('PIPE10_SKIP_NOTES')}")
        if skip_notes:
            logger.info("📝 Notas: salteadas por PIPE10_SKIP_NOTES=1")
        else:
            logger.info(f"📝 Notas: iniciando actualización para últimas {lim} órdenes...")
            n = update_notes_recent(lim)
            logger.info("📝 Notas: finalizó actualización")
            if n:
                logger.info(f"📝 Notas actualizadas para {n} órdenes recientes")
            else:
                logger.info("📝 Notas: no hubo órdenes para actualizar o no se encontraron notas")
    except Exception as e:
        logger.error(f"❌ Error actualizando notas: {e}")

    # 2) Asignación + Movimiento (idempotente, espera respuesta Dragonfish)
    try:
        logger.info("🏷️ Asignación + Movimiento: procesando pendientes...")
        processed = assign_pending()
        logger.info(f"✅ Asignación/Movimiento completado. Órdenes procesadas: {processed}")
    except Exception as e:
        logger.error(f"❌ Error en asignación/movimiento: {e}")

    # 3) Backfill de visibilidad de stock por depósito (no toca flags)
    try:
        updated = backfill_stock_columns(max_rows=20)
        if updated:
            logger.info(f"🧩 Backfill de stock por depósito aplicado a {updated} órdenes")
    except Exception as e:
        logger.error(f"❌ Error en backfill de stock: {e}")

    logger.info(f"🎯 MOVIMIENTO_TARGET actual: {MOVIMIENTO_TARGET}")
    logger.info("🏁 PIPELINE 10 - Fin de ciclo")



def main() -> None:
    parser = argparse.ArgumentParser(description="PIPELINE 10 ESTABLE - Loop de sync+asignación+movimiento")
    parser.add_argument("--limit", type=int, default=50, help="Cantidad de órdenes recientes a sincronizar por ciclo (PIPELINE 5)")
    parser.add_argument("--interval", type=int, default=None, help="Intervalo entre ciclos en segundos")
    parser.add_argument("--log", type=str, default=os.getenv("LOG_LEVEL", "INFO"), help="Nivel de log (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--once", action="store_true", help="Ejecuta un solo ciclo y termina")
    parser.add_argument("--limit-acc1", dest="limit_acc1", type=int, default=None, help="Límite por ciclo para la cuenta 1 (config/token.json)")
    parser.add_argument("--limit-acc2", dest="limit_acc2", type=int, default=None, help="Límite por ciclo para la cuenta 2 (config/token_02.json)")
    args = parser.parse_args()

    setup_logging(args.log)

    interval = args.interval if args.interval is not None else int(os.getenv("SLEEP_BETWEEN_CYCLES", SLEEP_BETWEEN_CYCLES))

    logger.info("============================================")
    logger.info("🧠 PIPELINE 10 ESTABLE - Loop en ejecución")
    logger.info(f"🔧 MOVIMIENTO_TARGET = {MOVIMIENTO_TARGET}")
    logger.info(f"⏱️ Intervalo = {interval}s | Limit = {args.limit}")
    logger.info("============================================")

    try:
        if args.once:
            run_cycle(limit=args.limit, limit_acc1=args.limit_acc1, limit_acc2=args.limit_acc2)
        else:
            while True:
                # Usar reloj monotónico para evitar problemas si el reloj del sistema cambia
                start = time.monotonic()
                run_cycle(limit=args.limit, limit_acc1=args.limit_acc1, limit_acc2=args.limit_acc2)
                elapsed = time.monotonic() - start
                sleep_left = max(0, interval - int(elapsed))
                if sleep_left > 0:
                    logger.info(f"😴 Esperando {sleep_left}s para próximo ciclo...")
                    time.sleep(sleep_left)
                # incrementar contador de ciclos
                try:
                    global _CYCLE_NO
                    _CYCLE_NO += 1
                except Exception:
                    pass
    except KeyboardInterrupt:
        logger.info("🛑 Detenido por usuario (Ctrl+C)")


if __name__ == "__main__":
    main()
