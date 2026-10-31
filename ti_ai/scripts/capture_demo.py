"""Create a truthful, credential-free screenshot of the Ti AI desktop UI."""
from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402
from Ti_Kontrol_Merkezi_v1 import Window  # noqa: E402


def main() -> int:
    output = ROOT / "assets" / "ti-ai-v2.3-demo.png"
    app = QApplication([])
    app.setApplicationName("Ti Kontrol Merkezi")
    app.setStyle("Fusion")
    window = Window()
    window.resize(1440, 860)
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
