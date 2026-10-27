"""C301 AI Security Monitor - camera voice integration installer.

Place next to main.py and camera_speaker.py, run with the project's Python.
- Creates an adapter, backs up only c301_monitor/gui.py, and edits exact anchors.
- Never edits go2rtc.yaml, worker.py, detection.py, or camera firmware.
- Opt in at runtime with C301_CAMERA_VOICE=1.
"""
from __future__ import annotations

import ast
import datetime
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
GUI = ROOT / "c301_monitor" / "gui.py"
ADAPTER = ROOT / "c301_monitor" / "camera_voice_adapter.py"
SPEAKER = ROOT / "camera_speaker.py"

ADAPTER_CODE = '''"""Use C301 camera speaker for the existing person alert; no YOLO changes."""
from camera_speaker import C301Speaker


class C301CameraVoice:
    def __init__(self):
        self._speaker = C301Speaker()

    def say(self, message: str):
        # Nonblocking, rate-limited. One alert per person event at most per minute.
        return self._speaker.notify("person", message, cooldown=60.0)

    def close(self):
        self._speaker.close()
'''


def replace_one(source: str, old: str, new: str, description: str) -> str:
    n = source.count(old)
    if n != 1:
        raise RuntimeError(
            f"{description}: Beklenen kod parcasi {n} kez bulundu (1 olmali). "
            "Herhangi bir dosya degistirilmedi. GUI surumun farkli olabilir."
        )
    return source.replace(old, new, 1)


def run() -> None:
    if not GUI.is_file() or not SPEAKER.is_file():
        raise RuntimeError(
            "Bu dosyayi main.py ve camera_speaker.py ile ayni proje klasorune koy. "
            "c301_monitor/gui.py dosyasi da mevcut olmali."
        )

    original = GUI.read_text(encoding="utf-8")
    if "C301_CAMERA_VOICE" in original:
        print("Kamera sesi entegrasyonu zaten kurulmus. Tekrar degisiklik yapilmadi.")
        return

    if ADAPTER.exists() and ADAPTER.read_text(encoding="utf-8") != ADAPTER_CODE:
        raise RuntimeError("camera_voice_adapter.py zaten mevcut ve icerigi farkli. Uzerine yazilmadi.")

    edited = replace_one(
        original,
        "import argparse\n",
        "import argparse\nimport os\n" if "import os\n" not in original else "import argparse\n",
        "GUI import bolumu",
    )
    edited = replace_one(
        edited,
        "from .speech import PCSpeaker\n",
        "from .speech import PCSpeaker\nfrom .camera_voice_adapter import C301CameraVoice\n",
        "Ses modulunun importu",
    )
    edited = replace_one(
        edited,
        "        self.speaker = PCSpeaker()",
        "        self.camera_voice_mode = os.environ.get('C301_CAMERA_VOICE') == '1'\n"
        "        self.speaker = C301CameraVoice() if self.camera_voice_mode else PCSpeaker()",
        "GUI ses cihazinin olusturulmasi",
    )
    edited = replace_one(
        edited,
        'text="PC\'den kişi algılama sesli uyarısı", variable=self.voice_var,',
        'text=("Kameradan kişi algılama sesli uyarısı" if self.camera_voice_mode '\
        'else "PC\'den kişi algılama sesli uyarısı"), variable=self.voice_var,',
        "Sesli uyari kutusunun etiketi",
    )
    edited = replace_one(
        edited,
        '                        self.speaker.say("Dikkat. Odada bir kişi algılandı.")',
        '                        if not self.camera_voice_mode or event["mode"] == "live":\n'
        '                            self.speaker.say("Dikkat. Odada bir kişi algılandı.")',
        "Olayin kameraya seslendirilmesi (DEMO kamera uyarisini devre disi birakir)",
    )

    ast.parse(edited, filename=str(GUI))
    ast.parse(ADAPTER_CODE, filename=str(ADAPTER))

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "c301_monitor" / f"backup_camera_voice_{timestamp}"
    if backup_dir.exists():
        raise RuntimeError("Yedek klasoru zaten var, tekrar calistirmadan kontrol et.")
    backup_dir.mkdir()
    shutil.copy2(GUI, backup_dir / "gui.py")

    # Write only after every check above passed; restore backup on any error.
    created_adapter = not ADAPTER.exists()
    try:
        if created_adapter:
            ADAPTER.write_text(ADAPTER_CODE, encoding="utf-8")
        GUI.write_text(edited, encoding="utf-8")
        compile(GUI.read_text(encoding="utf-8"), str(GUI), "exec")
    except Exception:
        shutil.copy2(backup_dir / "gui.py", GUI)
        if created_adapter:
            ADAPTER.unlink(missing_ok=True)
        raise

    print("\n[C301] KAMERA SESI ENTEGRASYONU KURULDU")
    print("Yedek:", backup_dir / "gui.py")
    print("Acik/Kapali: C301_CAMERA_VOICE=1 / 0")
    print("NOT: Sadece GERCEK kisi tespit olaylari kameradan seslenir; DEMO modu seslendirmez.")
    print("Kamera ve go2rtc yapilandirmasi degistirilmedi.")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("[C301] KURULUM DURDURULDU:", exc, file=sys.stderr)
        sys.exit(1)
