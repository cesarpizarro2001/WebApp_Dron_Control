@echo off

echo Verificando instalacion de Python...

:: Obtener version de Python (por ejemplo: "3.10.11")
for /f "tokens=2 delims= " %%v in ('python --version 2^>nul') do set PY_VERSION=%%v

:: Si PY_VERSION está vacía → Python no está instalado
if "%PY_VERSION%"=="" (
    echo.
    echo ==================================================
    echo   ERROR: Python no esta instalado en el sistema
    echo ==================================================
    echo.
    echo Se requiere exactamente Python 3.10.x
    echo Descarga e instala Python 3.10 desde:
    echo https://www.python.org/downloads/release/python-31011/
    echo.
    pause
    exit /b
)

echo Python detectado: %PY_VERSION%
echo.

:: Extraer major y minor (3 y 10, por ejemplo)
for /f "tokens=1,2 delims=." %%a in ("%PY_VERSION%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

:: Verificar que sea EXACTAMENTE 3.10
if not "%PY_MAJOR%"=="3" (
    goto version_error
)

if not "%PY_MINOR%"=="10" (
    goto version_error
)

echo Version correcta: Python 3.10.x
echo.

goto continue_setup

:version_error
echo.
echo ==================================================
echo   ERROR: Version de Python incompatible
echo ==================================================
echo.
echo Se encontro Python %PY_VERSION%
echo Se requiere EXACTAMENTE Python 3.10.x para este proyecto.
echo.
echo Descarga la version correcta desde:
echo https://www.python.org/downloads/release/python-31011/
echo.
pause
exit /b

:continue_setup

REM === Crear entorno virtual si no existe ===
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv
)

REM === Activar entorno virtual ===
call .venv\Scripts\activate.bat

REM === Instalar dependencias ===
echo.
echo Actualizando herramientas de instalacion...
python -m pip install --upgrade pip setuptools wheel

echo.
echo Instalando dependencias de la WebApp...
python -m pip install -r requirements.txt

echo.
echo Setup completado. Puedes ejecutar run.bat para iniciar la aplicacion.
echo.
pause
