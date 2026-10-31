"""Read-only diagnostic; no credentials or camera URLs printed."""
import importlib.util, os, pathlib, shutil, subprocess, sys
print('Ti — Bağımlılık Kontrolü')
print('Python:',sys.executable)
for module in ('PySide6','cv2','numpy','ultralytics','torch','faster_whisper','gtts','psutil'):
    try:ready=importlib.util.find_spec(module) is not None
    except (ImportError,ValueError):ready=False
    print(('OK' if ready else 'EKSİK').ljust(6),module)
print('FFmpeg:', 'OK' if shutil.which('ffmpeg') else 'EKSİK / PATH YOK')
try:
 import ti_services
 print('go2rtc yapılandırması:', 'BULUNDU' if ti_services.CONFIG_PATH.exists() else 'BULUNAMADI')
 print('go2rtc PTZ EXE:', 'BULUNDU' if ti_services.PTZ_EXE.exists() else 'BULUNAMADI')
 print('API bağlantısı:', 'HAZIR' if ti_services.get_streams() is not None else 'BAĞLANAMADI')
 print('Kamera ses dosyası:', 'BULUNDU' if (ti_services.BASE/'camera_speaker.py').exists() else 'BULUNAMADI')
except Exception as e:
 print('Durum hata:',type(e).__name__,str(e)[:140])
print('Eksik modüller varsa Kurulum.cmd ile kurulum yap.')
