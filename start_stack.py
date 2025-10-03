# -*- coding: utf-8 -*-
"""
Lanza toda la stack:
- Backend FastAPI (uvicorn server.app:app)
- Frontend (opcional modo dev: npm run dev en client/; si no, el backend sirve client/dist)
- Loop del pipeline estable (PIPELINE_10_ESTABLE/main.py) con limit=50 por defecto
- Abre el navegador en /ui/

Uso ejemplos:
  python start_stack.py                      # backend + pipeline loop (limit=50), UI estática servida por backend
  python start_stack.py --limit 100          # igual pero con 100
  python start_stack.py --once               # corre un ciclo del pipeline y termina (backend sigue)
  python start_stack.py --dev-frontend       # levanta Vite (frontend dev) además del backend
  python start_stack.py --backend-port 9000  # cambia puerto de backend
  python start_stack.py --split --ngrok-domain pandemoniumdev.ngrok.dev  # abre backend/pipeline y ngrok en 3 CMD

Notas:
- Requiere Python, Node (para --dev-frontend) y dependencias instaladas.
- En Windows, cierre con Ctrl+C. El script intenta cerrar subprocesos ordenadamente.
"""
from __future__ import annotations
import argparse
import os
import sys
import time
import subprocess
import webbrowser
import signal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLIENT_DIR = ROOT / 'client'
SERVER_APP = 'server.app:app'
PIPELINE_MAIN = ROOT / 'PIPELINE_10_ESTABLE' / 'main.py'


