@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Ti AI v2.3 - Guvenli Baslatma
if not exist ".venv\Scripts\python.exe" (
  echo [HATA] Python .venv bulunamadi. Bu dosya C301 ANA proje klasorunde olmalidir.
  echo Once Kurulum.cmd dosyasini calistirin.
  pause
  exit /b 2
)
if not exist "Ti_Guvenli_Baslat.py" (
  echo [HATA] Ti_Guvenli_Baslat.py bulunamadi. Paketi yeniden indirin.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -u "Ti_Guvenli_Baslat.py" %*
set "RC=%errorlevel%"
if not "%RC%"=="0" (
  echo.
  echo [HATA] Ti uygulamasi hata ile kapandi. Kod: %RC%
  echo Gunluk: Ti_Veriler\ti_baslatma_hata.log
  echo Windows/Python beklenmedik kapanmalari icin: Ti_Veriler\ti_gui_fatal.log
  echo Hata ekrani gorunsun diye bu pencere acik kalacak.
  pause
)
exit /b %RC%
