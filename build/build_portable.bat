@echo off
echo ============================================================
echo  LogAnalyzer - Portable Build
echo ============================================================

cd /d "%~dp0.."

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM Run PyInstaller
echo Building portable package...
pyinstaller ^
    --name LogAnalyzer ^
    --onedir ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --add-data "resources;resources" ^
    --hidden-import PySide6.QtCore ^
    --hidden-import PySide6.QtGui ^
    --hidden-import PySide6.QtWidgets ^
    --hidden-import chardet ^
    --hidden-import dateutil ^
    --hidden-import lxml ^
    --hidden-import polars ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

REM Copy config template
copy /y config.json dist\LogAnalyzer\config.json 2>nul

echo.
echo ============================================================
echo  Build complete: dist\LogAnalyzer\
echo  Run: dist\LogAnalyzer\LogAnalyzer.exe
echo ============================================================
pause
