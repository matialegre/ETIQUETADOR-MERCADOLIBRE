import os
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Asegurar path a librerías del pipeline 5
sys.path.append(r"c:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline\PIPELINE_5_CONSOLIDADO")
from meli_client_01 import MeliClient  # type: ignore


def fetch_last_orders_acc2(limit: int, token_path: str) -> List[Dict[str, Any]]:
    """Trae las últimas 'limit' órdenes de la cuenta 2 usando el token dado."""
    client = MeliClient(config_path=token_path)
    orders: List[Dict[str, Any]] = client.get_recent_orders(limit=limit)
    return orders or []


def extract_rows(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extrae las columnas requeridas para exportar."""
    rows: List[Dict[str, Any]] = []
    for o in orders:
        try:
            order_id = o.get('id')
            pack_id = o.get('pack_id')
            date_created = o.get('date_created') or o.get('created_at')
            # Extraer SKUs de todos los items de la orden (si hay varios, unir por ' | ')
            skus: List[str] = []
            try:
                items = o.get('order_items') or []
                for it in items:
                    itm = (it or {}).get('item') or {}
                    sku = itm.get('seller_sku') or itm.get('seller_custom_field') or itm.get('seller_sku_id')
                    if sku:
                        skus.append(str(sku))
            except Exception:
                pass
            # Deduplicar preservando orden
            seen = set()
            skus_unique = []
            for s in skus:
                if s not in seen:
                    seen.add(s)
                    skus_unique.append(s)
            sku_text = ' | '.join(skus_unique)
            # Forzar IDs como texto para evitar notación científica en Excel
            order_id_str = "" if order_id is None else str(order_id)
            pack_id_str = "" if pack_id is None else str(pack_id)
            rows.append({
                'date_created': date_created,
                'order_id': order_id_str,
                'pack_id': pack_id_str,
                'sku': sku_text,
            })
        except Exception:
            continue
    return rows


def save_to_excel_or_csv(rows: List[Dict[str, Any]], out_dir: Path, filename_prefix: str) -> Path:
    """Guarda en Excel (.xlsx) forzando texto en IDs y SKU.
    Si no está openpyxl, hace fallback a CSV.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    xlsx_path = out_dir / f"{filename_prefix}_{timestamp}.xlsx"
    csv_path = out_dir / f"{filename_prefix}_{timestamp}.csv"

    # Escribir con openpyxl directamente para controlar formato de texto
    try:
        from openpyxl import Workbook  # type: ignore
        wb = Workbook()
        ws = wb.active
        ws.title = 'orders'
        headers = ['date_created', 'order_id', 'pack_id', 'sku']
        ws.append(headers)
        for r in rows:
            # Prefijar con apóstrofe para que Excel NO convierta a número
            oid = r.get('order_id', '')
            pid = r.get('pack_id', '')
            sku = r.get('sku', '')
            oid_txt = "'" + ('' if oid is None else str(oid))
            pid_txt = "'" + ('' if pid is None else str(pid))
            sku_txt = "'" + ('' if sku is None else str(sku))
            ws.append([
                r.get('date_created', ''),
                oid_txt,
                pid_txt,
                sku_txt,
            ])
        # Forzar formato de texto en columnas B, C y D
        for row in ws.iter_rows(min_row=2, min_col=2, max_col=4):
            for c in row:
                c.number_format = '@'
        wb.save(xlsx_path)
        return xlsx_path
    except Exception:
        # Fallback a CSV estándar
        import csv
        # Prefijar también con apóstrofe para que Excel los lea como texto
        safe_rows = []
        for r in rows:
            safe_rows.append({
                'date_created': r.get('date_created', ''),
                'order_id': "'" + ('' if r.get('order_id') is None else str(r.get('order_id'))),
                'pack_id': "'" + ('' if r.get('pack_id') is None else str(r.get('pack_id'))),
                'sku': "'" + ('' if r.get('sku') is None else str(r.get('sku'))),
            })
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date_created', 'order_id', 'pack_id', 'sku'])
            writer.writeheader()
            writer.writerows(safe_rows)
        return csv_path


def main():
    parser = argparse.ArgumentParser(description='Exporta las últimas ventas de la 2da cuenta de MercadoLibre a Excel (o CSV si no hay pandas).')
    parser.add_argument('--limit', type=int, default=300, help='Cantidad de ventas a traer (por defecto 300)')
    parser.add_argument('--token', type=str, default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\config\\token_02.json", help='Ruta al token de la cuenta 2')
    parser.add_argument('--out-dir', type=str, default=r"c:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\exports", help='Directorio de salida para el archivo generado')
    args = parser.parse_args()

    token_path = args.token
    if not os.path.exists(token_path):
        print(f"❌ No se encontró el token de la cuenta 2 en: {token_path}")
        print("Guarda el archivo token_02.json ahí o pasa --token con la ruta correcta.")
        return

    print(f"🔐 Usando token: {token_path}")
    print(f"⬇️  Trayendo últimas {args.limit} ventas de la cuenta 2...")
    orders = fetch_last_orders_acc2(args.limit, token_path)

    print(f"✅ Órdenes obtenidas: {len(orders)}")
    rows = extract_rows(orders)

    out_path = save_to_excel_or_csv(rows, Path(args.out_dir), filename_prefix='acc2_last_sales')
    print(f"💾 Archivo generado: {out_path}")


if __name__ == '__main__':
    main()
