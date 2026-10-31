@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Ti AI v2.3 - Kurulum

where py >nul 2>&1
if errorlevel 1 (
  echo [HATA] Python baslaticisi bulunamadi. Python 3.11 x64 kurun.
  pause
  exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
  echo [Ti] Python 3.11 sanal ortami olusturuluyor...
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo [HATA] Python 3.11 ile .venv olusturulamadi.
    pause
    exit /b 3
  )
)

echo [Ti] pip guncelleniyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :install_error

echo [Ti] Kutuphaneler kuruluyor. PyTorch/Ultralytics nedeniyle biraz surebilir...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :install_error

echo.
echo [OK] Kurulum tamamlandi. Ti_Baslat.cmd dosyasini calistirin.
pause
exit /b 0

:install_error
echo.
echo [HATA] Kurulum tamamlanamadi. Internet baglantisini ve yukaridaki pip hatasini kontrol edin.
pause
exit /b 1
