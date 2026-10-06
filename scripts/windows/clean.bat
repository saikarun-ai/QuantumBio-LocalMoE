@echo off
setlocal
cd /d "%~dp0..\.."

echo ============================================================
echo  QuantumBio-LocalMoE - Clean Workspace
echo ============================================================

echo [Clean] Stopping containers (data volumes kept)...
docker-compose down 2>nul || docker compose down 2>nul || echo   (nothing to stop)

echo [Clean] Removing generated caches...
if exist .venv (
  choice /C YN /M "Delete the virtual environment .venv?  (Y/N)"
  if not errorlevel 2 (
    rmdir /S /Q .venv
    echo   Removed .venv
  )
)
for %%D in (__pycache__ .pytest_cache .mypy_cache) do (
  for /d /r . %%X in (%%D) do (
    if exist "%%X" (
      rmdir /S /Q "%%X"
      echo   Removed %%X
    )
  )
)
echo [Clean] Done.
endlocal