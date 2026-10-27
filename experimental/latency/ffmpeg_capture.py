"""RTSP low-buffer FFmpeg raw-BGR reader for C301.

VideoCapture-compatible adapter used by CameraWorker; it reads the same FFmpeg
pipeline which was tested successfully in the standalone latency probe.
No shell, no camera-side settings, no go2rtc configuration changes.
"""
from __future__ import annotations

import shutil
import subprocess
import threading

import numpy as np


def ffmpeg_command(binary: str, source: str, width: int, height: int) -> list[str]:
    if width <= 0 or height <= 0 or width > 3840 or height > 2160:
        raise ValueError("Invalid preview dimensions")
    if not source:
        raise ValueError("Camera source is required")
    return [
        binary, "-hide_banner", "-loglevel", "error", "-nostdin",
        "-rtsp_transport", "tcp", "-fflags", "nobuffer",
        "-flags", "low_delay", "-max_delay", "0",
        "-i", source, "-map", "0:v:0", "-an", "-sn", "-dn",
        "-vf", f"scale={width}:{height}:flags=fast_bilinear",
        "-pix_fmt", "bgr24", "-f", "rawvideo",
        "-fps_mode", "passthrough", "pipe:1",
    ]


class FFmpegCapture:
    """Stream frames into NumPy without OpenCV's VideoCapture backlog.

    One read thread owns read(); a different thread may call release() to end
    blocking pipe reads when the user stops the GUI. Output is BGR, writable.
    """
    def __init__(self, source: str, width: int = 960, height: int = 540):
        executable = shutil.which("ffmpeg")
        if executable is None:
            raise RuntimeError("FFmpeg bulunamadı. Yeni PowerShell açıp ffmpeg -version deneyin.")
        self.width, self.height = width, height
        self.frame_bytes = width * height * 3
        self._lock = threading.Lock()
        self._released = False
        self._process = subprocess.Popen(
            ffmpeg_command(executable, source, width, height),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # no blocked stderr pipe / no token leaking to console
            bufsize=self.frame_bytes,
        )

    def isOpened(self) -> bool:
        return not self._released and self._process.poll() is None

    def set(self, _key, _value):
        return False  # FFmpeg command already owns buffering policy.

    def read(self):
        with self._lock:
            if self._released:
                return False, None
        # BufferedReader.read(n) fills n bytes until EOF; no partial-frame display.
        pipe = self._process.stdout
        if pipe is None:
            return False, None
        try:
            packet = pipe.read(self.frame_bytes)
        except (OSError, ValueError):  # released while another thread was reading
            return False, None
        if len(packet) != self.frame_bytes:
            return False, None
        return True, np.frombuffer(packet, dtype=np.uint8).reshape(
            self.height, self.width, 3
        ).copy()  # writable BGR for OpenCV overlays / YOLO

    def release(self):
        with self._lock:
            if self._released:
                return
            self._released = True
        process = self._process
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1.5)
        if process.stdout is not None:
            process.stdout.close()
