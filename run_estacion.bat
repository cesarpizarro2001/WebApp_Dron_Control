@echo off
REM === Activar entorno virtual ===
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo [!] No se encontró .venv. Continuando sin activar entorno...
)

echo.
echo ================================================
echo Iniciando Estacion de Tierra...
echo ================================================
echo.

REM === Abrir EstacionDeTierra.py en una nueva ventana minimizada ===
start /min cmd /k "cd /d %~dp0EstacionTierra && if exist ..\.venv\Scripts\activate.bat call ..\.venv\Scripts\activate.bat && python EstacionDeTierra.py"

echo [OK] Estacion de Tierra lanzada en una ventana separada.

echo.
echo =================================================
echo                 QR GENERADOS
echo =================================================
echo.

REM === URLs fijas para entorno UPC ===
set prof_url=https://dronseetac.upc.edu:8106
set alum_url=https://dronseetac.upc.edu:8106/alumno_control

echo WebApp Profesor:
echo    %prof_url%
echo.
echo WebApp Alumno:
echo    %alum_url%
echo.
echo.
echo QR del Profesor                                            QR del Alumno
python Generador_QR_colindante.py %prof_url% %alum_url%
echo.
echo.

pause
