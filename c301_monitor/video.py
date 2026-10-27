"""Drop-old-frame buffer for low-latency video capture.

Frames are treated as immutable once passed to `update`; OpenCV normally
returns a new ndarray for each read. Consumers copy before editing.
"""
import threading


class LatestFrameBuffer:
    def __init__(self):
        self._lock = threading.Lock()
        self._frame = None
        self._sequence = 0

    def update(self, frame):
        with self._lock:
            self._frame = frame
            self._sequence += 1

    def snapshot(self):
        with self._lock:
            return self._sequence, self._frame
