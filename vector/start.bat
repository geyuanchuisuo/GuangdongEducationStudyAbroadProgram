@echo off
setlocal
cd /d "%~dp0"

set "MINERU_TOOLS_CONFIG_JSON=%~dp0magic-pdf.json"
set "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1"

echo [1/3] Checking Docker engine...
docker info >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Docker is not running. Please start Docker Desktop first.
  exit /b 1
)

echo [2/3] Starting Milvus containers...
docker compose up -d
if errorlevel 1 (
  echo [ERROR] Failed to start. See the messages above.
  exit /b 1
)

echo [3/3] Waiting for health check...
set /a n=0
:wait
set "STATUS="
for /f "delims=" %%i in ('docker inspect -f "{{.State.Health.Status}}" milvus-standalone 2^>nul') do set "STATUS=%%i"
if /i "%STATUS%"=="healthy" goto ok
set /a n+=1
if %n% geq 60 (
  echo [WARN] Timeout. Run: docker compose ps
  exit /b 1
)
ping -n 4 127.0.0.1 >nul
goto wait

:ok
echo.
echo Milvus is ready.
echo   SDK      : http://localhost:19530
echo   WebUI    : http://127.0.0.1:9091/webui/
echo   Config   : %~dp0magic-pdf.json
echo   Models   : %~dp0models
endlocal
