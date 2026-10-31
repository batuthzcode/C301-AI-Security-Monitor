"""Ti AI v2.1.1 - local AR hardware-independent diagnostics.

Does NOT access webcam, RTSP, cloud APIs or camera credentials.
Real MediaPipe model loading is explicitly tested when --models is used.
"""
from __future__ import annotations
import argparse
import importlib
import platform
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'Ti_AR_Modeller'
OUT=ROOT/'Ti_Veriler'/'ti_ar_teshis.log'


def main(test_models=False):
    reports=[]
    def line(message):
        print(message,flush=True);reports.append(message)
    good=True
    try:
        line('Ti AR v2.1.1 yerel teshis')
        line('Python: '+sys.version.split()[0]+'; '+platform.system()+' '+platform.machine())
        for package in ('cv2','numpy','mediapipe'):
            try:
                mod=importlib.import_module(package)
                line('[OK] '+package+' '+str(getattr(mod,'__version__','(surum bilinmiyor)')))
            except Exception as ex:
                good=False;line('[HATA] '+package+': '+type(ex).__name__+' '+str(ex)[:140])
        for name in ('hand_landmarker.task','face_landmarker.task'):
            path=MODELS/name
            if not path.is_file() or path.stat().st_size<50000:
                good=False;line('[HATA] '+name+' yok veya eksik - Ti AR Studio > Modelleri Indir')
            else:line('[OK] '+name+' ('+str(path.stat().st_size)+' bayt)')
        if test_models and good:
            import numpy as np
            from ti_ar_worker import MediapipeModel
            md=MediapipeModel(MODELS)
            try:
                md._init('hand')
                line('[OK] Gercek MediaPipe el modeli yuklendi')
                md._init('face')
                line('[OK] Gercek MediaPipe yuz modeli yuklendi')
                hands,faces=md.detect(np.zeros((256,256,3),dtype=np.uint8),True,True)
                line(f'[OK] Gercek model calisti - bos karede {len(hands)} el / {len(faces)} yuz (0 beklenir)')
            finally:md.close()
        line('[SONUC] '+('BASARILI' if good else 'EKSIK BAGIMLILIK / MODEL'))
    except Exception as ex:
        good=False
        line('[HATA] '+type(ex).__name__+': '+str(ex)[:400])
        line('[SONUC] MODEL TESTI BASARISIZ')
    finally:
        try:
            OUT.parent.mkdir(parents=True,exist_ok=True)
            OUT.write_text('\n'.join(reports)+'\n',encoding='utf-8')
            line('Rapor: Ti_Veriler/ti_ar_teshis.log')
        except OSError:line('Rapor diske yazilamadi.')
    return 0 if good else 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--models',action='store_true')
    args=parser.parse_args()
    raise SystemExit(main(test_models=args.models))
