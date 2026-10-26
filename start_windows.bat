@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" sudoku_studio.py
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python not found. Install Python 3.10 or newer first.
        pause
        exit /b 1
    )
    python sudoku_studio.py
)
if errorlevel 1 (
    echo.
    echo Failed to start. Check the error above.
    pause
)
