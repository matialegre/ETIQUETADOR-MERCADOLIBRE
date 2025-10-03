# Runs two lanes (Fast + Mid) of the pipeline in parallel, with auto-restart and timestamped logs.
# Usage: Right-click > Run with PowerShell (or: powershell -ExecutionPolicy Bypass -File .\scripts\run_pipeline_lanes.ps1)

$ErrorActionPreference = 'Stop'

# Working dir = repo root (assumes script placed under scripts/)
Set-Location -Path (Join-Path $PSScriptRoot '..')

# Common env: real-time logs and minimal concurrency to reduce races
$env:PYTHONUNBUFFERED = '1'
$env:MAX_WORKERS_ACCOUNTS = '1'

# Paths
$scriptPath = Join-Path (Get-Location) 'PIPELINE_10_ESTABLE\main.py'
$logsDir   = Join-Path (Get-Location) 'logs\lanes'
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

# Lanes
$ultraArgs = '--limit-acc1 10  --limit-acc2 0 --interval 5  --log INFO'
$fastArgs  = '--limit-acc1 50  --limit-acc2 0 --interval 10 --log INFO'
$midArgs   = '--limit-acc1 300 --limit-acc2 0 --interval 60 --log INFO'

function Start-LaneJob {
    param(
        [Parameter(Mandatory=$true)][string]$LaneName,
        [Parameter(Mandatory=$true)][string]$Args,
        [int]$StartDelaySeconds = 0
    )

    $jobScript = {
        param($scriptPath, $args, $logsDir, $lane, $startDelay)
        $ErrorActionPreference = 'Continue'
        $env:PYTHONUNBUFFERED = '1'
        $env:MAX_WORKERS_ACCOUNTS = '1'
        New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
        if ($startDelay -gt 0) {
            Write-Host "[${lane}] initial stagger delay ${startDelay}s"
            Start-Sleep -Seconds $startDelay
        }
        while ($true) {
            try {
                $ts  = Get-Date -Format 'yyyyMMdd_HHmmss'
                $log = Join-Path $logsDir ("${lane}_$ts.log")
                Write-Host "[${lane}] starting iteration at $ts -> $log"
                & python $scriptPath $args *>&1 | Tee-Object -File $log
            }
            catch {
                $ts  = Get-Date -Format 'yyyyMMdd_HHmmss'
                $elog = Join-Path $logsDir ("${lane}_err_$ts.log")
                $_ | Out-File -FilePath $elog -Append
            }
            # pequeño jitter para evitar sincronización perfecta entre lanes
            $base = 5
            $jitter = Get-Random -Minimum 0 -Maximum 5
            Start-Sleep -Seconds ($base + $jitter)
        }
    }

    Start-Job -Name "lane_$LaneName" -ScriptBlock $jobScript -ArgumentList $scriptPath, $Args, $logsDir, $LaneName, $StartDelaySeconds | Out-Null
}

Write-Host 'Launching lanes...'
Start-LaneJob -LaneName 'ultra' -Args $ultraArgs -StartDelaySeconds 0
Start-LaneJob -LaneName 'fast'  -Args $fastArgs  -StartDelaySeconds 5
Start-LaneJob -LaneName 'mid'   -Args $midArgs   -StartDelaySeconds 15

Write-Host 'Jobs running:'
Get-Job | Format-Table Id, Name, State, HasMoreData -AutoSize
Write-Host 'Use Receive-Job -Id <id> -Keep to tail logs, or Stop-Job -Name lane_fast/mid to stop.'

# Mantener esta consola viva para que los jobs sigan corriendo.
# Si cerrás la ventana, los jobs se paran. Presioná Ctrl+C para cancelar.
try {
    Write-Host "Press Ctrl+C to stop lanes. This window must stay open."
    # Mantener la consola viva sin pedir Ids (evita prompt de Wait-Job)
    while ($true) { Start-Sleep -Seconds 3600 }
}
catch {
    Write-Host "Stopping lanes..."
}
finally {
    # Intentar detener los jobs al salir
    Get-Job -Name lane_ultra, lane_fast, lane_mid -ErrorAction SilentlyContinue | Stop-Job -Force -ErrorAction SilentlyContinue
}
