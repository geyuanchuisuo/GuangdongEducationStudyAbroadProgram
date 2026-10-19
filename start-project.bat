@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem ============================================================
rem 粤教留学 一站式启动（完整一键拉起）
rem
rem 沙箱边界（哪些服务在沙箱外、哪些在沙箱内）：
rem   [沙箱外 / Docker 容器] mysql、redis、backend、nginx、Dify 全家桶
rem     （api/worker/web/db_postgres/dify_redis/weaviate/sandbox/ssrf_proxy/
rem       plugin_daemon/agent_backend/dify_nginx/dify-init）
rem     由 Docker Desktop 守护进程托管，容器文件系统与本地进程沙箱无关，
rem     全部通过 docker compose 一条命令拉起。
rem   [沙箱内 / 本地进程] vite dev(5173)、localtunnel(公网隧道)
rem     属于轻量本地 node 进程；npm/npx 默认全局缓存目录在受限环境下
rem     不可写（EPERM），本脚本统一把 npm_config_cache 重定向到 logs\npm-cache，
rem     对普通双击运行环境无副作用。
rem ============================================================

echo [1/7] Checking prerequisites...
where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js and npm are required.
  pause
  exit /b 1
)
docker version >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop must be running.
  pause
  exit /b 1
)
docker ps --format "{{.Names}}" 2>nul | findstr /b "docker-" >nul 2>nul
if not errorlevel 1 (
  echo [WARN] Legacy manual Dify containers ^(docker-*^) are running.
  echo        They conflict with the bundled Dify on ports 8081/5003.
  echo        Run first: docker compose -p docker down   ^(volumes kept^)
  pause
  exit /b 1
)

rem npm/npx 缓存重定向（沙箱内可写；普通环境同样可用）
if not exist "%~dp0logs" mkdir "%~dp0logs"
set "npm_config_cache=%~dp0logs\npm-cache"

echo [2/7] Ensuring environment files...
rem 根 .env 缺失时必须补建：没有它 COMPOSE_PROFILES 不生效，
rem Dify 的 db_postgres/weaviate 不会启动，dify-init 必失败并阻塞 backend。
if not exist "%~dp0.env" (
  echo        Root .env missing - creating from .env.example ^(enables Dify postgres/weaviate profiles^)
  copy /y "%~dp0.env.example" "%~dp0.env" >nul
  if errorlevel 1 goto :error
)
rem Dify 凭据文件缺失时补模板并阻断：模型三项必须客户填全，否则 dify-init 失败阻塞 backend（项目硬性约定）。
if not exist "%~dp0dify\docker\.env" (
  echo        dify\docker\.env missing - creating from .env.example
  copy /y "%~dp0dify\docker\.env.example" "%~dp0dify\docker\.env" >nul
  echo [ACTION REQUIRED] Fill DIFY_MODEL_API_KEY / DIFY_MODEL_BASE_URL / DIFY_MODEL_NAME in dify\docker\.env, then re-run this script.
  pause
  exit /b 1
)
findstr /r /c:"^DIFY_MODEL_API_KEY=." "%~dp0dify\docker\.env" >nul 2>nul
if errorlevel 1 (
  echo [ACTION REQUIRED] DIFY_MODEL_API_KEY is empty in dify\docker\.env - dify-init would fail and block backend startup.
  pause
  exit /b 1
)

echo [3/7] Starting full Docker stack ^(MySQL/Redis/Dify/backend/nginx^)...
echo        First run builds images and initializes Dify - may take several minutes.
docker compose up -d
if errorlevel 1 (
  echo Failed to start the compose stack. Check: docker compose ps ^&^& docker logs edu-dify-init
  pause
  exit /b 1
)

echo [4/7] Building frontend assets for nginx :8080...
cd /d "%~dp0frontend"
if not exist node_modules (
  call npm install
  if errorlevel 1 goto :error
)
call npm run build
if errorlevel 1 goto :error
cd /d "%~dp0"

