"""Local event records. Nothing is uploaded or written to a public repo."""
import json
from datetime import datetime, timezone
from pathlib import Path
import cv2


class EventRecorder:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.snapshots = self.root / "snapshots"
        self.snapshots.mkdir(parents=True, exist_ok=True)
        self.logfile = self.root / "events.jsonl"

    def save(self, frame, label: str, confidence: float | None,
             mode: str, kind: str = "detection") -> dict:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%dT%H%M%S_%fZ")
        safe_label = "".join(c if c.isascii() and c.isalnum() else "_" for c in label)[:32]
        path = self.snapshots / f"{stamp}_{safe_label}.jpg"
        if not cv2.imwrite(str(path), frame):
            raise OSError(f"Fotoğraf kaydedilemedi: {path}")
        event = {
            "timestamp_utc": now.isoformat(timespec="milliseconds"),
            "kind": kind,
            "label": label,
            "confidence": round(confidence, 3) if confidence is not None else None,
            "mode": mode,
            "image": str(path.relative_to(self.root)).replace("\\", "/"),
        }
        with self.logfile.open("a", encoding="utf-8") as out:
            out.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event
