@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo [HATA] .venv bulunamadi.& pause& exit /b 2)
echo [Ti] Bu komut yalnizca Windows'ta EXE uretir; Go2RTC ve FFmpeg harici bagimliliklardir.
".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (echo [HATA] PyInstaller kurulu degil. ^".venv\Scripts\python.exe^" -m pip install pyinstaller& pause& exit /b 3)
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name TiAI --collect-all ultralytics --collect-all faster_whisper --collect-all PySide6 --add-data "ti_detector_async.py;." Ti_Kontrol_Merkezi_v1.py
if errorlevel 1 (echo [HATA] EXE uretilemedi.& pause& exit /b 1)
echo [OK] dist\TiAI\TiAI.exe olusturuldu. Gercek cihazda test etmeden dagitma.
pause
