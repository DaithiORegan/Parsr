@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py --test-discord
if errorlevel 1 echo Test failed. Check your private .env file.
pause
