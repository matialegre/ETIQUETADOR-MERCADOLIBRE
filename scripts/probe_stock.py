"""
Probe Dragonfish stock per deposit for a given SKU using modules/07_dragon_api.get_stock_per_deposit
Usage:
  python scripts/probe_stock.py --sku NMIDKUDADE-NN0-T36
"""
from __future__ import annotations
import argparse
import os
import sys

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    def load_dotenv(*args, **kwargs):
        return None

PROJ_ROOT = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(PROJ_ROOT, 'config', '.env')
if os.path.isfile(ENV_PATH):
    load_dotenv(ENV_PATH, override=True)
else:
    load_dotenv()

import importlib
# Asegurar que 'modules' sea importable como paquete
if PROJ_ROOT not in sys.path:
    sys.path.append(PROJ_ROOT)
try:
    _mod = importlib.import_module('modules.07_dragon_api')
except Exception as e:
    print('Cannot import modules.07_dragon_api:', e)
    sys.exit(1)
get_stock_per_deposit = getattr(_mod, 'get_stock_per_deposit', None)

parser = argparse.ArgumentParser()
parser.add_argument('--sku', required=True)
parser.add_argument('--timeout', type=int, default=60)
args = parser.parse_args()

if not callable(get_stock_per_deposit):
    print('get_stock_per_deposit not available')
    sys.exit(2)

stock = {}
try:
    stock = get_stock_per_deposit(args.sku, timeout=args.timeout)
except Exception as e:
    print('Error:', e)
    sys.exit(3)

print('Stock per deposit for', args.sku)
if not stock:
    print('(empty)')
else:
    total = 0
    for depot, vals in stock.items():
        t = int(vals.get('total') or 0)
        r = int(vals.get('reserved') or 0)
        a = t - r
        print(f"  {depot:10s} total={t:4d} reserved={r:4d} available={a:4d}")
        total += a
    print('Total available =', total)
