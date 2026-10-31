"""Ti desktop launcher: show and record Python exceptions instead of hiding pythonw errors.

Run via Ti_Baslat.cmd from the existing project directory.
"""
from __future__ import annotations

from datetime import datetime
import faulthandler
from pathlib import Path
import runpy
import sys
import traceback

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'Ti_Veriler'
LOG = DATA / 'ti_baslatma_hata.log'


def save_error(message: str) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as out:
            out.write(f'\n[{datetime.now().isoformat(timespec="seconds")}]\n{message}\n')
    except OSError as exc:
        print('[Ti] Hata gunlugu yazilamadi:', exc, file=sys.stderr)
    print(message, file=sys.stderr, flush=True)
    print('[Ti] Hata gunlugu:', LOG, file=sys.stderr, flush=True)


def custom_excepthook(exc_type, value, tb):
    save_error(''.join(traceback.format_exception(exc_type, value, tb)))


def main() -> int:
    sys.excepthook = custom_excepthook
    main_file = ROOT / 'Ti_Kontrol_Merkezi_v1.py'
    if not main_file.is_file():
        save_error('[HATA] Ti_Kontrol_Merkezi_v1.py eksik. Paketi yeniden indirin.')
        return 2
    # Early actionable error rather than silently exiting through pythonw.exe.
    try:
        import PySide6  # noqa: F401
    except ImportError as exc:
        save_error(f'[HATA] PySide6 kurulu degil: {exc}. Kurulum.cmd dosyasini calistirin.')
        return 3
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        fatal_log = (DATA / 'ti_gui_fatal.log').open('a', encoding='utf-8')
        faulthandler.enable(file=fatal_log, all_threads=True)
        # Never display or save camera token/config contents.
        runpy.run_path(str(main_file), run_name='__main__')
        return 0
    except SystemExit as exc:
        # The Qt application normally returns SystemExit(0) when the window closes.
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    except BaseException:
        save_error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    sys.exit(main())
