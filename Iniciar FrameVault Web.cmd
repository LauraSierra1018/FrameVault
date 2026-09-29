@echo off
cd /d "%~dp0"
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
    python web_server.py
    if errorlevel 1 pause
    exit /b
)
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 (
    py -3 web_server.py
    if errorlevel 1 pause
    exit /b
)
echo FrameVault Web necesita Python 3.10 o posterior en el PATH.
pause
