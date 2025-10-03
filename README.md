# meli_stock_pipeline (carpeta limpia)

Pipeline standalone y modular para automatizar la asignación de stock y movimientos (MercadoLibre ↔ Dragonfish ↔ SQL Server), reutilizando el orquestador estable y dejando todo listo para operación diaria.

## Objetivo
- __End-to-End automático__: sincroniza órdenes reales ML, asigna depósito óptimo, registra movimiento WOO→WOO y persiste todo en SQL Server.
- __Standalone__: no depende del repo viejo; todo lo necesario vive en esta carpeta.
- __Configuración simple__: variables vía `.env` y `token.json`.

## Requisitos
- Python 3.10+ (probado en 3.12)
- SQL Server local: `.\\SQLEXPRESS` con base `meli_stock`
- Credenciales y permisos a APIs de MercadoLibre y Dragonfish
- ODBC Driver 17 for SQL Server

## Instalación
1) Crear y completar `config/.env` a partir de `config/.env.example`.
2) Copiar/actualizar `token.json` de MercadoLibre (ruta configurable por `.env`).
3) Instalar dependencias:

```powershell
pip install -r .\requirements.txt
```

## TL;DR · Arranque rápido (todo junto)

Ventanas separadas de PowerShell (recomendado):

1) Orquestador E2E (una pasada, 5 órdenes, logs INFO)

```powershell
python .\run_end_to_end.py --once --limit 5 --log INFO
```

2) Backend API (FastAPI + Uvicorn) en 8080

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8080 --reload
```

3) Web UI

- Si ya existe build en `client/dist/` (esta repo lo incluye):

```powershell
# Abrir http://127.0.0.1:8080/ui/
# (lo sirve FastAPI automáticamente desde client/dist)
```

- Si querés modo desarrollo React:

```powershell
pushd .\client; npm install; npm run dev
# UI local en http://127.0.0.1:5173 (el backend sigue en 8080)
```

4) Exponer la API por internet con ngrok (opcional)

```powershell
ngrok http http://127.0.0.1:8080
# Copiar la URL pública https://xxxx.ngrok-free.app y usarla en la GUI externa
```

Tips:

- Variables del backend se cargan desde `config/.env` (ver sección más abajo).
- Token del backend: `SERVER_API_TOKEN` (enviar como `Authorization: Bearer <token>`).
- Endpoint UI: `http://127.0.0.1:8080/ui/` y chat en `http://127.0.0.1:8080/chat-now`.

## Variables de entorno (config/.env)
- `SQL_SERVER=.\\SQLEXPRESS`
- `SQL_DB=meli_stock`
- `SQL_TRUSTED=yes` (o `no` + `SQL_USER`/`SQL_PASSWORD`)
- `TOKEN_PATH=C:\\Users\\Mundo Outdoor\\Desktop\\Develop_Mati\\Escritor Meli\\token.json` (recomendado: mover a `config/token.json`)
- `DRAGON_TIMEOUT_SECS=180`
- `MOVIMIENTO_TARGET=WOO`
- `ML_CLIENT_ID=...` / `ML_CLIENT_SECRET=...` (para refresh automático, opcional si ya existe token válido)
- `LOG_LEVEL=INFO`

Ejemplo completo en `config/.env.example`.

## Estructura principal
- `run_end_to_end.py`: runner orquestador E2E (una línea de comando).
- `PIPELINE_5_CONSOLIDADO/`: sincronización ML, procesamiento, asignación RTP.
- `PIPELINE_6_ASIGNACION/`: movimientos WOO→WOO.
- `PIPELINE_10_ESTABLE/`: orquestador estable reutilizado.
- `modules/`: utilitarios, Dragonfish, asignador, etc.
- `integraciones/`, `dominio/`, `infraestructura/`, `config/`: base modular para crecer.

## Ejecución (standalone)
PowerShell:

```powershell
python .\run_end_to_end.py --once --limit 5 --log INFO
```

