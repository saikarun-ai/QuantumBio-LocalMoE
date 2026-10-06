@echo off
setlocal
cd /d "%~dp0..\.."
echo [Deploy] Phase 1: infrastructure (postgres, redis, qdrant)...
docker-compose up -d postgres redis qdrant
if errorlevel 1 exit /b 1
echo [Deploy] Phase 2: building and starting the MoE engine container...
docker-compose up -d --build quantumbio-localmoe
if errorlevel 1 exit /b 1
echo [Deploy] Done.
echo   Health  : http://localhost:8000/health
echo   Models  : http://localhost:8000/v1/models
echo   Chat    : POST http://localhost:8000/v1/chat/completions
endlocal