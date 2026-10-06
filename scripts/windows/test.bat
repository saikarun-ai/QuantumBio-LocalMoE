@echo off
setlocal
cd /d "%~dp0..\.."
call .venv\Scripts\activate.bat
echo [Test] Installing dev dependencies...
pip install -r requirements-dev.txt
echo [Test] Running test suite...
pytest tests -v
if errorlevel 1 exit /b 1
echo [Test] All tests passed.
endlocal