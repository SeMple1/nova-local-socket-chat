@echo off
cd /d "%~dp0"
python -c "import customtkinter" 2>nul || python -m pip install -r requirements.txt
python app.py
if errorlevel 1 pause
