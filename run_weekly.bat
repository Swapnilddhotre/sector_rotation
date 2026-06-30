@echo off
REM ============================================================
REM Weekly NSE Sector Rotation Data Fetch
REM Runs every Sunday 7:00 PM via Task Scheduler
REM ============================================================

set PYTHONIOENCODING=utf-8
chcp 65001 >nul

call C:\Users\%USERNAME%\venvs\sector_rotation\Scripts\activate.bat

D:
cd D:\OneDrive\Github\sector_rotation

if not exist logs mkdir logs

echo. >> logs\schedule.log
echo ============================================================ >> logs\schedule.log
echo Run started: %DATE% %TIME% >> logs\schedule.log
echo ============================================================ >> logs\schedule.log

python phase2_signals\data_fetcher.py >> logs\schedule.log 2>&1

echo ============================================================ >> logs\schedule.log
echo Run finished: %DATE% %TIME% >> logs\schedule.log
echo ============================================================ >> logs\schedule.log

call deactivate