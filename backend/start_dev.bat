@echo off
REM 启动后端开发服务器
REM 注意：由于项目路径包含中文字符，需要删除editable install的.pth文件以避免编码问题

cd /d "%~dp0"

REM 删除可能导致编码问题的.pth文件
if exist ".venv\Lib\site-packages\_editable_impl_guangdong_education_backend.pth" (
    del ".venv\Lib\site-packages\_editable_impl_guangdong_education_backend.pth"
    echo 已清理.pth文件
)

REM 设置Python编码为UTF-8
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM 启动开发服务器
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
