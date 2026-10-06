@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - Container Logs
echo ============================================================

echo [Logs] quantumbio-localmoe engine container:
docker-compose logs -f quantumbio-localmoe 2>nul || docker compose logs -f quantumbio-localmoe 2>nul || (
  echo   Container not running. Start it with: scripts\windows\deploy.bat
  exit /b 1
)
endlocal