Secuencia que ejecuta:
1. Obtener últimas N órdenes reales de ML (shipping real / pack / multiventa)
2. Procesar y normalizar (barcode, color/talle)
3. Asignar depósitos sólo de la lista oficial (score por stock_total y reservado)
4. Registrar movimiento WOO→WOO por orden asignada
5. Persistir por-depósito, flags, y observaciones
6. Mostrar resumen y métricas

Notas clave implementadas:
- Consulta Dragonfish con SKU base, filtrando color/talle, con paginación por campo "Siguiente".
- Regla específica para SKUs `TDRK20**`: se consulta con clave base `TDRK20`.
- Timeout Dragonfish configurable por `DRAGON_TIMEOUT_SECS`.
- Idempotencia: no re-asigna ni re-mueve si ya está marcado en DB.
- Sólo depósitos oficiales considerados (DEP, MDQ, MONBAHIA, MTGBBPS, MTGCBA, MTGCOM, MTGJBJ, MTGROCA, MUNDOAL, MUNDOROC, NQNALB, NQNSHOP).

## Multiventa pack-aware (PASO 08)

Lógica de asignación a nivel pack (`pack_id`) con clusters y auditoría JSON en `asignacion_detalle`. Activa por defecto via `MULTIVENTA_MODE=clustered` en `modules/config.py`.

- __Opción 1 (single)__: un único depósito cubre todos los ítems del pack.
  - Asigna ese depósito a cada ítem.
  - Movimiento WOO→WOO por ítem.
  - `asignacion_detalle` minimal por ítem:
    ```json
    {"opcion": 1, "tipo": "single", "depo": "MTGCOM", "qty": 1}
    ```
- __Opción 2 (cluster)__: no hay single; un único cluster cubre todo el pack.
  - Asigna por ítem dentro del mismo cluster.
  - Movimiento WOO→WOO por ítem con `dist=DEPO:qty` en la observación.
  - `asignacion_detalle` por ítem:
    ```json
    {"opcion": 2, "tipo": "cluster", "cluster": "A", "qty": 1, "distribucion": [{"depo": "DEP", "qty": 1}]}
    ```
- __Opción 3 (split_required)__: ni single ni cluster alcanzan.
  - Marca todo el pack con `DEBE_PARTIRSE = 1`.
  - Deja `deposito_asignado = 'DIVIDIDO'` en cada ítem.
  - Completa `asignacion_detalle` tipo `split_required`.
  - __No__ hace reserva ni movimiento.

Clusters validados:

- `A = [DEPO, DEP, MUNDOAL, MTGBBL, BBPS, MONBAHIA, MTGBBPS]`
- `B = [MUNDOROC, MTGROCA]`

### Importante: evitar pasos legacy que pisan la asignación pack-aware

El orquestador (PIPELINE 10) llama al PASO 08 para asignación pack-aware. El PIPELINE 5 también tenía pasos legacy de asignación/movimiento (PASO 5 y 5.1) que podían pisar la auditoría. Se agregó un skip controlado por variables de entorno y activado por defecto:

- `PIPE5_SKIP_ASSIGN=1`
- `PIPE5_SKIP_MOVE=1`

Con esto, la asignación/movimiento se hacen sólo desde `modules/08_assign_tx.py` (pack-aware).

### Ejecución recomendada (solo PASO 08 aplica)

PowerShell:

```powershell
# (opcional) limpiar base
@"
from PIPELINE_5_CONSOLIDADO.database_utils import clear_all_orders, clear_movimientos
clear_movimientos(); clear_all_orders(); print('DB cleared')
"@ | python -

# correr E2E con pasos legacy de PIPE 5 desactivados
$env:PIPE5_SKIP_ASSIGN='1'; $env:PIPE5_SKIP_MOVE='1'
python .\run_end_to_end.py --once --limit 30 --log DEBUG
```

### Verificación rápida multiventa

Últimos packs y opciones usadas:

