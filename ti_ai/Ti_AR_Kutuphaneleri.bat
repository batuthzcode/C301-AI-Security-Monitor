@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo [HATA] .venv bu klasorde bulunamadi.
 pause
 exit /b 2
)
echo Ti AR MediaPipe kurulumunda bagimlilik dogrulamasi yapiliyor...
".venv\Scripts\python.exe" -m pip install "mediapipe>=0.10.14,<0.11"
if errorlevel 1 (
 echo [HATA] MediaPipe kurulum basarisiz. Hata metnini paylas.
 pause
 exit /b 1
)
echo.
echo [Ti AR] Kutuphane kuruldu. Model dosyalarini Ti icinden 'Modelleri Indir' ile indir.
echo Sonra Ti_AR_Teshis.bat ile EL/YUZ model testini yap.
".venv\Scripts\python.exe" -u "Ti_AR_Teshis.py"
echo.
pause
