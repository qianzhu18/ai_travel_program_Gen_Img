@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%.") do set "ROOT=%%~fI"

if not defined ROOT (
  echo [ERROR] Unable to resolve project directory.
  exit /b 1
)

pushd "%ROOT%" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Unable to enter project directory:
  echo         %ROOT%
  echo [ERROR] The path might contain unsupported characters.
  pause
  exit /b 1
)

if not exist "docker-compose.yml" (
  echo [ERROR] docker-compose.yml not found in:
  echo         %CD%
  popd >nul
  pause
  exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
  echo [ERROR] docker command not found. Please install Docker Desktop first.
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
    echo         Install Docker Compose v2 or docker-compose.
    popd >nul
    pause
    exit /b 1
  )
  set "COMPOSE_CMD=docker-compose"
)

if not exist ".env" (
  if exist ".env.example" (
    copy ".env.example" ".env" >nul
    echo [WARN] .env not found. Created from .env.example. Fill API keys and rerun.
  )
)

if not exist "data" mkdir "data" >nul 2>nul
if not exist "models" mkdir "models" >nul 2>nul

call %COMPOSE_CMD% up -d --build %*
set "RC=!errorlevel!"
popd >nul
if not "!RC!"=="0" exit /b !RC!

echo.
echo ==================== DOCKER STARTED ====================
echo Frontend : http://localhost:3000
echo Backend  : http://localhost:8000
echo Stop all : stop_docker.cmd
echo ========================================================
exit /b 0
