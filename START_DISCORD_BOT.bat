@echo off
cd /d "%~dp0"
if not exist .bot-venv\Scripts\python.exe (
  py -3 -m venv .bot-venv
  if errorlevel 1 goto failure
)
.bot-venv\Scripts\python.exe -m pip install -r requirements-bot.txt
if errorlevel 1 goto failure
.bot-venv\Scripts\python.exe discord_bot.py
pause
exit /b
:failure
echo Setup failed. Install Python 3.12 or newer and try again.
pause
