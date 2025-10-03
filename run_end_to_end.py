# -*- coding: utf-8 -*-
"""
Runner end-to-end limpio
- Reutiliza el orquestador estable existente del repo actual.
- No duplica lógica; solo reenvía parámetros y ejecuta el flujo completo.

Uso:
  python run_end_to_end.py --limit 10 --log INFO --once
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys

# Ruta al orquestador estable existente
PIPELINE7_FULL = r"C:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline"
ORQ_PATH = os.path.join(PIPELINE7_FULL, 'PIPELINE_10_ESTABLE', 'main.py')


def run(cmd: list[str], cwd: str | None = None) -> int:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=cwd or PIPELINE7_FULL)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Runner end-to-end')
    parser.add_argument('--limit', type=int, default=10, help='Cantidad de órdenes a sincronizar')
    parser.add_argument('--log', type=str, default='INFO', help='Nivel de log (DEBUG/INFO/WARNING/ERROR)')
    parser.add_argument('--once', action='store_true', help='Ejecutar solo un ciclo (recomendado)')
    args = parser.parse_args(argv)

    if not os.path.isfile(ORQ_PATH):
        print(f" No se encuentra el orquestador estable en: {ORQ_PATH}")
        return 1

    print("================ RUNNER E2E - INICIO ================")
    code = run([sys.executable, ORQ_PATH, '--once', '--limit', str(args.limit), '--log', args.log], cwd=PIPELINE7_FULL)
    if code != 0:
        print(f" Orquestador estable terminó con código {code}")
        return code
    print("================ RUNNER E2E - FIN ================")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
