"""C301 akilli kisi giris uyarisi - guvenli ve geri alinabilir kurulum.

Bu betik mevcut c301_monitor/gui.py, worker.py ve camera_voice_adapter.py
ustune KONTROLLU bir guncelleme yapar. go2rtc ve kamera ayarlarini degistirmez.

Kullanim:
  python install_c301_smart_person.py --check
  python install_c301_smart_person.py

Gereken: onceki install_c301_camera_voice.py entegrasyonu kurulmus olmali.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "c301_monitor"
GUI = PKG / "gui.py"
WORKER = PKG / "worker.py"
ADAPTER = PKG / "camera_voice_adapter.py"
SPEAKER = ROOT / "camera_speaker.py"
PRESENCE = PKG / "person_presence.py"
MARKER = "C301_SMART_PERSON"

PRESENCE_CODE = '''"""Kisi mevcudiyetini karelerden bagimsiz YOLO analizi zamanlarinda izler.

Bu biyometrik kisi tanima DEGiLDIR. Bir veya birden fazla kisi varken
tek bir 'odada kisi var' durumu izlenir. Giris 2 pozitif analizle onaylanir;
cikis 8 saniye surekli negatif analizle onaylanir.
"""
from __future__ import annotations


class PersonPresenceGate:
    def __init__(self, confirmations: int = 2, absence_seconds: float = 8.0):
        if confirmations < 1 or absence_seconds < 0:
            raise ValueError("Gecersiz kisi mevcudiyet esikleri")
        self.confirmations = confirmations
        self.absence_seconds = absence_seconds
        self._present = False
        self._hits = 0
        self._missing_since: float | None = None

    @property
    def present(self) -> bool:
        return self._present

    def observe(self, detected: bool, now: float) -> bool:
        """Yalnizca yeni ve onaylanmis giriste True dondurur."""
        if detected:
            self._missing_since = None
            if self._present:
                return False
            self._hits += 1
            if self._hits >= self.confirmations:
                self._present = True
                self._hits = 0
                return True
            return False

        self._hits = 0
        if self._present:
            if self._missing_since is None:
                self._missing_since = now
            elif now - self._missing_since >= self.absence_seconds:
                self._present = False
                self._missing_since = None
        return False
'''


def replace_once(src: str, old: str, new: str, label: str) -> str:
    count = src.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: beklenen kod parcasi {count} kez bulundu (1 olmali). "
            "Dosyalar degistirilmedi. Mevcut proje surumu farkli olabilir."
        )
    return src.replace(old, new, 1)


def build_changes() -> dict[Path, str]:
    required = (ROOT / "main.py", GUI, WORKER, ADAPTER, SPEAKER)
    for file in required:
        if not file.is_file():
            raise RuntimeError(f"Gerekli dosya bulunamadi: {file}")

    gui = GUI.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")

    if MARKER in gui:
        raise RuntimeError("Akilli kisi uyarisi zaten kurulu. Tekrar degisiklik yapilmadi.")
    if "C301_CAMERA_VOICE" not in gui or "C301CameraVoice" not in adapter:
        raise RuntimeError("Once kamera ses entegrasyonu kurulmali (install_c301_camera_voice.py).")
    if PRESENCE.exists():
        raise RuntimeError("person_presence.py zaten var; guvenlik icin uzerine yazilmadi.")

    worker = replace_once(
        worker,
        "from .detection import EventGate, unpack_yolo\n",
        "from .detection import EventGate, unpack_yolo\nfrom .person_presence import PersonPresenceGate\n",
        "worker: presence import",
    )
    worker = replace_once(
        worker,
        "        self._gate = EventGate()\n",
        "        self._gate = EventGate()\n"
        "        self._presence_gate = PersonPresenceGate(confirmations=2, absence_seconds=8.0)\n",
        "worker: presence gate baslatma",
    )
    worker = replace_once(
        worker,
        "        filtered = [d for d in predictions if not self.person_only or d.name == \"person\"]\n"
        "        for det in self._gate.observe(filtered, now):\n",
        "        filtered = [d for d in predictions if not self.person_only or d.name == \"person\"]\n"
        "        if self._presence_gate.observe(any(d.name == \"person\" for d in filtered), now):\n"
        "            self._emit((\"person_entered\", \"demo\" if demo else \"live\"))\n"
        "        for det in self._gate.observe(filtered, now):\n",
        "worker: YOLO presence entegrasyonu",
    )

    gui = replace_once(
        gui,
        "        self.camera_voice_mode = os.environ.get('C301_CAMERA_VOICE') == '1'\n",
        "        self.camera_voice_mode = os.environ.get('C301_CAMERA_VOICE') == '1'\n"
        "        self.smart_person_mode = (self.camera_voice_mode and\n"
        "                                  os.environ.get('C301_SMART_PERSON', '1') == '1')\n",
        "gui: akilli kisi anahtari",
    )
    gui = replace_once(
        gui,
        '                    if event["label"] == "person" and self.voice_var.get() and event["kind"] == "detection":\n',
        '                    if (event["label"] == "person" and self.voice_var.get() and\n'
        '                            event["kind"] == "detection" and not self.smart_person_mode):\n',
        "gui: eski kisi uyarisi ile cakismaz",
    )
    gui = replace_once(
        gui,
        '                elif kind == "ended":\n',
        '                elif kind == "person_entered":\n'
        '                    if (self.smart_person_mode and self.voice_var.get() and\n'
        '                            self.running and msg[1] == "live"):\n'
        '                        self.speaker.person_entered("Dikkat. Odada bir kişi algılandı.")\n'
        '                elif kind == "ended":\n',
        "gui: yeni giris olayinin sesi",
    )
    adapter = replace_once(
        adapter,
        "    def close(self):\n",
        "    def person_entered(self, message: str):\n"
        "        # Giris mantigi Worker'da; sesi tekrar yollamayi engelle.\n"
        '        return self._speaker.notify("person-presence", message, cooldown=1.0)\n\n'
        "    def close(self):\n",
        "adapter: kisi giris uyarisi",
    )

    result = {GUI: gui, WORKER: worker, ADAPTER: adapter, PRESENCE: PRESENCE_CODE}
    for path, content in result.items():
        ast.parse(content, filename=str(path))
    _validate_gate(result[PRESENCE])
    return result


def _validate_gate(source: str) -> None:
    namespace: dict = {}
    exec(compile(source, "<person_presence-test>", "exec"), namespace)
    Gate = namespace["PersonPresenceGate"]
    gate = Gate(confirmations=2, absence_seconds=8)
    assert gate.observe(True, 0) is False
    assert gate.observe(True, 0.3) is True
    assert gate.observe(True, 1.0) is False
    assert gate.observe(False, 2.0) is False
    assert gate.observe(True, 5.0) is False  # gecici YOLO kaybi
    assert gate.observe(False, 9.0) is False
    assert gate.observe(False, 17.0) is False  # kisi gorunmez, cikis onaylandi
    assert gate.observe(True, 18.0) is False
    assert gate.observe(True, 18.3) is True  # yeni giris
    assert gate.observe(True, 19) is False
    single = Gate(confirmations=2)
    assert not single.observe(True, 0)
    assert not single.observe(False, 0.1)
    assert not single.observe(True, 0.2)
    assert single.observe(True, 0.3)


def backup_dir() -> Path:
    # LocalAppData / OneDrive disi: Xiaomi anahtarlarini senkronize etmeyelim.
    local = Path(os.getenv("LOCALAPPDATA") or str(ROOT))
    base = local / "C301-AI-Security-Monitor" / "backups"
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return base / f"smart-person-{timestamp}"


def run(check: bool) -> None:
    changes = build_changes()
    if check:
        print("[C301] ON KONTROL BASARILI. Dosyalar degistirilmedi.")
        print("Etkilenecek dosyalar:")
        for path in changes:
            print(" -", path.relative_to(ROOT))
        return

    backup = backup_dir()
    backup.mkdir(parents=True, exist_ok=False)
    existing = (GUI, WORKER, ADAPTER, SPEAKER)
    for file in existing:
        shutil.copy2(file, backup / file.name)
    # Basarili ise sadece bu backup konumunda saklanir; camera config ve exe'yi de koru.
    fixed = Path(os.getenv("LOCALAPPDATA", "")) / "C301-go2rtc-audio-fix" / "go2rtc_audio_fixed.exe"
    conf = Path.home() / "OneDrive" / "Masaüstü" / "thz proje" / "go2rtc_win64" / "go2rtc.yaml"
    for optional, destination in ((fixed, "go2rtc_audio_fixed.exe"), (conf, "go2rtc.yaml")):
        if optional.is_file():
            shutil.copy2(optional, backup / destination)

    written: list[Path] = []
    try:
        for file, content in changes.items():
            file.write_text(content, encoding="utf-8")
            written.append(file)
        for file in changes:
            compile(file.read_text(encoding="utf-8"), str(file), "exec")
    except Exception:
        for file in (GUI, WORKER, ADAPTER):
            shutil.copy2(backup / file.name, file)
        if PRESENCE in written:
            PRESENCE.unlink(missing_ok=True)
        raise

    print("\n[C301] AKILLI KISI UYARISI KURULDU")
    print("Yedek klasoru:", backup)
    print("C301_CAMERA_VOICE=1 ve C301_SMART_PERSON=1 => akilli uyarilar acik")
    print("C301_SMART_PERSON=0 => eski kamera sesi davranisi")
    print("Giris: 2 ardarda kisi tespiti; cikis: 8 saniye kisi gorulmemesi")
    print("Mevcut go2rtc ve ses servisi degistirilmedi.")
    print("NOT: Bu kisi KIMLIGI tanima degil, goruntude kisi bulunma takibidir.")


def main():
    parser = argparse.ArgumentParser(description="C301 akilli kisi tespiti / sesli giris uyarisi")
    parser.add_argument("--check", action="store_true", help="Degisiklik yapmadan kontrol et")
    args = parser.parse_args()
    try:
        run(args.check)
    except Exception as exc:
        print("[C301] ISLEM DURDURULDU:", exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
