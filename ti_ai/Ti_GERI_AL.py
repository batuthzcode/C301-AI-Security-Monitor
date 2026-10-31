"""Restore only Ti-owned files from a validated installer backup, never user data.
Usage: .venv\\Scripts\\python.exe Ti_GERI_AL.py --list OR --restore BACKUP_FOLDER
"""
from pathlib import Path
import argparse
import shutil
import sys

ROOT=Path(__file__).resolve().parent
ALLOWED={
    'ARASTIRMA_10_OZELLIK.md',
    'DEVAM_NOTLARI.md',
    'GITHUB_PORTFOY_REHBERI.md',
    'KURULUM_v1_3_1.md',
    'KURULUM_v1_3_2.md',
    'KURULUM_v1_3_3.md',
    'KURULUM_v2_0.md',
    'ONCE_BUNU_OKU.txt',
    'OZELLIK_DURUMU_v2.md',
    'Ti_Bagimlilik_Kontrol.py',
    'Ti_Baslat.cmd',
    'Ti_Buton_Gorsel_Test.py',
    'Ti_Buton_Test.cmd',
    'Ti_EXE_OLUSTUR.bat',
    'Ti_GERI_AL.bat',
    'Ti_GERI_AL.py',
    'Ti_Guvenli_Baslat.py',
    'Ti_Hata_Ayikla.cmd',
    'Ti_Kontrol.cmd',
    'Ti_Kontrol_Merkezi_v1.py',
    'Ti_Kur.cmd',
    'Ti_Saglik_Kontrol.py',
    'Ti_Test.cmd',
    'Ti_Testleri.py',
    'Ti_Testleri_v1_1.py',
    'Ti_v1_2_Testleri.py',
    'Ti_v1_3_1_Testleri.py',
    'Ti_v1_3_2_Testleri.py',
    'Ti_v1_3_3_Testleri.py',
    'Ti_v1_3_Testleri.py',
    'Ti_v2_Testleri.py',
    'requirements-ti-v1.txt',
    'ti_commands.py',
    'ti_detector_async.py',
    'ti_follow.py',
    'ti_lab.py',
    'ti_lowlatency.py',
    'ti_services.py',
    'ti_spotify.py',
    'ti_v1_core.py',
    'ti_v2_developer.py',
    'ti_v2_features.py',
    'ti_v2_updater.py',
    'ti_v2_web.py',
}


def restore(backup):
    path=Path(backup).resolve()
    base=(ROOT/'Ti_Yedekler').resolve()
    if path.parent!=base or not path.is_dir():raise ValueError('Yedek Ti_Yedekler altındaki doğrudan bir klasör olmalı.')
    files=[p for p in path.iterdir() if p.is_file() and not p.is_symlink()]
    if not files or any(p.name not in ALLOWED for p in files):raise ValueError('Yedek içeriği güvenli değil.')
    for p in files:compile(p.read_bytes(),p.name,'exec') if p.suffix=='.py' else None
    for p in files:shutil.copy2(p,ROOT/p.name)
    return len(files)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--list',action='store_true');parser.add_argument('--restore')
    args=parser.parse_args()
    if args.list:
        for p in sorted((ROOT/'Ti_Yedekler').glob('v*'),reverse=True):
            if p.is_dir():print(p.name)
    elif args.restore:
        print('Geri yüklenen Ti dosyası:',restore(args.restore))
    else:parser.print_help()

if __name__=='__main__':main()
