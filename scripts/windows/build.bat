@echo off
setlocal
cd /d "%~dp0..\.."
echo [Build] Building the QuantumBio-LocalMoE container image...
docker-compose build quantumbio-localmoe
endlocal