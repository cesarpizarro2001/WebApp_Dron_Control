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

pause
