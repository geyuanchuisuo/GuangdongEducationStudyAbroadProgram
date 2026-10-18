@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo [1/6] Checking prerequisites...
where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js and npm are required.
  pause
  exit /b 1
)
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is required. Install it from https://docs.astral.sh/uv/
  pause
  exit /b 1
)
docker version >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop must be running.
  pause
  exit /b 1
)

echo [1.5/6] Checking legacy Dify instance conflicts...
docker ps --format "{{.Names}}" 2>nul | findstr /b "docker-" >nul 2>nul
if not errorlevel 1 (
  echo [警告] 检测到旧的手动 Dify 实例（docker-* 容器）正在运行。
  echo        它会与项目一体化 Dify 抢占 8081/5003 端口，导致启动失败。
  echo        请先执行: docker compose -p docker down   （数据卷保留）
  pause
  exit /b 1
)

set COMPOSE=docker compose
docker compose version >nul 2>nul
if errorlevel 1 set COMPOSE=docker-compose

echo [2/6] Starting MySQL and Redis...
%COMPOSE% up -d mysql redis
if errorlevel 1 (
  echo Failed to start supporting services.
  pause
  exit /b 1
)

echo [3/6] Installing backend dependencies...
cd /d "%~dp0backend"
uv sync --frozen
if errorlevel 1 goto :error
uv pip install reportlab
if errorlevel 1 goto :error

echo [4/6] Starting backend on port 8000...
start "Yuejiao Backend" cmd /k "set DATABASE_URL=mysql+aiomysql://root:420821@localhost:59000/GuangdongEducationStudyAbroadProgram&& .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 8 /nobreak >nul

echo [5/6] Creating four test accounts...
.venv\Scripts\python.exe ..\scripts\create_frontend_test_accounts.py
if errorlevel 1 goto :error

echo [6/6] Installing frontend dependencies and starting the website...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 goto :error
start "Yuejiao Frontend" cmd /k "npm run dev -- --host 0.0.0.0"
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"

echo.
echo Startup completed.
echo Keep the Backend and Frontend windows open.
echo Test accounts:
echo   PROSPECT  13810000001 / Test@123456
echo   STUDENT   13810000002 / Test@123456
echo   EMPLOYEE  13810000003 / Test@123456
echo   MANAGER   13810000004 / Test@123456
echo.
pause
exit /b 0

:error
echo Startup failed. Review the messages above.
pause
exit /b 1
