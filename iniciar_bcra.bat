@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro el entorno virtual .venv en esta carpeta.
    echo Crealo con:  python -m venv .venv
    echo Y luego:     .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem Levanta el servidor en una ventana aparte (cerrarla detiene el servidor)
start "Servidor BCRA" cmd /k ".venv\Scripts\python.exe app_web.py"

rem Espera a que el servidor arranque
timeout /t 4 /nobreak >nul

rem Abre Chrome; si no lo encuentra, usa el navegador predeterminado
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" "http://127.0.0.1:5000"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" "http://127.0.0.1:5000"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" "http://127.0.0.1:5000"
) else (
    start "" "http://127.0.0.1:5000"
)