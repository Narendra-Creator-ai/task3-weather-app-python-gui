@echo off
setlocal

cd /d "%~dp0"

if exist "%~dp0weather_app.py" (
    python "%~dp0weather_app.py"
    if errorlevel 1 (
        echo.
        echo Python command failed. Trying with py launcher...
        py "%~dp0weather_app.py"
    )
) else (
    echo weather_app.py not found in this folder.
)

echo.
echo Press any key to close...
pause >nul
