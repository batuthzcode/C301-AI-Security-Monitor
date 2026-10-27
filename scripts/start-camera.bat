@echo off
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python main.py --source rtsp://127.0.0.1:8554/c301
pause
