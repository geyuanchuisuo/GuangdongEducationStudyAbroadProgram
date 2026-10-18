@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo   粤教留学项目 - 一键内网穿透
echo ========================================
echo.

rem 1. 探测本地服务端口：优先 8080（Docker 一体化 nginx），其次 5173（本地 dev 前端）
set PORT=
curl.exe -s -o nul --max-time 2 http://localhost:8080/
if not errorlevel 1 set PORT=8080
if not defined PORT (
  netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>nul
  if not errorlevel 1 set PORT=5173
)
if not defined PORT (
  echo [错误] 未检测到项目服务（8080 Docker 一体化 / 5173 本地 dev 均未监听）。
  echo        请先启动项目：双击 start-project.bat，或 docker compose up -d
  echo.
  pause
  exit /b 1
)

rem 2. 启动 localtunnel（免注册，npx 直跑；vite 已放行 .loca.lt 子域，nginx 不校验 Host）
echo 检测到本地服务端口: %PORT%
echo 使用 localtunnel（免注册）启动穿透...
echo   首次运行 npx 会自动下载 localtunnel（约几秒）
echo   看到 "your url is: https://xxx.loca.lt" 即为公网地址，发给任何人即可访问
echo   按 Ctrl+C 停止穿透
echo.
echo   如需固定域名/更稳定链路，可改用 ngrok（需注册）：
echo     8080 Docker 模式：  powershell -File scripts\start-ngrok.ps1
echo.
npx --yes localtunnel --port %PORT%
