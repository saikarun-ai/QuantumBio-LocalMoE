@echo off
rem Regenerate all evaluation results. Run from the repository root.
setlocal
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1

set PY=.venv\Scripts\python.exe
if not exist %PY% set PY=python

echo ==^> environment
%PY% evaluation\benchmark\environment.py || goto :err
echo ==^> routing
%PY% evaluation\benchmark\routing_benchmark.py || goto :err
echo ==^> quantum
%PY% evaluation\benchmark\quantum_benchmark.py || goto :err
echo ==^> offline
%PY% evaluation\benchmark\offline_check.py || goto :err
echo ==^> reliability (loads model)
%PY% evaluation\benchmark\reliability_test.py || goto :err
echo ==^> api extended (model select + LLM report calls)
%PY% evaluation\benchmark\api_extended_test.py || goto :err
echo ==^> quantization (loads 3 models)
%PY% evaluation\benchmark\quantization_benchmark.py || goto :err
echo ==^> speculative (loads model twice)
%PY% evaluation\benchmark\speculative_test.py || goto :err
echo ==^> scientific (10 LLM calls)
%PY% evaluation\benchmark\scientific_task.py || goto :err
echo ==^> aggregate
%PY% evaluation\benchmark\process_results.py || goto :err
echo done
exit /b 0

:err
echo FAILED
exit /b 1