"""Append a milestone template to docs/DEVLOG.md for a future working session."""
from datetime import datetime
from pathlib import Path


if __name__ == "__main__":
    file = Path(__file__).resolve().parents[1] / "docs" / "DEVLOG.md"
    title = input("Yapılan çalışma / milestone: ").strip()
    changes = input("Değişiklikler: ").strip()
    tests = input("Testler ve sonuçları: ").strip()
    blockers = input("Sorunlar / kalan işler: ").strip()
    date = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    with file.open("a", encoding="utf-8") as out:
        out.write(f"\n## {date} — {title or 'Yeni çalışma'}\n\n")
        out.write(f"- Değişiklikler: {changes or 'Belirtilmedi'}\n")
        out.write(f"- Testler: {tests or 'Henüz yapılmadı'}\n")
        out.write(f"- Sorunlar / sıradaki adım: {blockers or 'Belirtilmedi'}\n")
    print(f"Kaydedildi: {file}")
