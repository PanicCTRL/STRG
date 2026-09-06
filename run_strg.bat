@echo off
cd /d "%~dp0"
"Y:\market_replayer\.venv\Scripts\python.exe" "main.py"
if errorlevel 1 pause