```powershell
@"
import pyodbc
cn=pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;')
c=cn.cursor()
c.execute("""
SELECT TOP 30 pack_id,
       SUM(CASE WHEN asignacion_detalle LIKE '%"opcion": 1%' THEN 1 ELSE 0 END) op1,
       SUM(CASE WHEN asignacion_detalle LIKE '%"opcion": 2%' THEN 1 ELSE 0 END) op2,
       SUM(CASE WHEN asignacion_detalle LIKE '%"opcion": 3%' THEN 1 ELSE 0 END) op3,
       SUM(CASE WHEN deposito_asignado='DIVIDIDO' THEN 1 ELSE 0 END) divididos,
       COUNT(*) items
FROM orders_meli
WHERE ISNULL(pack_id,'')<>''
GROUP BY pack_id
ORDER BY MAX(id) DESC
""")
for r in c.fetchall(): print(r)
cn.close()
"@ | python -
```

Split sin movimientos ni reserva:

```powershell
@"
import pyodbc
cn=pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;')
c=cn.cursor()
c.execute("""
SELECT TOP 20 order_id, pack_id, sku, deposito_asignado,
       ISNULL(DEBE_PARTIRSE,0) debe_partirse,
       ISNULL(asignado_flag,0) asignado, ISNULL(movimiento_realizado,0) mov
FROM orders_meli
WHERE deposito_asignado='DIVIDIDO' OR ISNULL(DEBE_PARTIRSE,0)=1
ORDER BY id DESC
""")
for r in c.fetchall(): print(r)
cn.close()
"@ | python -
```

### Título de la publicación (campo `nombre`)

- __Dónde se obtiene__: si el título no viene en la orden, se consulta la API de ML `GET /items/{item_id}`.
  - Código: `PIPELINE_5_CONSOLIDADO/meli_client_01.py` → `MeliClient.get_item(item_id)`.
  - Uso: `PIPELINE_5_CONSOLIDADO/order_processor.py` dentro de `extract_order_data()` resuelve `item_title` con fallback a `get_item()`.
- __Log visible__: durante el procesamiento de cada orden se imprime siempre:
  - `🏷️ Título publicación: <título>`
- __Persistencia en DB__: el título se guarda en `orders_meli.nombre` en ambos flujos:
  - Inserción/actualización completa (órdenes no asignadas aún).
  - Actualización incremental (órdenes ya asignadas): `database_utils.py` actualiza `nombre = COALESCE(?, nombre)` para no pisar si viene vacío.
- __Verificación rápida__:
  - Consultar una orden concreta:
    ```powershell
    @"
    import pyodbc
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;')
    cur = conn.cursor()
    cur.execute("SELECT TOP 1 order_id, item_id, nombre FROM orders_meli ORDER BY fecha_actualizacion DESC, id DESC")
    print(cur.fetchone())
    conn.close()
    "@ | python -
    ```

## Verificación en SQL Server
Consultas útiles (PowerShell → Python inline):

```powershell
@"
import pyodbc
conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;')
cur = conn.cursor()
print('=== Resumen asignación y movimientos (standalone) ===')
cur.execute("SELECT COUNT(*) FROM orders_meli WHERE asignado_flag=1")
print('Asignadas:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM orders_meli WHERE ISNULL(movimiento_realizado,0)=1")
print('Movimientos OK:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM orders_meli WHERE ISNULL(movimiento_realizado,0)=0 AND asignado_flag=1")
print('Asignadas sin mover:', cur.fetchone()[0])
print('\n-- Últimas 5 con movimiento --')
cur.execute("SELECT TOP 5 order_id, sku, deposito_asignado, numero_movimiento, observacion_movimiento, fecha_actualizacion FROM orders_meli WHERE ISNULL(movimiento_realizado,0)=1 ORDER BY fecha_actualizacion DESC, id DESC")
for r in cur.fetchall():
    print(r)
print('\n-- Últimas 5 asignadas --')
cur.execute("SELECT TOP 5 order_id, sku, asignado_flag, deposito_asignado, stock_real, stock_reservado, resultante, fecha_asignacion FROM orders_meli WHERE asignado_flag=1 ORDER BY fecha_asignacion DESC, id DESC")
for r in cur.fetchall():
    print(r)
conn.close()
"@ | python -
```

## Configuración avanzada
- __Retrys SQL__: en ambientes con timeouts es recomendable habilitar retry/backoff en la apertura de conexión y operaciones críticas.
- __Logs__: se puede activar `DEBUG` o configurar rotación (ej. `RotatingFileHandler`).
- __Token ML__: si `ML_CLIENT_ID/SECRET` están en `.env`, el runner refresca `token.json` automáticamente.

