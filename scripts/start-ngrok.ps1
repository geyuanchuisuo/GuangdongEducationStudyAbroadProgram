# 内网穿透启动脚本：把本地 80 端口暴露到公网
# 用法：在项目根目录执行 .\scripts\start-ngrok.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  粤教留学项目 - 公网访问（ngrok）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 检查 ngrok 是否安装
$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue
if (!$ngrok) {
    Write-Host "`n[错误] 未找到 ngrok，请先安装：" -ForegroundColor Red
    Write-Host "  1. 访问 https://ngrok.com/download 下载 Windows 版"
    Write-Host "  2. 解压到任意目录，把 ngrok.exe 加入 PATH"
    Write-Host "  3. 或直接用 winget 安装： winget install ngrok.ngrok"
    Write-Host ""
    exit 1
}

# 2. 检查是否已配置 authtoken
$configPath = "$env:USERPROFILE\.ngrok2\ngrok.yml"
$hasToken = $false
if (Test-Path $configPath) {
    $content = Get-Content $configPath -Raw
    if ($content -match "authtoken:\s*\S+") { $hasToken = $true }
}

if (!$hasToken) {
    Write-Host "`n[配置] 首次使用需要 ngrok authtoken" -ForegroundColor Yellow
    Write-Host "  获取地址：https://dashboard.ngrok.com/get-started/your-authtoken"
    $token = Read-Host "  请输入 authtoken"
    if (!$token) {
        Write-Host "[取消] 未输入 token，退出" -ForegroundColor Red
        exit 1
    }
    ngrok config add-authtoken $token
    Write-Host "[成功] authtoken 已配置`n" -ForegroundColor Green
}

# 3. 检查本地服务是否已启动
$port80 = Test-NetConnection -ComputerName localhost -Port 80 -InformationLevel Quiet -WarningAction SilentlyContinue
if (!$port80) {
    Write-Host "[警告] 本地 80 端口未监听，请先启动服务：" -ForegroundColor Yellow
    Write-Host "  .\scripts\build-and-serve.ps1"
    Write-Host ""
    $continue = Read-Host "是否仍要启动 ngrok？（y/N）"
    if ($continue -ne "y" -and $continue -ne "Y") { exit 0 }
}

# 4. 启动 ngrok
Write-Host "`n[启动] ngrok http 80 ..." -ForegroundColor Green
Write-Host "  等待公网 URL 分配（见下方 Forwarding 行）"
Write-Host "  按 Ctrl+C 停止穿透`n"
ngrok http 80
