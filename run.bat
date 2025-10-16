@echo off
REM === Activar entorno virtual ===
call .venv\Scripts\activate.bat

REM === Obtener IP local ===
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /i "IPv4"') do set "ip=%%i"
set ip=%ip: =%
echo.
echo ================================================
echo INICIANDO SERVIDORES DE CONTROL DE DRONES...
echo ================================================
echo.
echo.

REM === Abrir run.py en una nueva ventana minimizada ===
start /min cmd /k "cd /d %~dp0WebAppMQTT && call ..\.venv\Scripts\activate.bat && python run.py"

REM === Esperar 7 segundos para asegurar que el servidor arranca completamente ===
timeout /t 7 >nul

REM === Abrir EstacionDeTierra.py en una nueva ventana minimizada ===
start /min cmd /k "cd /d %~dp0EstacionTierra && call ..\.venv\Scripts\activate.bat && python EstacionDeTierra.py"

echo.
echo ================================================
echo            SERVIDORES LISTOS
echo ================================================
echo.
echo WebApp en:
echo.
echo    *** https://%ip%:5004 ***
echo.
echo.
echo.
pause