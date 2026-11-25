@echo off
cd /d "%~dp0"
echo Stopping Milvus containers ^(data is kept in data\^)...
docker compose down
echo Done.
