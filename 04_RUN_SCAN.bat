@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" run.py
if errorlevel 1 echo One or more scan or notification errors occurred.
pause
