@echo off
setlocal EnableExtensions
chcp 65001 >nul

echo ========================================
echo   AI 图片批量生成系统 - Windows 停止脚本
echo ========================================
echo.

call :KillPort 8000 后端
call :KillPort 3000 前端
call :KillPort 8090 IOPaint

echo.
echo 所有相关端口进程已尝试关闭。
echo.
pause
exit /b 0

:KillPort
set "PORT=%~1"
set "NAME=%~2"
set "FOUND=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT% ^| findstr LISTENING') do (
  set "FOUND=1"
  echo [INFO] 关闭 %NAME% (端口 %PORT%)，PID=%%a
  taskkill /F /PID %%a >nul 2>nul
)
if "%FOUND%"=="0" (
  echo [INFO] %NAME% (端口 %PORT%) 未运行
)
goto :eof
