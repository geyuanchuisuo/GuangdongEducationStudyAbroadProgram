@echo off
cd /d "%~dp0"
set "MINERU_TOOLS_CONFIG_JSON=%~dp0magic-pdf.json"

echo === Containers ===
docker compose ps

echo.
echo === Health check ===
curl -s http://127.0.0.1:9091/healthz
echo.

echo === pymilvus test ===
"%~dp0..\backend\.venv\Scripts\python.exe" -c "from pymilvus import MilvusClient; c = MilvusClient(uri='http://localhost:19530'); print('Milvus OK, collections:', c.list_collections())"
echo.