## Troubleshooting
- 403 en pack detail: permiso insuficiente del token; el flujo sigue con datos de shipping real.
- Login timeout SQL: verificar servicio `SQLEXPRESS`, ODBC 17 y conectividad. Considerar retry/backoff.
- Sin asignaciones: revisar depósitos oficiales disponibles y stock Dragonfish por talle/color.

## Scheduling (tarea programada)
1) Crear script `run_meli_pipeline.ps1`:

```powershell
python "C:\\Users\\Mundo Outdoor\\CascadeProjects\\meli_stock_pipeline\\run_end_to_end.py" --once --limit 10 --log INFO
```

2) Programar en Task Scheduler (cada X minutos) con usuario de servicio y start in en la carpeta del proyecto.

## Cambios realizados para que funcione
- Normalización Dragonfish: SKU base, filtro talle/color, paginación por "Siguiente" y regla `TDRK20`.
- Persistencia por depósito y flags extra (`agotamiento_flag`, `fecha_orden`).
- Idempotencia en asignación y movimientos; commit por iteración con logs detallados.
- Integración del PASO 5.1 (movimientos) en la carpeta nueva, corrigiendo imports/rutas a `modules/` locales.
- Runner E2E simplificado con parámetros `--once`, `--limit`, `--log`.
- Multiventa pack-aware por `pack_id` (opción 1: single; opción 2: cluster; opción 3: split) con `asignacion_detalle` y flags `DEBE_PARTIRSE` y `DIVIDIDO` cuando corresponde, y movimientos sólo para opciones 1/2.
- Desactivación de pasos legacy (PIPELINE 5 PASO 5 y 5.1) mediante `PIPE5_SKIP_ASSIGN/PIPE5_SKIP_MOVE` para no pisar la auditoría pack-aware del PASO 08.
 - Idempotencia reforzada en `modules/08_assign_tx.py`: si una orden ya está asignada (`asignado_flag=1`), se preservan `deposito_asignado`, `stock_reservado` y `resultante`, se actualizan solo columnas informativas (stock por depósito y `asignacion_detalle`) y se evita el doble movimiento WOO→WOO.
 - Conteo correcto de packs vs individuales en `assign_pending()`: sólo se consideran "packs" los `pack_id` con más de un ítem pendiente; los grupos de tamaño 1 se tratan como individuales. Esto evita logs del tipo `packs=N` cuando todas son individuales con `pack_id` por fallback.

---
Hecho con cariño para operar en producción y evolucionar fácil. Cualquier mejora futura (tests unitarios, refactor a `dominio/` e `integraciones/`) ya tiene base en esta estructura.

## Servidor de Órdenes y Movimientos (API)

Backend HTTP pensado para que una app GUI consuma órdenes y ejecute movimientos desde un solo lugar, sin hablar directo con ML/SQL/Dragonfish. Esta API encapsula la lógica del pipeline (ML real + estados shipping + multiventa + normalización SKU/barcode + filtros por depósito) y expone dos endpoints clave:

- `GET /orders`: consulta de órdenes normalizadas, con filtros y paginación.
- `POST /dragonfish/stock-movement`: registra movimientos (WOO→WOO ó MELI invertido) aplicando reglas vigentes.

Nota: La API puede funcionar sin SQL (modo sólo ML/Dragonfish). Si SQL está configurado, además puede persistir estados/estadísticas como el pipeline.

### Variables de entorno (API)

- Server:
  - `SERVER_HOST=0.0.0.0`
  - `SERVER_PORT=8080`
  - `SERVER_API_TOKEN=tu_token_backend` (se exige como `Authorization: Bearer <token>`)
- MercadoLibre:
  - `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`
  - `ML_TOKEN_PATH` (o `TOKEN_PATH` del proyecto)
- Dragonfish:
  - `DRAGONFISH_BASE_URL` (si no se usa el default del pipeline)
  - `DRAGONFISH_TOKEN`
  - `DRAGON_TIMEOUT_SECS=180`
  - `MOVIMIENTO_TARGET=WOO` (o `MELI` para invertido ROCA/CABA)
