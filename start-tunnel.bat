@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   Yuejiao Project - One-Click Tunnel
echo ========================================
echo.

rem 1. Detect local service port: prefer 8080 (Docker bundled nginx), then 5173 (vite dev)
set PORT=
curl.exe -s -o nul --max-time 2 http://localhost:8080/
if not errorlevel 1 set PORT=8080
if not defined PORT (
  netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
  if not errorlevel 1 set PORT=5173
)
if not defined PORT (
  echo [ERROR] No project service found ^(neither 8080 Docker nor 5173 dev^).
  echo        Start the project first: run start-project.bat, or docker compose up -d
  echo.
  pause
  exit /b 1
)

rem 2. Start localtunnel (no signup, npx; vite allows .loca.lt hosts, nginx does not check Host)
echo Detected local service port: %PORT%
echo Starting localtunnel (no signup needed)...
echo   First run: npx downloads localtunnel automatically (a few seconds)
echo   When you see "your url is: https://xxx.loca.lt" that is the public URL
echo   Press Ctrl+C to stop the tunnel
echo.
echo   For a fixed domain / more stable link, use ngrok ^(signup required^):
echo     Docker mode 8080:  powershell -File scripts\start-ngrok.ps1
echo.
npx --yes localtunnel --port %PORT%
