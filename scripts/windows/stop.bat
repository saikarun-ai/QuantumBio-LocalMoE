@echo off
setlocal
cd /d "%~dp0..\.."
echo [Stop] Stopping all QuantumBio-LocalMoE services...
docker-compose down
if errorlevel 1 exit /b 1
echo [Stop] Done. Volumes kept; use "docker-compose down -v" to remove data.
endlocal