- SQL (opcional):
  - `SQL_SERVER=.\\SQLEXPRESS`, `SQL_DB=meli_stock`, `SQL_TRUSTED=yes`
  - (o `SQL_USER/SQL_PASSWORD` si no usás trusted)
- Logs: `LOG_LEVEL=INFO`

### Endpoints

- `GET /orders`
  - Auth: `Authorization: Bearer {SERVER_API_TOKEN}`
  - Query params:
    - `deposito` (obligatorio): `DEPOSITO` | `CABA` | `ROCA`
    - `from` (ISO8601), `to` (ISO8601)
    - `page` (default 1), `limit` (default 200)
  - Función: trae órdenes reales de ML, resuelve shipping real, normaliza SKU/barcode/variaciones, aplica filtro por depósito según reglas actuales, y devuelve paginado.
  - Respuesta (ejemplo):
    ```json
    {
      "orders": [
        {
          "order_id": 123456789,
          "date_created": "2025-08-14T10:22:00-03:00",
          "seller_id": 209611492,
          "order_status": "paid",
          "buyer": { "nickname": "john123", "full_name": "John Doe" },
          "shipping": { "logistic_type": "drop_off", "status": "ready_to_ship", "substatus": null },
          "payments": { "total_paid_amount": 19999.0 },
          "items": [
            {
              "seller_sku": "ABC123",
              "sku": "ABC123",
              "barcode": "7790000000012",
              "title": "Zapatilla X",
              "quantity": 1,
              "variation_attributes": [{ "name": "Talle", "value": "42" }]
            }
          ],
          "note": "DEPOSITO",
          "pack_id": null
        }
      ],
      "page": 1,
      "total": 1
    }
    ```

- `POST /dragonfish/stock-movement`
  - Auth: `Authorization: Bearer {SERVER_API_TOKEN}`
  - Body mínimo:
    ```json
    {
      "pedido_id": 123456789,
      "codigo_barra": "7790000000012",
      "cantidad": 1,
      "datos_articulo": { "sku": "ABC123", "titulo": "Zapatilla X" },
      "contexto": { "depo": "MUNDOROC", "origen": "MELI", "observacion": "MATIAPP WOO A WOO | order=..." }
    }
    ```
  - Comportamiento: aplica reglas ROCA/CABA “invertido” cuando `MOVIMIENTO_TARGET=MELI` (Tipo=1, OrigenDestino=MUNDOROC/CABA, BaseDeDatos="MELI"). Devuelve número de movimiento o error estructurado.
  - Respuesta:
    ```json
    { "ok": true, "status": 200, "numero": 987654, "data": {} }
    ```

### Cómo consultar TODOS los campos (MEGA API MUNDO OUTDOOR)

- Título de la API: MEGA API MUNDO OUTDOOR
- Base local por defecto: `http://127.0.0.1:8080`
- Ver columnas disponibles: `GET /orders/columns`
- Traer todas las columnas: usar `?fields=all` (o seleccionar una lista separada por comas)

Ejemplos:

```bash
curl -H "Authorization: Bearer $SERVER_API_TOKEN" \
  "http://127.0.0.1:8080/orders?fields=all&page=1&limit=200&sort_by=id&sort_dir=DESC"

# Selección parcial
curl -H "Authorization: Bearer $SERVER_API_TOKEN" \
  "http://127.0.0.1:8080/orders?fields=order_id,pack_id,sku,barcode,nombre,deposito_asignado,qty,ready_to_print,printed,date_created&desde=2025-08-01T00:00:00&hasta=2025-08-15T23:59:59"

# Filtros avanzados
curl -H "Authorization: Bearer $SERVER_API_TOKEN" \
  "http://127.0.0.1:8080/orders?deposito_asignado=DEPO&ready_to_print=1&include_printed=0&q_title=zapatilla&q_sku=HF500"
```

Campos soportados para filtros y selección: la API descubre las columnas existentes en `orders_meli` y permite `fields=all` o una lista parcial. Consultá `GET /orders/columns` para ver el catálogo completo.

