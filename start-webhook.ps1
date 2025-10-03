#requires -version 5
# Script de arranque para servidor de webhooks (port 8080)
# Proyecto: C:\Users\Mundo Outdoor\CascadeProjects\meli_stock_pipeline
# Uso: clic derecho > Run with PowerShell (o ejecutar desde una consola de PowerShell)

$ErrorActionPreference = 'Stop'

# 1) Posicionarse en el root del proyecto
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

# 2) Crear venv si no existe
$venvPath = Join-Path $proj ".venv"
if (!(Test-Path $venvPath)) {
  Write-Host "Creando entorno virtual en $venvPath" -ForegroundColor Cyan
  py -3 -m venv .venv
}

# 3) Actualizar pip y deps mínimas del proyecto
$python = Join-Path $venvPath "Scripts/python.exe"
Write-Host "Actualizando pip..." -ForegroundColor Cyan
& $python -m pip install -U pip

# Instalar requirements del proyecto (incluye pyodbc, requests, fastapi, uvicorn, dotenv)
$req = Join-Path $proj "requirements.txt"
if (Test-Path $req) {
  Write-Host "Instalando requirements.txt..." -ForegroundColor Cyan
  & $python -m pip install -r $req
} else {
  Write-Host "Instalando paquetes necesarios..." -ForegroundColor Cyan
  & $python -m pip install fastapi uvicorn[standard] requests pyodbc python-dotenv
}

# 4) Variables de entorno (editá estos valores a tu necesidad)
# Modo de procesamiento (no bloquea en FastAPI, pero sirve para lógica futura)
$env:SYNC_PROCESSING = "true"

# Cadena de conexión a SQL Server (seleccioná una de estas 2 variables que tu app usa)
# Preferida por el código: SQLSERVER_APP_CONN_STR
# Alternativa:           SQLSERVER_CONN_STR
if (-not $env:SQLSERVER_APP_CONN_STR -and -not $env:SQLSERVER_CONN_STR) {
  $env:SQLSERVER_APP_CONN_STR = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=mi-servidor,1433;DATABASE=mi_db;UID=mi_user;PWD=mi_pwd;TrustServerCertificate=yes"
}

# Token de ML (opcional, para enriquecer Articulo/Color/Talle)
# $env:ML_ACCESS_TOKEN = "<TU_TOKEN>"

# 5) Iniciar el servidor FastAPI con Uvicorn en 127.0.0.1:8080
Write-Host "Levantando Uvicorn en 127.0.0.1:8080 (server.app:app)..." -ForegroundColor Green
& $python -m uvicorn server.app:app --host 127.0.0.1 --port 8080

# 6) Mensaje sobre ngrok (ejecutar en otra consola)
Write-Host "En otra consola, ejecutar ngrok:" -ForegroundColor Yellow
Write-Host "    ngrok http --domain=pandemoniumdev.ngrok.dev --region=sa 127.0.0.1:8080" -ForegroundColor Yellow

# 7) Rutas útiles
Write-Host "Health:   https://pandemoniumdev.ngrok.dev/health" -ForegroundColor Cyan
Write-Host "Webhook:  https://pandemoniumdev.ngrok.dev/meli/callback" -ForegroundColor Cyan
Write-Host "OAuth:    https://pandemoniumdev.ngrok.dev/meli/oauth/callback" -ForegroundColor Cyan