echo [5/7] Waiting for backend health on :8000 ^(empty DB auto-seeds on cold start^)...
set /a _tries=0
:wait_backend
curl.exe -s -o nul --max-time 2 http://localhost:8000/health
if not errorlevel 1 goto :backend_ready
set /a _tries+=1
if %_tries% geq 90 (
  echo [ERROR] Backend not healthy within 180s. Check: docker logs edu-backend
  goto :error
)
ping -n 3 127.0.0.1 >nul
goto :wait_backend
:backend_ready
echo        Backend is ready.
rem 种子保险：seed_all 幂等（已有数据自动跳过）；4 个演示账号 13810000001-04 已含在种子链中
docker exec edu-backend /app/.venv/bin/python -m scripts.seed_all
if errorlevel 1 (
  echo [ERROR] Seed injection failed. Check: docker logs edu-backend
  goto :error
)

echo [6/7] Starting vite dev server :5173 ^(dev convenience; nginx :8080 is the delivery entry^)...
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
if not errorlevel 1 goto :frontend_ready
start "Yuejiao Frontend" /d "%~dp0frontend" cmd /k "npm run dev -- --host 0.0.0.0"
set /a _tries=0
:wait_frontend
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
if not errorlevel 1 goto :frontend_ready
set /a _tries+=1
if %_tries% geq 20 (
  echo [WARN] vite dev not ready within 40s ^(window spawn may be restricted^). Delivery entry nginx :8080 is unaffected.
  goto :frontend_ready
)
ping -n 3 127.0.0.1 >nul
goto :wait_frontend
:frontend_ready

echo [7/7] Starting public tunnel for remote visitors...
rem Prefer the Docker nginx build on 8080; fall back to the vite dev server on 5173.
set PORT=
curl.exe -s -o nul --max-time 2 http://localhost:8080/
if not errorlevel 1 set PORT=8080
if not defined PORT set PORT=5173
echo        Tunnel target port: %PORT%
del /q "%~dp0logs\tunnel.log" 2>nul
start "Yuejiao Tunnel" cmd /k "npx --yes localtunnel --port %PORT% > "%~dp0logs\tunnel.log" 2>&1"
set /a _tries=0
set PUBLIC_URL=
:wait_tunnel
for /f "tokens=4" %%u in ('findstr /c:"your url is:" "%~dp0logs\tunnel.log" 2^>nul') do set PUBLIC_URL=%%u
if defined PUBLIC_URL goto :tunnel_ready
set /a _tries+=1
if %_tries% geq 30 (
  echo [WARN] Tunnel URL not detected within 60s. Check the "Yuejiao Tunnel" window, or run start-tunnel.bat.
  goto :tunnel_done
)
ping -n 3 127.0.0.1 >nul
goto :wait_tunnel
:tunnel_ready
echo        Public URL: %PUBLIC_URL%
rem localtunnel shows visitors a password page; the password is this machine's public IP
set TUNNEL_PWD=
for /f "delims=" %%p in ('curl.exe -s --max-time 5 https://loca.lt/mytunnelpassword') do set TUNNEL_PWD=%%p
:tunnel_done
start "" "http://localhost:8080"

echo.
echo Startup completed.
echo Local:    http://localhost:8080  ^(nginx delivery entry, opened automatically^)
echo Dev:      http://localhost:5173  ^(vite hot-reload, optional^)
echo Backend:  http://localhost:8000  ^(API docs: http://localhost:8000/docs^)
echo Dify:     http://localhost:8081  ^(console^)
if defined PUBLIC_URL (
  echo Public:   %PUBLIC_URL%  ^(share with remote visitors^)
  if defined TUNNEL_PWD echo Tunnel password for visitors: %TUNNEL_PWD%
) else (
  echo Public:   tunnel not ready - see the "Yuejiao Tunnel" window, or run start-tunnel.bat
)
echo Keep the Frontend and Tunnel windows open; Docker services run in the background.
echo.
echo Test accounts ^(password for all: Test@123456^):
echo   PROSPECT  13810000001
echo   STUDENT   13810000002
echo   EMPLOYEE  13810000003
echo   MANAGER   13810000004
echo.
pause
exit /b 0

:error
echo Startup failed. Review the messages above.
pause
exit /b 1
