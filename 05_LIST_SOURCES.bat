@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" run.py --list-sources
) else (
  py -3 run.py --list-sources
)
pause
