@echo off
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
"%PY%" -m pip install -q -r requirements-dev.txt
"%PY%" -m pytest -q
pause
