"""Low-latency RTSP capture for Ti.

FFmpeg is the sole reader of the stream, the reader thread ALWAYS drains raw
frames, and the UI/YOLO consumes only the most recent complete frame.
Never logs camera URLs or sensitive credentials. Does not modify go2rtc.
"""
from __future__ import annotations
import shutil
import subprocess
import threading
import time

import numpy as np

WIDTH, HEIGHT = 848, 480
FRAMERATE = 15


def command(ffmpeg: str, source: str, width: int = WIDTH, height: int = HEIGHT) -> list[str]:
    if not source.startswith('rtsp://127.0.0.1:8554/'):
        raise ValueError('Yalnızca yerel go2rtc RTSP akışı desteklenir.')
    if (width, height) != (WIDTH, HEIGHT):
        raise ValueError('Beklenmeyen video boyutu.')
    # Aspect preserving fit+pad: no center crop / artificial zoom.
    vf=(f'scale={width}:{height}:force_original_aspect_ratio=decrease:flags=fast_bilinear,'
        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={FRAMERATE}')
    return [ffmpeg,'-hide_banner','-loglevel','error','-nostdin',
            '-rtsp_transport','tcp','-fflags','nobuffer','-flags','low_delay',
            '-max_delay','0','-i',source,'-map','0:v:0','-an','-sn','-dn',
            '-vf',vf,'-pix_fmt','bgr24','-f','rawvideo','pipe:1']


class LatestFFmpegCapture:
    """OpenCV-like interface, with a bounded single-frame mailbox.

    Reading the pipe is independent from YOLO inference, so a costly prediction
    never blocks the decoder or accumulates stale frames in the UI.
    """
    def __init__(self, source):
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise RuntimeError('FFmpeg bulunamadı. ffmpeg -version ile kontrol edin.')
        self._closed = threading.Event()
        self._condition = threading.Condition()
        self._latest = None
        self._sequence = 0
        self._returned = 0
        self._received_at = 0.0
        self._started_at = time.monotonic()
        self._process = subprocess.Popen(
            command(ffmpeg, source), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            bufsize=WIDTH*HEIGHT*3,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self._thread = threading.Thread(target=self._reader, name='ti-rtsp-reader', daemon=True)
        self._thread.start()

    def _reader(self):
        pipe=self._process.stdout
        expected=WIDTH*HEIGHT*3
        try:
            while not self._closed.is_set():
                data=pipe.read(expected)
                if len(data)!=expected:break
                frame=np.frombuffer(data, np.uint8).reshape((HEIGHT,WIDTH,3)).copy()
                with self._condition:
                    self._latest=frame
                    self._sequence+=1
                    self._received_at=time.monotonic()
                    self._condition.notify_all()
        except (OSError, ValueError):
            pass
        finally:
            with self._condition:self._condition.notify_all()

    def isOpened(self):
        return not self._closed.is_set() and self._process.poll() is None

    def read(self):
        """(True,None) means stream alive but no fresh frame yet."""
        with self._condition:
            if self._sequence == self._returned and self.isOpened():
                self._condition.wait(timeout=.22)
            if self._sequence != self._returned:
                self._returned=self._sequence
                return True, self._latest  # consumer does not modify raw frame
        if not self.isOpened():return False,None
        if time.monotonic()-max(self._started_at,self._received_at)>8:
            return False,None
        return True,None

    def release(self):
        if self._closed.is_set():return
        self._closed.set()
        if self._process.poll() is None:
            try:self._process.terminate()
            except OSError:pass
        try:self._process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=1)
        with self._condition:self._condition.notify_all()
        if self._thread.is_alive():self._thread.join(timeout=2)
        if self._process.stdout is not None:
            try:self._process.stdout.close()
            except (OSError,ValueError):pass
