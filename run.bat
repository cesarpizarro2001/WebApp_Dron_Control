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
echo [1/2] Iniciando servidor Flask + Socket.IO (run.py)...
start /min cmd /k "cd /d %~dp0WebApp && call ..\.venv\Scripts\activate.bat && python run.py"

REM === Esperar a que el servidor este listo ===
echo [*] Esperando a que el servidor este listo (puerto 5004)...
set /a counter=0
:wait_loop
timeout /t 1 >nul
netstat -an | find ":5004" | find "LISTENING" >nul 2>&1
if errorlevel 1 (
    set /a counter+=1
    if %counter% lss 15 (
        goto wait_loop
    ) else (
        echo.
        echo [!] ADVERTENCIA: El servidor no respondio en 15s
        echo     Continuando de todas formas...
        echo.
    )
)
echo [OK] Servidor listo!
echo.

REM === Abrir EstacionDeTierra.py en una nueva ventana minimizada ===
echo [2/2] Iniciando Estacion de Tierra (EstacionDeTierra.py)...
start /min cmd /k "cd /d %~dp0EstacionTierra && call ..\.venv\Scripts\activate.bat && python EstacionDeTierra.py"

timeout /t 2 >nul

echo.
echo ================================================
echo            SERVIDORES LISTOS
echo ================================================
echo.
REM === URLs ===
set prof_url=https://%ip%:5004
set alum_url=https://%ip%:5004/alumno_control

echo WebApp Profesor:
echo    %prof_url%
echo.
echo WebApp Alumno:
echo    %alum_url%
echo.
echo.
echo =================================================
echo                 QR GENERADOS
echo =================================================
echo.
REM === Generar QR ===
echo QR del Profesor               QR del Alumno
python Generador_QR_colindante.py %prof_url% %alum_url%
echo.
echo.

pause