@echo off
setlocal
cd /d "%~dp0\..\.."
echo [1/3] Starting NLP Feedback System...
docker compose up -d --build
if errorlevel 1 goto :error
echo [2/3] Waiting for health check...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 40;$i++){try{$r=Invoke-WebRequest -UseBasicParsing http://localhost:8080/health -TimeoutSec 2;if($r.StatusCode -eq 200){$ok=$true;break}}catch{};Start-Sleep -Seconds 2};if(-not $ok){exit 1}"
if errorlevel 1 goto :error
echo [3/3] Ready: http://localhost:8080
start "" http://localhost:8080
exit /b 0
:error
echo.
echo Startup failed. Run: docker compose logs app
pause
exit /b 1
