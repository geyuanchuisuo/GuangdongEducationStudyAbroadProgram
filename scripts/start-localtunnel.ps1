# 内网穿透启动脚本（localtunnel 版）：无需注册，npx 直跑
# 用法：在项目根目录执行 .\scripts\start-localtunnel.ps1
# 实测验证：2026-10-17 v6.9.0（URL: https://wide-cameras-pay.loca.lt 访问成功）

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  粤教留学项目 - 公网访问（localtunnel）" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 检查本地服务是否已启动（项目 nginx 用 8080，80 被本机 Dify 占用）
$port8080 = Test-NetConnection -ComputerName localhost -Port 8080 -InformationLevel Quiet -WarningAction SilentlyContinue
if (!$port8080) {
    Write-Host "[警告] 本地 8080 端口未监听，请先启动服务：" -ForegroundColor Yellow
    Write-Host "  .\scripts\build-and-serve.ps1"
    Write-Host ""
    exit 1
}

# 2. 启动 localtunnel（前台运行，URL 直接显示在输出中）
Write-Host "`n[启动] npx localtunnel --port 8080 ..." -ForegroundColor Green
Write-Host "  首次运行 npx 会自动下载 localtunnel（约几秒）"
Write-Host "  看到 'your url is: https://xxx.loca.lt' 即为公网地址"
Write-Host "  按 Ctrl+C 停止穿透`n"
npx localtunnel --port 8080
