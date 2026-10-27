"""Video capture/inference on a worker thread. The GUI remains responsive."""
import os
import queue
import threading
import time

from .demo import make_demo_frame
from .detection import EventGate, unpack_yolo
from .records import EventRecorder


class CameraWorker:
    def __init__(self, source: str, messages: queue.Queue, recorder: EventRecorder,
                 *, demo: bool = False, confidence: float = .45,
                 device: str = "cpu", person_only: bool = False):
        self.source = source
        self.messages = messages
        self.recorder = recorder
        self.demo = demo
        self.confidence = confidence
        self.device = device
        self.person_only = person_only
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self._current_frame = None
        self._frame_lock = threading.Lock()
        self._gate = EventGate()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()

    def save_manual(self):
        with self._frame_lock:
            frame = self._current_frame.copy() if self._current_frame is not None else None
        if frame is None:
            return None
        event = self.recorder.save(frame, "manual", None,
                                   "demo" if self.demo else "live", "manual")
        self._emit(("event", event))
        return event

    def _emit(self, message):
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            # Drop oldest video frame rather than block capture indefinitely.
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            try:
                self.messages.put_nowait(message)
            except queue.Full:
                pass

    def _run(self):
        import cv2
        cap = None
        try:
            self._emit(("status", "Model hazırlanıyor..." if not self.demo else "DEMO modunda"))
            if self.demo:
                model = None
            else:
                # Delay import/download until a real stream is requested.
                from ultralytics import YOLO
                model = YOLO("yolo11n.pt")
                source = int(self.source) if self.source.isdecimal() else self.source
                if str(self.source).startswith("rtsp://"):
                    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
                cap = cv2.VideoCapture(source)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # best effort only
                if not cap.isOpened():
                    raise RuntimeError("Görüntü kaynağı açılamadı. go2rtc akışını ve adresi kontrol edin.")
            self._emit(("status", "DEMO / sahte görüntü" if self.demo else "Canlı akış bağlı"))
            previous_predictions = []
            last_predict = 0.0
            last_display = 0.0
            no_frame_count = 0
            start = time.monotonic()
            while not self.stopped.is_set():
                if self.demo:
                    frame, previous_predictions = make_demo_frame(time.monotonic() - start)
                    time.sleep(.12)
                else:
                    ok, frame = cap.read()
                    if not ok:
                        no_frame_count += 1
                        if no_frame_count > 50:
                            raise RuntimeError("Kamera akışı kesildi. Bağlantıyı yeniden başlatın.")
                        time.sleep(.10)
                        continue
                    no_frame_count = 0
                    # Rate limit CPU inference for responsiveness.
                    if time.monotonic() - last_predict >= .45:
                        out = model.predict(frame, conf=self.confidence,
                                            imgsz=640, device=self.device,
                                            verbose=False)[0]
                        previous_predictions = unpack_yolo(out)
                        last_predict = time.monotonic()
                detections = [d for d in previous_predictions
                              if not self.person_only or d.name == "person"]
                now = time.monotonic()
                for det in self._gate.observe(detections, now):
                    # Full images can be sensitive; saved only on this local PC.
                    event = self.recorder.save(frame, det.name, det.confidence,
                                               "demo" if self.demo else "live")
                    self._emit(("event", event))
                with self._frame_lock:
                    self._current_frame = frame.copy()
                if now - last_display > .095:
                    self._emit(("frame", frame.copy(), detections))
                    last_display = now
        except Exception as error:
            self._emit(("error", str(error)))
        finally:
            if cap is not None:
                cap.release()
            self._emit(("status", "Bağlantı kapalı"))
            self._emit(("ended",))
