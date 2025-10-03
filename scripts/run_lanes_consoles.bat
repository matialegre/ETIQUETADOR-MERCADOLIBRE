@echo off
setlocal ENABLEEXTENSIONS ENABLEDELAYEDEXECUTION

rem Launch 3 lanes in separate console windows (ultra / fast / mid) with staggered starts
rem Double-click this file or run from any location

set SCRIPT_DIR=%~dp0
rem Go to repo root (one level up from scripts/)
pushd "%SCRIPT_DIR%.." 1>nul 2>nul

rem Common env for all lanes
set PYTHONUNBUFFERED=1
set MAX_WORKERS_ACCOUNTS=1

rem Enable/disable lanes (1=ON, 0=OFF)
set ENABLE_ULTRA=1
set ENABLE_FAST=1
set ENABLE_MID=1

echo Launching API server and lanes in separate consoles...

rem API server (FastAPI/Uvicorn) - binds 0.0.0.0:8080 for ngrok
start "server_api" cmd /k python -m uvicorn server.app:app --host 0.0.0.0 --port 8080 --reload

rem small stagger before ngrok
timeout /t 2 /nobreak >nul

rem NGROK tunnel to backend
start "ngrok" cmd /k ngrok http --domain=pandemoniumdev.ngrok.dev --region=sa 0.0.0.0:8080

rem small stagger before lanes
timeout /t 3 /nobreak >nul

rem ULTRA lane (most recent orders)
if "%ENABLE_ULTRA%"=="1" start "lane_ultra" cmd /k python ".\PIPELINE_10_ESTABLE\main.py" --limit-acc1 1 --limit-acc2 0 --interval 5 --log INFO

rem small stagger
timeout /t 5 /nobreak >nul

rem FAST lane
if "%ENABLE_FAST%"=="1" start "lane_fast" cmd /k python ".\PIPELINE_10_ESTABLE\main.py" --limit-acc1 50 --limit-acc2 0 --interval 10 --log INFO

rem larger stagger
timeout /t 10 /nobreak >nul

rem MID lane
if "%ENABLE_MID%"=="1" start "lane_mid" cmd /k python ".\PIPELINE_10_ESTABLE\main.py" --limit-acc1 300 --limit-acc2 0 --interval 60 --log INFO

echo All lanes launched. Close a window to stop that lane.

popd 1>nul 2>nul
endlocal
