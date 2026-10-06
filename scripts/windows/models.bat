@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - Model Catalog & Management
echo ============================================================

if not exist .venv (
  echo [Models] No virtual environment found. Run: scripts\windows\setup.bat
  exit /b 1
)
call .venv\Scripts\activate.bat

set COMMAND=%1
if "%COMMAND%"=="" set COMMAND=list

if /i "%COMMAND%"=="list" (
  python scripts\manage_models.py list
) else if /i "%COMMAND%"=="export" (
  python scripts\manage_models.py export %2 %3 %4 %5
) else (
  echo [Models] Unknown command "%COMMAND%". Usage:
  echo   scripts\windows\models.bat list
  echo   scripts\windows\models.bat export [--source DIR] [--dest DIR] [--hardlink]
  exit /b 1
)
endlocal