@echo off
setlocal
cd /d "%~dp0..\.."
echo [Infra] Starting postgres, redis and qdrant...
docker-compose up -d postgres redis qdrant
if errorlevel 1 (
  echo [Infra] ERROR: docker-compose failed. Is Docker running?
  exit /b 1
)
echo [Infra] Services started:
docker-compose ps postgres redis qdrant
endlocal