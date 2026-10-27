"""Regression test: slow inference should not block continuous frame capture."""
import queue
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import numpy as np

from c301_monitor.records import EventRecorder
from c301_monitor.worker import CameraWorker


class FakeCapture:
    def __init__(self, source):
        self.count = 0
        self.released = False

    def isOpened(self):
        return True

    def set(self, key, value):
        return True

    def read(self):
        time.sleep(.017)
        self.count += 1
        return True, np.full((32, 32, 3), self.count % 256, dtype=np.uint8)

    def release(self):
        self.released = True


class FakeYolo:
    call_count = 0

    def __init__(self, *args, **kwargs):
        pass

    def predict(self, *args, **kwargs):
        type(self).call_count += 1
        time.sleep(.12)  # artificially expensive model
        return [types.SimpleNamespace(boxes=None)]


class CaptureTests(unittest.TestCase):
    def test_capture_continues_during_inference(self):
        FakeYolo.call_count = 0
        capture = FakeCapture("rtsp://example/stream")
        with tempfile.TemporaryDirectory() as directory:
            worker = CameraWorker("rtsp://example/stream", queue.Queue(maxsize=50),
                                  EventRecorder(directory), inference_size=416,
                                  inference_interval=.1)
            stub = types.ModuleType("ultralytics")
            stub.YOLO = FakeYolo
            with patch.dict(sys.modules, {"ultralytics": stub}), \
                 patch("cv2.VideoCapture", return_value=capture):
                worker.start()
                time.sleep(.72)
                worker.stop()
                worker.thread.join(timeout=2)
        self.assertFalse(worker.thread.is_alive())
        self.assertTrue(capture.released)
        self.assertGreater(FakeYolo.call_count, 1)
        # In older synchronous design reads would match model calls closely.
        self.assertGreater(capture.count, 2 * FakeYolo.call_count)
        seq, latest = worker._latest.snapshot()
        self.assertEqual(seq, capture.count)
        self.assertIsNotNone(latest)


if __name__ == "__main__":
    unittest.main()
