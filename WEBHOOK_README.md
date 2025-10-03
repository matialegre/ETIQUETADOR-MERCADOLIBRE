# Webhook Mercado Libre · Proyecto meli_stock_pipeline (puerto 8080)

Guía corta y clara para levantar mañana el servidor de webhooks y validar end-to-end con ngrok.

## Qué ya está hecho
- Backend unificado en FastAPI (no Flask) en `server/app.py`.
- Endpoints implementados:
  - `POST /meli/callback` → recibe webhooks de MercadoLibre, inserta en SQL Server (`dbo.meli_webhook_events`) y responde 200.
  - `GET|POST /meli/oauth/callback` → callback OAuth dummy (evita 404 y devuelve 200, útil para pruebas).
  - `GET /debug/which-ui` y UI varias (no necesarias para webhooks).
- Inserción en DB: función `_insert_webhook_event()` dentro de `server/app.py` usa `SQLSERVER_APP_CONN_STR` (preferido) o `SQLSERVER_CONN_STR`.
- Dominio ngrok reservado: `https://pandemoniumdev.ngrok.dev`.

## Requisitos
- Windows + PowerShell
- ngrok v3 con authtoken configurado y dominio reservado activo
- SQL Server accesible y driver ODBC 17/18 instalado
- Python 3 con venv en este proyecto (el script lo crea si falta)

## Variables de entorno
- `SQLSERVER_APP_CONN_STR` (preferida) o `SQLSERVER_CONN_STR` (alternativa)
  - Ejemplo:
    ```
    DRIVER={ODBC Driver 17 for SQL Server};SERVER=mi-servidor,1433;DATABASE=mi_db;UID=mi_user;PWD=mi_pwd;TrustServerCertificate=yes
    ```
- `ML_ACCESS_TOKEN` (opcional) si más adelante se enriquece desde ML (la app actual persiste el payload y datos básicos; el enriquecimiento avanzado existe en otra variante Flask, no se necesita para guardar eventos).
- `SYNC_PROCESSING` se setea a `true` por el script (no bloquea esta app, pero queda listo para futuras lógicas).

## Cómo iniciar (puerto 8080)
Usá el script que dejé listo:

```powershell
# En C:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline
./start-webhook.ps1
```
El script:
- Crea `.venv` si falta.
- Instala dependencias desde `requirements.txt` (FastAPI, Uvicorn, requests, pyodbc, dotenv).
- Exporta variables por defecto si no están (podés editar el archivo para pegar tu cadena ODBC).
- Levanta Uvicorn en `127.0.0.1:8080` sirviendo `server.app:app`.

En otra consola PowerShell, levantá ngrok apuntando a 8080:
```powershell
ngrok http --domain=pandemoniumdev.ngrok.dev --region=sa 127.0.0.1:8080
```
Deberías ver: `Forwarding https://pandemoniumdev.ngrok.dev -> http://127.0.0.1:8080`.

Inspector de tráfico: http://127.0.0.1:4040

## Configurar Mercado Libre
- URL de webhooks: `https://pandemoniumdev.ngrok.dev/meli/callback`
- Tópicos: `orders_v2`, `shipments`
- Content-Type: `application/json`
- (Opcional) Redirect OAuth: `https://pandemoniumdev.ngrok.dev/meli/oauth/callback`

## Pruebas rápidas (PowerShell)
Salud (si exponés uno, opcional): en esta app no hay `/health` por defecto, usar pruebas directas del endpoint webhook.

Webhook de prueba (orders_v2):
```powershell
Invoke-WebRequest -Uri "https://pandemoniumdev.ngrok.dev/meli/callback" `
  -Method POST -ContentType "application/json" `
  -Body '{ "topic":"orders_v2","resource":"/orders/2000012722971284","user_id":209611492,"application_id":8063857234740063 }'
```

Webhook de prueba (shipments):
```powershell
Invoke-WebRequest -Uri "https://pandemoniumdev.ngrok.dev/meli/callback" `
  -Method POST -ContentType "application/json" `
  -Body '{ "topic":"shipments","resource":"/shipments/45367316224","user_id":209611492,"application_id":8063857234740063 }'
```

OAuth (dummy):
```powershell
Invoke-WebRequest -Uri "https://pandemoniumdev.ngrok.dev/meli/oauth/callback?code=abc&state=xyz"
```

## Qué deberías ver
- Respuestas 200 OK en las pruebas.
- En SQL Server:
```sql
SELECT TOP 50 id, received_at, topic, resource, resource_id, status, attempts
FROM dbo.meli_webhook_events
ORDER BY id DESC;
```
Deberían aparecer filas nuevas con `resource_id` real cuando lleguen notificaciones reales o simuladas.

## Notas y diferencias con la versión Flask anterior
- Esta app es FastAPI y ya trae rutas:
  - `POST /meli/callback` y `GET|POST /meli/oauth/callback` (dummy) implementadas en `server/app.py`.
  - Inserción en DB usando `pyodbc` y la cadena `SQLSERVER_APP_CONN_STR` o `SQLSERVER_CONN_STR`.
- La versión Flask (`C:\meli-webhook\app.py`) tenía logging a archivos y enriquecimiento avanzado.
  - Si querés portar el enriquecimiento a esta app, se puede añadir un worker con requests a ML.
  - Para persistencia básica de eventos en DB, con esta FastAPI ya alcanza.

## Troubleshooting
- Si ngrok muestra `-> http://127.0.0.1:8080` pero la llamada falla:
  - Verificá que Uvicorn esté en ejecución en esa consola.
  - Revisá firewall local/bloqueos corporativos.
- Si no inserta en DB:
  - Revisá que `SQLSERVER_APP_CONN_STR` o `SQLSERVER_CONN_STR` esté seteado correctamente.
  - Driver ODBC instalado (17/18). Reiniciá la consola tras instalar.
- 401 al llamar APIs de ML: setear/actualizar `ML_ACCESS_TOKEN` (solo si implementás enriquecimiento).

## Archivos relevantes
- `server/app.py` → FastAPI, rutas `/meli/callback` y `/meli/oauth/callback`, DB helper `_insert_webhook_event()`.
- `start-webhook.ps1` → arranque rápido en 8080 y recordatorio ngrok.
- `requirements.txt` → dependencias (pyodbc, requests, fastapi, uvicorn, dotenv).
