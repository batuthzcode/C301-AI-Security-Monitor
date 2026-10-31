"""Lightweight local preflight. Never prints config contents or camera credentials."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
REQUIRED = ('Ti_Kontrol_Merkezi_v1.py','ti_services.py','ti_detector_async.py',
            'ti_lowlatency.py','ti_v1_core.py','ti_spotify.py','ti_commands.py',
            'Ti_Guvenli_Baslat.py','ti_follow.py')
MODULES = ('PySide6','numpy','cv2','torch','ultralytics','faster_whisper','psutil','gtts')


def main() -> int:
    problems=[]
    print('=== Ti AI v2.3 - Saglik Kontrolu ===')
    print('Python:',sys.version.split()[0])
    if sys.version_info < (3,10):problems.append('Python 3.10+ gerekli')
    for name in REQUIRED:
        if not (ROOT/name).is_file():problems.append('Eksik paket dosyasi: '+name)
    for name in MODULES:
        try: available=importlib.util.find_spec(name) is not None
        except (ValueError,ModuleNotFoundError):available=False
        print(('  OK    ' if available else '  EKSIK ')+name)
        if not available:problems.append('Eksik Python kutuphanesi: '+name)
    print('FFmpeg:', 'bulundu' if shutil.which('ffmpeg') else 'PATH icinde bulunamadi')
    if not shutil.which('ffmpeg'):problems.append('FFmpeg PATH icinde yok')
    # These are personal external prerequisites: do not copy or print their contents.
    print('camera_speaker.py:', 'mevcut' if (ROOT/'camera_speaker.py').is_file() else 'yok (sesli asistan kisitlanabilir)')
    print('Mevcut kamera go2rtc sistemi ve kimlik bilgileri bu testte kontrol edilmez.')
    print('Sorun:', len(problems))
    for p in problems:print(' -',p)
    return 0 if not problems else 1


if __name__=='__main__':sys.exit(main())
