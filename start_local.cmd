@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ========================================
echo   AI 图片批量生成系统 - Windows 一键启动
echo ========================================
echo.

where py >nul 2>nul
if %errorlevel% neq 0 (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Python（py/python）。
    echo 请先安装 Python 3.10+，并勾选 "Add Python to PATH"。
    pause
    exit /b 1
  )
  set "PY_CMD=python"
) else (
  set "PY_CMD=py -3"
)

where npm >nul 2>nul
if %errorlevel% neq 0 (
  echo [ERROR] 未检测到 npm。
  echo 请先安装 Node.js 18+（建议 LTS）。
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [WARN] 未找到 .env，已从 .env.example 自动创建。
  ) else (
    echo [ERROR] 缺少 .env 和 .env.example。
    pause
    exit /b 1
  )
)

if exist "scripts\apply_access_keys.py" (
  if exist "可行性分析\AccessKey.txt" (
    echo [INFO] 检测到 可行性分析\AccessKey.txt，正在自动写入 .env ...
    %PY_CMD% "scripts\apply_access_keys.py" --access-key-file "可行性分析\AccessKey.txt" --env-file ".env" --env-example ".env.example" --quiet
  )
)

echo [1/5] 准备 Python 虚拟环境...
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv 2>nul
  if %errorlevel% neq 0 (
    python -m venv .venv
    if %errorlevel% neq 0 (
      echo [ERROR] 创建虚拟环境失败。
      pause
      exit /b 1
    )
  )
)

echo [2/5] 安装后端依赖（首次会较慢）...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\pip.exe" install -r "backend\requirements.txt"
if %errorlevel% neq 0 (
  echo [ERROR] 后端依赖安装失败。
  pause
  exit /b 1
)

echo [3/5] 安装前端依赖（首次会较慢）...
if not exist "frontend\node_modules" (
  pushd "frontend"
  call npm ci
  set "NPM_RC=!errorlevel!"
  popd
  if not "!NPM_RC!"=="0" (
    echo [ERROR] 前端依赖安装失败。
    pause
    exit /b 1
  )
)

echo [4/5] 初始化数据库...
set "DEBUG=false"
".venv\Scripts\python.exe" "scripts\init_db.py"
if %errorlevel% neq 0 (
  echo [ERROR] 数据库初始化失败，请检查 .env 配置。
  pause
  exit /b 1
)

echo [5/5] 启动服务...
set "P8000="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do set "P8000=%%a"
if not defined P8000 (
  start "AI Backend :8000" cmd /k "cd /d \"%ROOT%backend\" && set DEBUG=false && \"%ROOT%.venv\Scripts\python.exe\" -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
) else (
  echo [INFO] 后端端口 8000 已在监听，跳过启动。
)

set "P3000="
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do set "P3000=%%a"
if not defined P3000 (
  start "AI Frontend :3000" cmd /k "cd /d \"%ROOT%frontend\" && npm run dev -- --host 0.0.0.0 --port 3000"
) else (
  echo [INFO] 前端端口 3000 已在监听，跳过启动。
)

echo.
echo ========================================
echo 启动完成：
echo   前端: http://localhost:3000
echo   后端: http://localhost:8000
echo 停止服务：双击 stop_local.cmd
echo ========================================
echo.
pause
