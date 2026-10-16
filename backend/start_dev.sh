#!/bin/bash
# 启动后端开发服务器
# 注意：由于项目路径包含中文字符，需要删除editable install的.pth文件以避免编码问题

cd "$(dirname "$0")"

# 删除可能导致编码问题的.pth文件
PTH_FILE=".venv/Lib/site-packages/_editable_impl_guangdong_education_backend.pth"
if [ -f "$PTH_FILE" ]; then
    rm -f "$PTH_FILE"
    echo "已清理.pth文件"
fi

# 设置Python编码为UTF-8
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

# 启动开发服务器
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
