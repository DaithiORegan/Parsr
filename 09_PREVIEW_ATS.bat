@echo off
cd /d "%~dp0"
python run.py --backfill --dry-run --channel ats
pause
