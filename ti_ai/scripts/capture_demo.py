"""Create a truthful, credential-free screenshot of the Ti AI desktop UI."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from Ti_Kontrol_Merkezi_v1 import Window  # noqa: E402


SECTIONS = {
    "home": (0, "ti-ai-v2.3-demo.png"),
    "ar": (8, "ti-ai-v2.3-ar-studio.png"),
    "cyber": (9, "ti-ai-v2.3-cyber-soc.png"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=SECTIONS, default="home")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    section_index, default_name = SECTIONS[args.section]
    output = args.output or ROOT / "assets" / default_name
    app = QApplication([])
    app.setApplicationName("Ti Kontrol Merkezi")
    app.setStyle("Fusion")
    window = Window()
    window.resize(1440, 860)
    window.show_section(section_index)
    if args.section == "ar":
        # The app itself marks this render as synthetic; it proves only the
        # overlay/display path and does not pretend to be real inference.
        window.ar_visual_test()
    elif args.section == "cyber":
        # Never expose the developer's real LAN inventory in a public image.
        window.net_state.setText("SENTETİK DEMO • Gerçek ağ taraması yapılmadı")
        window.net_output.setPlainText(
            "Cyber SOC önizlemesi\n\n"
            "• Yerel IP / bağlantı / ARP teşhisi\n"
            "• İzinli 12 saniyelik TShark metaveri analizi\n"
            "• Ham paket kaydı yok\n"
            "• Rapor yalnız kullanıcı isterse JSON olarak dışa aktarılır\n\n"
            "Bu görüntüde gerçek IP, alan adı veya ağ cihazı kullanılmadı."
        )
        window.cyber_status.setText("SENTETİK DEMO • Kişisel IP/MAC bilgisi gösterilmez")
        window.cyber_output.setPlainText(
            "Manuel cihaz envanteri karşılaştırması\n\n"
            "Yeni cihaz: örnek-telefon\n"
            "Durum: Kullanıcı onayı ve yerel JSON gerekir\n\n"
            "Otomatik modem oturumu veya parola toplama yapılmaz."
        )
    window.show()

    result = {"ok": False}

    def capture() -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        result["ok"] = window.grab().save(str(output), "PNG")
        window.close()
        app.quit()

    QTimer.singleShot(900, capture)
    app.exec()
    print(output)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