### Ejecución (desarrollo)

Sugerido con FastAPI + Uvicorn en `server/app.py` (no incluido por defecto, esta sección documenta la interfaz):

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8080 --reload
```

Producción:

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8080 --workers 2
```

### Exponer el backend con ngrok (túnel público)

Requisitos: tener `ngrok` instalado e iniciado sesión (`ngrok config add-authtoken <TOKEN>` una sola vez).

```powershell
ngrok http http://127.0.0.1:8080
# Resultado esperado: URL pública tipo https://xxxx-xx-xx-xx.ngrok-free.app
# Usá esa URL para acceder a:
#  - API:    https://xxxx.ngrok-free.app/orders
#  - UI:     https://xxxx.ngrok-free.app/ui/
#  - Chat:   https://xxxx.ngrok-free.app/chat-now
```

Notas:

- Si definiste `SERVER_API_TOKEN` en `.env`, recordá enviar el header en tus requests:

```bash
curl -H "Authorization: Bearer TU_TOKEN" "https://xxxx.ngrok-free.app/orders?fields=all&limit=50"
```

### Comandos útiles (PowerShell)

- Backend (desarrollo):

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8080 --reload
```

- Backend (producción simple):

```powershell
uvicorn server.app:app --host 0.0.0.0 --port 8080 --workers 2
```

- E2E una pasada, 10 órdenes:

```powershell
python .\run_end_to_end.py --once --limit 10 --log INFO
```

- E2E continua (loop), lote chico y logs DEBUG para diagnóstico:

```powershell
python .\run_end_to_end.py --limit 5 --log DEBUG
```

- Web UI React (dev):

```powershell
pushd .\client; npm install; npm run dev
```

- Build UI React y servir con el backend:

```powershell
pushd .\client; npm install; npm run build
# FastAPI detecta client/dist y lo sirve en /ui
```

### Integración con la GUI

- `.env` de la GUI:
  - `SERVER_API_BASE=http://127.0.0.1:8080`
  - `SERVER_API_TOKEN=tu_token_backend`
  - `SERVER_API_ENABLED=true`
- La GUI consume `GET /orders` con `deposito/from/to` y mapea el JSON directo.
- Movimientos via `POST /dragonfish/stock-movement`.

## Cómo hablarle a la IA (chat)

Endpoint: `POST /api/chat`.

Intents soportados (respuestas locales, sin LLM, cuando aplica):

- **Título por orden**: "título de la orden 123456" → devuelve `orders_meli.nombre`.
- **Impresión de una orden**: "¿la orden 123456 está impresa?" → usa `ready_to_print`/`printed` (mutuamente excluyentes).
- **Impresos HOY**: "¿cuántos paquetes se imprimieron hoy?" → cuenta órdenes y `pack_id` únicos con `printed=1` en el día.
- **Preparar HOY por depósito**: "¿qué tengo que preparar hoy desde DEPO?" → `ready_to_print=1 AND printed=0` para `deposito_asignado=DEPO`.
- **Ventas por SKU**: "¿cuántos se vendieron de NDPMB0E770AR048?".
- **Stock por depósito para un SKU**: "stock NDPMB0E770AR048 en DEPO".
- **Multiventa o individual**: "¿la 123456 es multiventa?".
- **Estado general**: "estado de la 123456".
- **Despachos por día**: "¿se despachó hoy 7790000... o ABC-123?" o "¿cuántos se despacharon el 14/08/2025?".

Tips:

- Para buscar por título, usá comillas: `"mostrame ventas de \"zapatilla runner azul\""` (internamente usa `q_title`).
- Si la pregunta no entra en los intents, el backend agrega contexto de DB y consulta el LLM, pidiéndote más filtros si faltan.

### Troubleshooting API

- 401/403: revisar `SERVER_API_TOKEN` o header Authorization.
- 429/5xx ML: implementar retry/backoff del lado backend; devolver a la GUI un mensaje claro.
- Tiempos altos: ajustar `limit`, cachear `get_item` de ML, usar paginación.
- ROCA/CABA no mueven: confirmar `MOVIMIENTO_TARGET=MELI` y formateo “invertido”.
