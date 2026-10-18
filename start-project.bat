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
rem 8000 已被占用且健康检查通过（如 Docker 一体化栈的 edu-backend）时直接复用，避免端口冲突
curl.exe -s -o nul --max-time 2 http://localhost:8000/health
if not errorlevel 1 (
  echo        Port 8000 already serving a healthy backend, reusing it.
  goto :backend_ready
)
start "Yuejiao Backend" cmd /k "set DATABASE_URL=mysql+aiomysql://root:420821@localhost:59000/GuangdongEducationStudyAbroadProgram&& .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
rem 等待后端就绪（最多 60 秒），取代固定等待
set /a _tries=0
:wait_backend
curl.exe -s -o nul --max-time 2 http://localhost:8000/health
if not errorlevel 1 goto :backend_ready
set /a _tries+=1
if %_tries% geq 30 (
  echo [错误] 后端 60 秒内未就绪，请查看 "Yuejiao Backend" 窗口日志。
  goto :error
)
timeout /t 2 /nobreak >nul
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
rem 5173 已被占用时直接复用现有前端
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
if errorlevel 1 (
  start "Yuejiao Frontend" cmd /k "npm run dev -- --host 0.0.0.0"
  rem 等待前端就绪（最多 40 秒）
  set /a _tries=0
  :wait_frontend
  netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
  if not errorlevel 1 goto :frontend_ready
  set /a _tries+=1
  if %_tries% geq 20 (
    echo [错误] 前端 40 秒内未就绪，请查看 "Yuejiao Frontend" 窗口日志。
    goto :error
  )
  timeout /t 2 /nobreak >nul
  goto :wait_frontend
)
:frontend_ready
start "" "http://localhost:5173"

echo.
echo Startup completed.
echo Website:  http://localhost:5173  (opened automatically)
echo Backend:  http://localhost:8000  (API docs: http://localhost:8000/docs)
echo Keep the Backend and Frontend windows open.
echo.
echo 需要公网访问？双击运行根目录 start-tunnel.bat 即可一键内网穿透。
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
