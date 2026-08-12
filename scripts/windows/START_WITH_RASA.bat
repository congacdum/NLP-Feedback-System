@echo off
setlocal
cd /d "%~dp0\..\.."
echo [1/3] Building main app...
docker compose build app
if errorlevel 1 goto :error

echo [2/3] Training Rasa model into rasa_bot\models ...
docker compose --profile rasa run --rm rasa train --domain domain.yml --data data --out models
if errorlevel 1 goto :error

echo [3/3] Starting app + Rasa + action server...
docker compose --profile rasa up -d --build
if errorlevel 1 goto :error

powershell -NoProfile -Command "$u='http://localhost:8080/health'; for($i=0;$i -lt 40;$i++){try{$r=Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 2;if($r.StatusCode -eq 200){exit 0}}catch{}; Start-Sleep -Seconds 2}; exit 1"
if errorlevel 1 goto :error
start "" http://localhost:8080
exit /b 0

:error
echo Startup failed. Inspect: docker compose --profile rasa logs
pause
exit /b 1
