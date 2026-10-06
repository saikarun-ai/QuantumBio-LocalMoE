@echo off
setlocal
cd /d "%~dp0..\.."
echo [Setup] QuantumBio-LocalMoE - creating virtual environment...
if not exist .venv (
  python -m venv .venv
  if errorlevel 1 (
    echo [Setup] ERROR: failed to create venv. Ensure Python 3.10+ is installed.
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo [Setup] Installing core dependencies...
pip install -r requirements.txt
if errorlevel 1 (
  echo [Setup] ERROR: core dependency install failed.
  exit /b 1
)
if exist requirements-optional.txt (
  echo [Setup] Installing optional extras (vLLM/SD/whisper) - best effort...
  call pip install -r requirements-optional.txt
  if errorlevel 1 echo [Setup] WARNING: optional extras failed (need GPU/Linux); continuing.
)
if not exist .env (
  echo [Setup] Creating .env from .env.example...
  copy .env.example .env
)
echo [Setup] Building model catalog...
python -c "from quantumbio_moe.inference.registry import ModelRegistry; r=ModelRegistry(); print(' text:', [m.name for m in r.text_models]); print(' diffusion:', [m.name for m in r.diffusion_models]); print(' audio:', [m.name for m in r.audio_models])"
echo [Setup] Complete. Activate with: .venv\Scripts\activate
endlocal