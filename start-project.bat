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
  echo [WARN] Legacy manual Dify containers ^(docker-*^) are running.
  echo        They conflict with the bundled Dify on ports 8081/5003.
  echo        Run first: docker compose -p docker down   ^(volumes kept^)
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
rem Reuse a healthy backend already on 8000 (e.g. Docker stack edu-backend)
curl.exe -s -o nul --max-time 2 http://localhost:8000/health
if not errorlevel 1 (
  echo        Port 8000 already serving a healthy backend, reusing it.
  goto :backend_ready
)
start "Yuejiao Backend" cmd /k "set DATABASE_URL=mysql+aiomysql://root:420821@localhost:59000/GuangdongEducationStudyAbroadProgram&& .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
rem Wait for backend readiness (up to 60s) instead of a fixed sleep
set /a _tries=0
:wait_backend
curl.exe -s -o nul --max-time 2 http://localhost:8000/health
if not errorlevel 1 goto :backend_ready
set /a _tries+=1
if %_tries% geq 30 (
  echo [ERROR] Backend not ready within 60s. Check the "Yuejiao Backend" window log.
  goto :error
)
ping -n 3 127.0.0.1 >nul
goto :wait_backend
:backend_ready
echo        Backend is ready.

echo [5/6] Creating four test accounts...
.venv\Scripts\python.exe ..\scripts\create_frontend_test_accounts.py
if errorlevel 1 goto :error

echo [6/6] Installing frontend dependencies and starting the website...
cd /d "%~dp0frontend"
if not exist node_modules (
  call npm install
  if errorlevel 1 goto :error
)
rem Reuse an existing frontend already listening on 5173
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
if not errorlevel 1 goto :frontend_ready
start "Yuejiao Frontend" cmd /k "npm run dev -- --host 0.0.0.0"
rem Wait for frontend readiness (up to 40s); keep this loop top-level (no parenthesized block)
set /a _tries=0
:wait_frontend
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
if not errorlevel 1 goto :frontend_ready
set /a _tries+=1
if %_tries% geq 20 (
  echo [ERROR] Frontend not ready within 40s. Check the "Yuejiao Frontend" window log.
  goto :error
)
ping -n 3 127.0.0.1 >nul
goto :wait_frontend
:frontend_ready
start "" "http://localhost:5173"

echo.
echo Startup completed.
echo Website:  http://localhost:5173  (opened automatically)
echo Backend:  http://localhost:8000  (API docs: http://localhost:8000/docs)
echo Keep the Backend and Frontend windows open.
echo.
echo Need public access? Run start-tunnel.bat in the project root for one-click tunneling.
echo.
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
