@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py --dry-run
if errorlevel 1 echo Preview encountered an error. Check the messages above.
pause
