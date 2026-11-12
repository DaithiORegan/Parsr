@echo off
cd /d "%~dp0"
echo Creating local Python environment...
py -3 -m venv .venv
if errorlevel 1 (
  echo Python 3 not found. Install Python 3 and enable the py launcher.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Installation failed.
  pause
  exit /b 1
)
echo.
echo INSTALL COMPLETE. Next, double-click 02_PREVIEW.bat.
pause
