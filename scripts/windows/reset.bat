@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - Full Reset & Rebuild
echo ============================================================

echo [Reset] Tearing down the docker stack (INCLUDING data volumes)...
docker-compose down -v 2>nul || docker compose down -v 2>nul || echo   (nothing to stop)

echo [Reset] Cleaning caches...
for /d /r . %D in (__pycache__ .pytest_cache) do @if exist "%D" rmdir /S /Q "%D" 2>nul

echo [Reset] Running setup...
call scripts\windows\setup.bat
if errorlevel 1 exit /b 1

echo [Reset] Rebuilding the container image...
call scripts\windows\build.bat
if errorlevel 1 exit /b 1

echo [Reset] Deploying fresh stack...
call scripts\windows\deploy.bat
if errorlevel 1 exit /b 1

echo [Reset] Refresh complete.
endlocal