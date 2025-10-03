#requires -version 5
# Script para correr PIPELINE 10 en loop con paralelismo multi-cuenta
# Uso típico:
#   .\start-pipeline10.ps1 -Limit 30 -Interval 60 -WorkersAccounts 2 -ProcessEveryNLowTraffic 1 -Log INFO

param(
  [int]$Limit = 30,
  [int]$Interval = 60,
  [ValidateSet("DEBUG","INFO","WARNING","ERROR")]
  [string]$Log = "INFO",
  [int]$WorkersAccounts = 2,
  [int]$ProcessEveryNLowTraffic = 1,
  [switch]$UseVenv = $false,
  [switch]$Once = $false
)

$ErrorActionPreference = 'Stop'

# 1) Posicionarse en el root del proyecto
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

# 2) Resolver Python a usar
if ($UseVenv) {
  $venvPath = Join-Path $proj ".venv"
  if (!(Test-Path $venvPath)) {
    Write-Host "Creando entorno virtual en $venvPath" -ForegroundColor Cyan
    py -3 -m venv .venv
  }
  $python = Join-Path $venvPath "Scripts/python.exe"
  # 3) (Opcional) Asegurar dependencias solo si se usa venv
  Write-Host "(venv) Actualizando pip y requirements..." -ForegroundColor Cyan
  & $python -m pip install -U pip
  $req = Join-Path $proj "requirements.txt"
  if (Test-Path $req) {
    & $python -m pip install -r $req
  }
} else {
  # Usar Python del sistema (como venías haciendo)
  $python = "python"
  Write-Host "Usando Python del sistema: $python" -ForegroundColor Yellow
}

# 4) Variables de entorno para este proceso (paralelismo y frecuencia)
$env:MAX_WORKERS_ACCOUNTS = "$WorkersAccounts"
$env:PROCESS_EVERY_N_CYCLES_786086955 = "$ProcessEveryNLowTraffic"

# 5) Ejecutar pipeline en loop
Write-Host "Lanzando PIPELINE 10 (limit=$Limit, interval=${Interval}s, log=$Log, once=$Once)" -ForegroundColor Green
if ($Once) {
  & $python "PIPELINE_10_ESTABLE/main.py" --limit $Limit --once --log $Log
} else {
  & $python "PIPELINE_10_ESTABLE/main.py" --limit $Limit --interval $Interval --log $Log
}
