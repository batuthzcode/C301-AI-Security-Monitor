"""The preview-only mode must not load a YOLO model or record detections."""
import queue
import tempfile
import time
import unittest
from unittest.mock import patch

from c301_monitor.records import EventRecorder
from c301_monitor.worker import CameraWorker
import numpy as np


class FakeCapture:
    def __init__(self, source):
        self.count = 0
        self.released = False
    def isOpened(self):
        return True
    def set(self, *args):
        return True
    def read(self):
        time.sleep(.015)
        self.count += 1
        return True, np.full((32,32,3), self.count % 255, dtype=np.uint8)
    def release(self):
        self.released = True


class PreviewOnlyTests(unittest.TestCase):
    def test_preview_continues_without_yolo(self):
        fake = FakeCapture("rtsp://example/stream")
        with tempfile.TemporaryDirectory() as directory:
            worker = CameraWorker("rtsp://example/stream", queue.Queue(maxsize=30),
                                  EventRecorder(directory), preview_only=True)
            # Any attempt to import ultralytics would fail this test in environments
            # where YOLO is not installed, but none should occur in this mode.
            with patch("cv2.VideoCapture", return_value=fake):
                worker.start()
                time.sleep(0.20)
                worker.stop()
                worker.thread.join(timeout=3)
        self.assertFalse(worker.thread.is_alive())
        self.assertTrue(fake.released)
        self.assertGreater(fake.count, 3)
        self.assertGreater(worker._latest.snapshot()[0], 3)


if __name__ == "__main__":
    unittest.main()
