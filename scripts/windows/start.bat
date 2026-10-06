@echo off
setlocal
cd /d "%~dp0..\.."
call .venv\Scripts\activate.bat
echo [Start] Launching QuantumBio-LocalMoE API on http://localhost:8000 ...
uvicorn main:app --host 0.0.0.0 --port 8000
endlocal