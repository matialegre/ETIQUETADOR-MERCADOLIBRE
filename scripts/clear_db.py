# -*- coding: utf-8 -*-
"""
Limpia la base de datos (orders_meli y tablas auxiliares) usando las utilidades del pipeline.
Uso:
  python scripts/clear_db.py
"""
from __future__ import annotations
import os
import sys

# Asegurar que podemos importar desde PIPELINE_5_CONSOLIDADO
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
PIPE5_DIR = os.path.join(PROJECT_ROOT, 'PIPELINE_5_CONSOLIDADO')
if PIPE5_DIR not in sys.path:
    sys.path.insert(0, PIPE5_DIR)

try:
    import database_utils as d
except Exception as e:
    print(f"❌ No se pudo importar database_utils: {e}")
    raise SystemExit(1)

print("🧹 Limpiando base...")
try:
    ok = d.clear_all_orders()
    print(f"✅ Limpieza: {ok}")
    raise SystemExit(0)
except Exception as e:
    print(f"❌ Error limpiando base: {e}")
    raise SystemExit(1)
