@echo off
REM === Crear entorno virtual si no existe ===
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv
)

REM === Activar entorno virtual ===
call .venv\Scripts\activate.bat

REM === Instalar dependencias ===
echo.
echo Instalando dependencias...
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo.
echo Setup completado. Puedes ejecutar run.bat para iniciar la aplicacion.
echo.
pause