def _exists_node() -> bool:
    try:
        subprocess.run(['node', '-v'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        subprocess.run(['npm', '-v'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False


def _maybe_build_frontend() -> None:
    dist = CLIENT_DIR / 'dist'
    if dist.is_dir():
        return
    pkg = CLIENT_DIR / 'package.json'
    if not pkg.is_file():
        return
    if not _exists_node():
        print('Aviso: Node/npm no disponibles; no puedo construir client/dist. El backend servirá /server/static por fallback.')
        return
    print('Construyendo frontend (vite build)...')
    try:
        # instalar deps si falta node_modules
        node_modules = CLIENT_DIR / 'node_modules'
        if not node_modules.exists():
            subprocess.run(['npm', 'install', '--silent'], cwd=str(CLIENT_DIR), check=False)
        subprocess.run(['npm', 'run', 'build'], cwd=str(CLIENT_DIR), check=False)
    except Exception as e:
        print(f'Error construyendo frontend: {e}')


def launch_backend(host: str, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    # Asegurar que config/.env sea tomado por server/app.py; allí ya se carga explícitamente.
    cmd = [sys.executable, '-m', 'uvicorn', SERVER_APP, '--host', host, '--port', str(port), '--reload']
    print('$', ' '.join(cmd))
    return subprocess.Popen(cmd, cwd=str(ROOT), env=env)


def launch_frontend_dev() -> subprocess.Popen | None:
    if not _exists_node():
        print('Aviso: Node/npm no disponibles; no puedo iniciar Vite dev. Usa la UI servida por el backend en /ui/.')
        return None
    if not (CLIENT_DIR / 'package.json').is_file():
        print('Aviso: client/package.json no existe; omito Vite dev.')
        return None
    cmd = ['npm', 'run', 'dev']
    print('$', ' '.join(cmd), '(cwd=client)')
    return subprocess.Popen(cmd, cwd=str(CLIENT_DIR))


def launch_pipeline(limit: int, interval: int, once: bool) -> subprocess.Popen:
    if not PIPELINE_MAIN.is_file():
        raise FileNotFoundError(f'No se encontró {PIPELINE_MAIN}')
    cmd = [sys.executable, str(PIPELINE_MAIN), '--limit', str(limit), '--interval', str(interval)]
    if once:
        cmd.append('--once')
    print('$', ' '.join(cmd))
    return subprocess.Popen(cmd, cwd=str(ROOT))


def open_in_new_console(title: str, command: str, cwd: Path) -> None:
    """Abre un nuevo CMD en Windows y ejecuta el comando (deja la ventana abierta)."""
    if os.name != 'nt':
        # En no-Windows, solo lanza como proceso normal
        subprocess.Popen(command, cwd=str(cwd), shell=True)
        return
    # cmd /k mantiene la consola abierta; start "title" ejecuta en nueva ventana
    full = f'start "{title}" cmd /k {command}'
    # Usar shell=True evita que PowerShell interprete mal el título como ejecutable
    subprocess.Popen(full, cwd=str(cwd), shell=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Lanzador full stack (backend + frontend opcional + pipeline)')
    parser.add_argument('--limit', type=int, default=30, help='Cantidad de órdenes recientes por ciclo (pipeline)')
    parser.add_argument('--interval', type=int, default=10, help='Intervalo entre ciclos del pipeline (segundos)')
    parser.add_argument('--once', action='store_true', help='Ejecutar solo un ciclo del pipeline')
    parser.add_argument('--backend-host', type=str, default='0.0.0.0', help='Host de backend')
    parser.add_argument('--backend-port', type=int, default=8080, help='Puerto de backend')
    parser.add_argument('--dev-frontend', action='store_true', help='Levantar Vite (npm run dev) para el frontend')
    parser.add_argument('--open', action='store_true', help='Abrir navegador automáticamente en la UI')
    parser.add_argument('--split', action='store_true', help='Abrir backend, pipeline y frontend en 3 CMD distintos y salir')
    parser.add_argument('--ngrok-domain', type=str, default='', help='Si se especifica, abre una CMD con ngrok http --domain=<dominio> apuntando al backend')
    args = parser.parse_args(argv)

    # Build de frontend si falta dist (no bloqueante en caso de error)
    _maybe_build_frontend()

    # Modo split: abrir 3 consolas y terminar
    if args.split:
        # Backend
        be_cmd = f'"{sys.executable}" -m uvicorn {SERVER_APP} --host {args.backend_host} --port {args.backend_port} --reload'
        open_in_new_console('Backend - Uvicorn', be_cmd, ROOT)

        # Pipeline
        if not PIPELINE_MAIN.is_file():
            print(f'No se encontró pipeline en {PIPELINE_MAIN}')
        else:
            pipe_cmd = f'"{sys.executable}" "{PIPELINE_MAIN}" --limit {args.limit} --interval {args.interval}' + (' --once' if args.once else '')
            open_in_new_console('Pipeline 10 Estable', pipe_cmd, ROOT)

        # Frontend (dev). Si no hay Node, abriré una consola que avise del problema
        if args.dev_frontend:
            if _exists_node() and (CLIENT_DIR / 'package.json').is_file():
                fe_cmd = 'npm run dev'
                open_in_new_console('Frontend - Vite Dev', fe_cmd, CLIENT_DIR)
            else:
                open_in_new_console('Frontend - Aviso', 'echo Node/npm no disponibles o falta package.json & pause', CLIENT_DIR)
        else:
            # Sin dev frontend, la UI la sirve el backend desde /ui/
            pass

        # Ngrok (opcional)
        if args.ngrok_domain:
            ngrok_cmd = f'ngrok http --domain={args.ngrok_domain} --region=sa {args.backend_host}:{args.backend_port}'
            open_in_new_console('Ngrok Tunnel', ngrok_cmd, ROOT)

        # Abrir navegador (opcional)
        if args.open:
            time.sleep(2)
            url = f'http://{args.backend_host}:{args.backend_port}/ui/'
            try:
                webbrowser.open(url)
            except Exception:
                print(f'Abrí manualmente: {url}')
        print('Ventanas lanzadas en modo split. Este proceso termina ahora.')
        return 0

    procs: list[subprocess.Popen] = []

    try:
        # 1) Backend
        be = launch_backend(args.backend_host, args.backend_port)
        procs.append(be)

        # 2) Frontend dev (opcional). Si no, la UI se sirve por backend desde client/dist
        fe = None
        if args.dev_frontend:
            fe = launch_frontend_dev()
            if fe:
                procs.append(fe)

        # 3) Pipeline
        pipe = launch_pipeline(args.limit, args.interval, args.once)
        procs.append(pipe)

        # 4) Abrir navegador
        if args.open:
            # Espera breve para que backend suba
            time.sleep(2)
            url = f'http://{args.backend_host}:{args.backend_port}/ui/'
            try:
                webbrowser.open(url)
            except Exception:
                print(f'Abrí manualmente: {url}')
        print('Stack iniciada. Ctrl+C para detener.')

        # Esperar a que el pipeline termine si es --once; si no, esperar backend
        if args.once:
            pipe.wait()
            print('Pipeline (once) finalizado. Manteniendo backend activo. Ctrl+C para salir.')
            be.wait()
        else:
            # Mantener script vivo mientras backend siga corriendo
            be.wait()
        return 0

    except KeyboardInterrupt:
        print('Interrumpido por usuario. Cerrando procesos...')
        return 0

    finally:
        # Intento de terminación ordenada
        for p in procs[::-1]:  # cerrar primero pipeline/frontend, luego backend
            try:
                if p and p.poll() is None:
                    if os.name == 'nt':
                        p.send_signal(signal.CTRL_BREAK_EVENT) if hasattr(signal, 'CTRL_BREAK_EVENT') else p.terminate()
                    else:
                        p.terminate()
            except Exception:
                pass
        # Grace period
        time.sleep(1.0)
        for p in procs[::-1]:
            try:
                if p and p.poll() is None:
                    p.kill()
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
