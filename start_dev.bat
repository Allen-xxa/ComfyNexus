@echo off
echo Starting ComfyNexus (dev mode)...
cd /d "%~dp0source-code\backend"
".venv\Scripts\python.exe" -u main.py
