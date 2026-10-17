# 一键构建并启动服务（本地开发环境）
# 用法：在项目根目录执行 .\scripts\build-and-serve.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  粤教留学项目 - 构建并启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

# 1. 检查 frontend/node_modules
Write-Host "`n[1/4] 检查前端依赖..." -ForegroundColor Yellow
if (!(Test-Path "frontend/node_modules")) {
    Write-Host "  首次运行，安装前端依赖..."
    Set-Location frontend
    npm install
    Set-Location ..
}

# 2. 构建前端
Write-Host "`n[2/4] 构建前端（生产模式）..." -ForegroundColor Yellow
Set-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 前端构建失败" -ForegroundColor Red
    Set-Location ..
    exit 1
}
Set-Location ..

# 3. 检查 dist 目录
if (!(Test-Path "frontend/dist/index.html")) {
    Write-Host "[错误] 构建产物缺失：frontend/dist/index.html" -ForegroundColor Red
    exit 1
}

# 4. 启动 Docker 服务
Write-Host "`n[3/4] 启动 Docker 服务（mysql + redis + backend + nginx）..." -ForegroundColor Yellow
docker compose up -d

# 5. 等待后端就绪
Write-Host "`n[4/4] 等待服务就绪..." -ForegroundColor Yellow
$maxWait = 60
$waited = 0
$healthy = $false
while ($waited -lt $maxWait) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    } catch { }
    Start-Sleep -Seconds 2
    $waited += 2
    Write-Host "  等待中... ${waited}s" -NoNewline
    Write-Host "`r" -NoNewline
}

Write-Host ""
if ($healthy) {
    Write-Host "[成功] 服务已启动！" -ForegroundColor Green
    Write-Host "  本地访问：http://localhost:8080  （80 端口被本机 Dify 占用，项目 nginx 用 8080）"
    Write-Host "  后端 API：http://localhost:8080/api/v1/docs"
    Write-Host ""
    Write-Host "如需公网访问，请运行：" -ForegroundColor Cyan
    Write-Host "  .\scripts\start-ngrok.ps1"
} else {
    Write-Host "[警告] 服务未在 ${maxWait}s 内就绪，请检查日志：" -ForegroundColor Yellow
    Write-Host "  docker compose logs -f backend"
}
