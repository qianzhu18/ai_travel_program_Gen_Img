@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "ROOT=%%~fI"

if not defined ROOT exit /b 1

pushd "%ROOT%" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Unable to enter project directory:
  echo         %ROOT%
  pause
  exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
  echo [ERROR] docker command not found.
  popd >nul
  pause
  exit /b 1
)

set "COMPOSE_CMD="
docker compose version >nul 2>nul
if not errorlevel 1 (
  set "COMPOSE_CMD=docker compose"
) else (
  where docker-compose >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] docker compose is unavailable.
    popd >nul
    pause
    exit /b 1
  )
  set "COMPOSE_CMD=docker-compose"
)

call %COMPOSE_CMD% down %*
set "RC=!errorlevel!"
popd >nul
exit /b !RC!
