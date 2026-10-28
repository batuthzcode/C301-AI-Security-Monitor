"""Low-latency worker: capture never waits for YOLO inference.

One thread continually drains the RTSP decoder, replacing the previous frame.
A second thread (this worker's main thread) performs detection on snapshots.
This keeps the preview fresh even on slower CPUs, at the expense of predictions
which may temporarily trail the latest preview frame.
"""
import os
import queue
import threading
import time

from .demo import make_demo_frame
from .detection import EventGate, unpack_yolo
from .records import EventRecorder
from .video import LatestFrameBuffer


class CameraWorker:
    def __init__(self, source: str, messages: queue.Queue, recorder: EventRecorder,
                 *, demo: bool = False, confidence: float = .45,
                 device: str = "cpu", person_only: bool = False,
                 inference_size: int = 416, inference_interval: float = .45,
                 preview_only: bool = False):
        self.source = source
        self.messages = messages
        self.recorder = recorder
        self.demo = demo
        self.confidence = confidence
        self.device = device
        self.person_only = person_only
        self.inference_size = inference_size
        self.inference_interval = inference_interval
        self.preview_only = preview_only
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self._latest = LatestFrameBuffer()
        self._predictions = []
        self._predictions_at = 0.0
        self._pred_lock = threading.Lock()
        self._gate = EventGate()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stopped.set()
        pipe = getattr(self, "_active_pipe", None)
        if pipe is not None:
            pipe.release()

    def save_manual(self):
        _sequence, latest = self._latest.snapshot()
        frame = latest.copy() if latest is not None else None
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
            # Best effort: discard an older update rather than block capture.
            # The GUI additionally renders only the newest frame each poll.
            try:
                self.messages.get_nowait()
            except queue.Empty:
                return
            try:
                self.messages.put_nowait(message)
            except queue.Full:
                pass

    def _observe(self, frame, predictions, now, *, demo=False):
        filtered = [d for d in predictions if not self.person_only or d.name == "person"]
        for det in self._gate.observe(filtered, now):
            event = self.recorder.save(frame, det.name, det.confidence,
                                       "demo" if demo else "live")
            self._emit(("event", event))

    def _run_demo(self):
        self._emit(("status", "DEMO / sahte görüntü"))
        started = time.monotonic()
        last_display = 0.0
        while not self.stopped.is_set():
            frame, predictions = make_demo_frame(time.monotonic() - started)
            self._latest.update(frame)
            now = time.monotonic()
            self._observe(frame, predictions, now, demo=True)
            if now - last_display >= .10:
                self._emit(("frame", frame.copy(), predictions))
                last_display = now
            self.stopped.wait(.12)

    def _read_stream(self, cap):
        """Continuously read and replace frames; NEVER wait for inference."""
        no_frame_count = 0
        last_display = 0.0
        try:
            while not self.stopped.is_set():
                ok, frame = cap.read()
                if not ok:
                    no_frame_count += 1
                    if no_frame_count > 50:
                        self._emit(("error", "Kamera akışı kesildi. Bağlantıyı yeniden başlatın."))
                        self.stopped.set()
                        return
                    self.stopped.wait(.10)
                    continue
                no_frame_count = 0
                self._latest.update(frame)
                now = time.monotonic()
                if now - last_display >= .10:
                    with self._pred_lock:
                        # Avoid drawing very old bounding boxes on new frames.
                        detections = list(self._predictions) if now - self._predictions_at < 2.0 else []
                    self._emit(("frame", frame, detections))
                    last_display = now
        except Exception as exc:
            if not self.stopped.is_set():
                self._emit(("error", f"RTSP okuma hatası: {exc}"))
                self.stopped.set()
        finally:
            cap.release()

    def _run_live(self):
        import cv2
        model = None
        if not self.preview_only:
            self._emit(("status", "Model hazırlanıyor..."))
            from ultralytics import YOLO
            model = YOLO("yolo11n.pt")
        source = int(self.source) if self.source.isdecimal() else self.source
        if str(self.source).startswith("rtsp://"):
            os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        use_pipe = os.environ.get("C301_FFMPEG_PIPE") == "1" and str(self.source).startswith("rtsp://")
        cap = FFmpegPipeCapture(self.source) if use_pipe else cv2.VideoCapture(source)
        self._active_pipe = cap if use_pipe else None
        # For FFMPEG, this property might not be honored; our continuously
        # draining reader thread handles most decoder backlog in practice.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            cap.release()
            raise RuntimeError("Görüntü kaynağı açılamadı. go2rtc akışını ve adresi kontrol edin.")
        self._emit(("status", "Canlı akış bağlı (yalnızca önizleme)" if self.preview_only
                    else "Canlı akış bağlı (düşük gecikme modu)"))
        capture_thread = threading.Thread(target=self._read_stream, args=(cap,), daemon=True)
        capture_thread.start()
        last_infer_start = 0.0
        processed_seq = 0
        try:
            if self.preview_only:
                # Isolate capture/transcoding latency without YOLO, recording or alerts.
                self.stopped.wait()
                return
            while not self.stopped.is_set():
                now = time.monotonic()
                if now - last_infer_start < self.inference_interval:
                    self.stopped.wait(min(.08, self.inference_interval - (now - last_infer_start)))
                    continue
                seq, frame = self._latest.snapshot()
                if frame is None or seq == processed_seq:
                    self.stopped.wait(.025)
                    continue
                # YOLO reads a stable snapshot while the camera reader continues.
                processed_seq = seq
                last_infer_start = time.monotonic()
                result = model.predict(frame.copy(), conf=self.confidence,
                                       imgsz=self.inference_size, device=self.device,
                                       verbose=False)[0]
                predictions = unpack_yolo(result)
                with self._pred_lock:
                    self._predictions = predictions
                    self._predictions_at = time.monotonic()
                self._observe(frame, predictions, self._predictions_at)
        finally:
            self.stopped.set()
            capture_thread.join(timeout=3.0)

    def _run(self):
        try:
            if self.demo:
                self._run_demo()
            else:
                self._run_live()
        except Exception as error:
            self._emit(("error", str(error)))
        finally:
            self.stopped.set()
            self._emit(("status", "Bağlantı kapalı"))
            self._emit(("ended",))


class FFmpegPipeCapture:
    def __init__(self, url):
        import subprocess
        import shutil
        import numpy as np
        from latency_probe_ffmpeg import ffmpeg_command

        binary = shutil.which("ffmpeg")
        if binary is None:
            raise RuntimeError("FFmpeg bulunamadi")

        self.np = np
        self.subprocess = subprocess
        self.size = 960 * 540 * 3
        self.closed = False

        self.process = subprocess.Popen(
            ffmpeg_command(binary, url, 960, 540),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=self.size
        )

    def isOpened(self):
        return not self.closed and self.process.poll() is None

    def set(self, prop, value):
        return False

    def read(self):
        if self.closed:
            return False, None

        try:
            data = self.process.stdout.read(self.size)
        except (OSError, ValueError):
            return False, None

        if len(data) != self.size:
            return False, None

        frame = self.np.frombuffer(
            data, dtype=self.np.uint8
        ).reshape(540, 960, 3).copy()

        return True, frame

    def release(self):
        if self.closed:
            return

        self.closed = True

        if self.process.poll() is None:
            self.process.terminate()

        try:
            self.process.wait(timeout=2)
        except self.subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)

        if self.process.stdout is not None:
            self.process.stdout.close()
