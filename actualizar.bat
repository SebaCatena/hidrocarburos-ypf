@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Actualizando datos de hidrocarburos...
python descargar_datos.py
if errorlevel 1 goto error

echo Generando graficos e informe...
python analisis.py
if errorlevel 1 goto error

echo.
echo Listo. Abriendo el informe en el navegador...
start "" "index.html"
pause
exit /b 0

:error
echo.
echo Hubo un error. Revisa el mensaje de arriba.
pause
exit /b 1
