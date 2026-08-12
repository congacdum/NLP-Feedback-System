@echo off
setlocal
cd /d "%~dp0"

set "JAVA_HOME=%CD%\.tools\jre21\jdk-21.0.12+8-jre"
set "PATH=%JAVA_HOME%\bin;%JAVA_HOME%\bin\server;%PATH%"

set "NLP_BACKEND=transformer"
set "TRANSFORMER_ARTIFACT=%CD%\model_artifacts\experimental_phobert_absa_v5_hard_cases_final"
set "VNCORENLP_DIR=C:\vncorenlp"
set "ALLOW_EXPERIMENTAL_TRANSFORMER=true"
set "TRANSFORMER_DEVICE=cpu"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_OFFLINE=1"

echo Starting NLP Feedback System with local V5 Transformer...
echo Artifact: %TRANSFORMER_ARTIFACT%
echo URL: http://127.0.0.1:8000
echo.

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
