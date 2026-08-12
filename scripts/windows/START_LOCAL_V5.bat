@echo off
setlocal
cd /d "%~dp0\..\.."

rem Use the project virtual environment and a local JDK for VnCoreNLP.
rem Change JAVA_HOME below only if Java is installed elsewhere on your machine.
set "JAVA_HOME=C:\Program Files\Java\jdk-24"
set "PATH=%JAVA_HOME%\bin;%PATH%"

set "NLP_BACKEND=transformer"
set "TRANSFORMER_ARTIFACT=%CD%\model_artifacts"
set "VNCORENLP_DIR=C:\vncorenlp"
set "ALLOW_EXPERIMENTAL_TRANSFORMER=true"
set "TRANSFORMER_DEVICE=cpu"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_OFFLINE=1"

echo Starting NLP Feedback System with local V5 Transformer...
echo Artifact: %TRANSFORMER_ARTIFACT%
echo URL: http://127.0.0.1:8000
echo.

"%CD%\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
