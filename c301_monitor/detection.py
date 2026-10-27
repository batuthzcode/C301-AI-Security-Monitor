"""Portable detection metadata and an event debouncer.

The 'radar' shown by the UI is strictly a 2D image-coordinate visualization,
not a true radar and not a way to infer physical distance.
"""
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Detection:
    name: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    track_id: int | None = None

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


class EventGate:
    """A new event occurs when a class reappears after being absent.

    At most one event per class per min_interval seconds. This is a
    class-level appearance detector, NOT a unique person tracker.
    """

    def __init__(self, gap: float = 6.0, min_interval: float = 30.0):
        self.gap = gap
        self.min_interval = min_interval
        self.last_seen: dict[str, float] = {}
        self.last_event: dict[str, float] = {}

    def observe(self, detections: Iterable[Detection], now: float) -> list[Detection]:
        # Use the highest-confidence object of a given class.
        selected: dict[str, Detection] = {}
        for det in detections:
            if det.name not in selected or selected[det.name].confidence < det.confidence:
                selected[det.name] = det
        events: list[Detection] = []
        for name, det in selected.items():
            previously_seen = self.last_seen.get(name)
            previous_event = self.last_event.get(name)
            appeared = previously_seen is None or now - previously_seen >= self.gap
            cooled = previous_event is None or now - previous_event >= self.min_interval
            if appeared and cooled:
                events.append(det)
                self.last_event[name] = now
            self.last_seen[name] = now
        return events


def unpack_yolo(result) -> list[Detection]:
    """Convert a single Ultralytics Results object to lightweight data."""
    detections: list[Detection] = []
    if result.boxes is None:
        return detections
    for box in result.boxes:
        class_id = int(box.cls[0].item())
        score = float(box.conf[0].item())
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        tid = getattr(box, 'id', None)
        track_id = int(tid[0].item()) if tid is not None else None
        detections.append(Detection(str(result.names[class_id]), score,
                                    x1, y1, x2, y2, track_id))
    return detections
