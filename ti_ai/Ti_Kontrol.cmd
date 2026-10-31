@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [HATA] .venv bulunamadi.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -u "Ti_Saglik_Kontrol.py"
set "RC=%errorlevel%"
echo.
pause
exit /b %RC%
