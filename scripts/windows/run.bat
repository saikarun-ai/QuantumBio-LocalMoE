@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - One-Click Local Run
echo ============================================================

if not exist .venv (
  echo [Run] First-time setup detected - running setup...
  call scripts\windows\setup.bat
  if errorlevel 1 exit /b 1
) else (
  call .venv\Scripts\activate.bat
  echo [Run] Using existing virtual environment.
)

echo [Run] Optional: start infrastructure services (postgres/redis/qdrant)?
choice /C YN /M "Start docker-compose infra (Y/N)"
if errorlevel 2 (
  echo [Run] Skipping infrastructure services - using in-memory fallbacks.
) else (
  call scripts\windows\start_infra.bat
)

echo [Run] Launching API at http://localhost:8000 ... (Ctrl+C to stop)
uvicorn main:app --host 0.0.0.0 --port 8000
endlocal