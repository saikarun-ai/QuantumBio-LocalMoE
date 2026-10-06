@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - API Smoke Test
echo ============================================================

if not exist .venv (
  echo [Smoke] No virtual environment found. Run: scripts\windows\setup.bat
  exit /b 1
)
call .venv\Scripts\activate.bat

if "%1"=="" (
  python scripts\smoke_test.py
) else (
  python scripts\smoke_test.py %*
)
endlocal