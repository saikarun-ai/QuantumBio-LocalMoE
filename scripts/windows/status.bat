@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - Stack Status
echo ============================================================

echo [Compose] Running containers:
docker-compose ps 2>nul || docker compose ps 2>nul || echo   (Docker not running or no stack)

echo.
echo [API] Health check on localhost:8000 ...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing 'http://localhost:8000/health' -TimeoutSec 3; Write-Output ('  HTTP ' + [int]$r.StatusCode) } catch { Write-Output '  API not reachable' }"

endlocal