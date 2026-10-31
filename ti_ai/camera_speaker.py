"""Xiaomi C301 camera speaker, via patched go2rtc and Google TTS.

Requirements:
  pip install gTTS
  FFmpeg and FFprobe available on PATH
  patched go2rtc running at http://127.0.0.1:1984
  the c301_ses_test stream configured with Xiaomi audio enabled

Examples:
  python camera_speaker.py "Merhaba! Ses sistemim hazir."
  from camera_speaker import C301Speaker
  speaker = C301Speaker()
  speaker.notify("person", "Dikkat! Odada bir kisi algilandi.", cooldown=60)
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from gtts import gTTS


ROOT = Path(__file__).resolve().parent
VOICE_DIR = ROOT / "_voice_test"
GO2RTC_API = "http://127.0.0.1:1984"
STREAM_NAME = "c301_ses_test"
AUDIO_PORT = 8766  # Separate from the existing 8765 test HTTP server


class _QuietFileHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


class C301Speaker:
    """One instance per program. Keep it alive while detection is running."""

    def __init__(self, *, api: str = GO2RTC_API,
                 stream: str = STREAM_NAME, port: int = AUDIO_PORT):
        self.api = api.rstrip("/")
        self.stream = stream
        self.port = port
        self.voice_dir = VOICE_DIR
        self.voice_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._cooldown_lock = threading.Lock()
        self._last_notice: dict[str, float] = {}
        self._queue: queue.Queue[str | None] = queue.Queue(maxsize=4)
        self._closed = False
        self._viewer: subprocess.Popen | None = None
        self._flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        handler = functools.partial(_QuietFileHandler, directory=str(self.voice_dir))
        try:
            self._server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as exc:
            raise RuntimeError(
                f"Yerel ses sunucusu acilamadi (127.0.0.1:{port}). "
                "Bu modulu iki kez calistirmadigindan emin ol."
            ) from exc
        self._server_thread = threading.Thread(
            target=self._server.serve_forever, daemon=True,
            name="c301-audio-http"
        )
        self._server_thread.start()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True,
                                        name="c301-speech-worker")
        self._worker.start()

    def _start_viewer(self) -> None:
        if self._viewer is not None and self._viewer.poll() is None:
            return
        # Keep go2rtc's Xiaomi producer connected without decoding H.265.
        cmd = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-rtsp_transport", "tcp", "-i",
            f"rtsp://127.0.0.1:8554/{self.stream}",
            "-map", "0:v:0", "-c:v", "copy", "-an", "-f", "null", "-",
        ]
        try:
            self._viewer = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, creationflags=self._flags,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("FFmpeg bulunamadi. PATH ayarini kontrol et.") from exc

    def _wait_for_speaker(self, timeout: float = 35.0) -> None:
        self._start_viewer()
        deadline = time.monotonic() + timeout
        last_error = ""
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(self.api + "/api/streams", timeout=5) as resp:
                    data = json.load(resp)
                stream_info = data.get(self.stream)
                if not stream_info:
                    raise RuntimeError(
                        f"'{self.stream}' go2rtc'de yok. Ses test akisinin "
                        "Xiaomi audio=1 ile yapilandirildigini kontrol et."
                    )
                for prod in stream_info.get("producers", []):
                    medias = prod.get("medias") or []
                    if any(
                        "audio" in str(m).lower()
                        and "sendonly" in str(m).lower()
                        and "opus" in str(m).lower()
                        for m in medias
                    ):
                        return
                last_error = "OPUS sendonly ses kanali henüz gorunmuyor"
            except RuntimeError:
                raise
            except (OSError, ValueError, urllib.error.URLError) as exc:
                last_error = type(exc).__name__
            if self._viewer is not None and self._viewer.poll() is not None:
                last_error = "FFmpeg kamera test akisini acamadi"
                self._start_viewer()
            time.sleep(1)
        raise RuntimeError(
            "Kamera hoparlor kanali acilamadi: " + last_error
            + ". go2rtc konsolunu ve c301_ses_test akisinin goruntusunu kontrol et."
        )

    def _duration_seconds(self, file: Path, fallback: float) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(file)],
                capture_output=True, text=True, timeout=8,
                creationflags=self._flags,
            )
            if result.returncode == 0:
                return max(1.0, min(float(result.stdout.strip()), 180.0))
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
        return max(5.0, min(fallback, 120.0))

    def say(self, text: str) -> None:
        """Speak once; blocks until the audio file has finished playing."""
        text = text.strip()
        if not text:
            return
        if self._closed:
            raise RuntimeError("C301Speaker kapatilmis.")
        with self._lock:
            self._wait_for_speaker()
            filename = f"c301_{uuid.uuid4().hex}.mp3"
            file = self.voice_dir / filename
            try:
                # gTTS needs an Internet connection.
                gTTS(text=text, lang="tr").save(str(file))
                duration = self._duration_seconds(file, len(text) / 11 + 3)
                media_url = f"http://127.0.0.1:{self.port}/{filename}"
                source = f"ffmpeg:{media_url}#audio=opus#input=file"
                query = urllib.parse.urlencode({"dst": self.stream, "src": source})
                request = urllib.request.Request(
                    f"{self.api}/api/streams?{query}", method="POST"
                )
                try:
                    with urllib.request.urlopen(request, timeout=20) as response:
                        response.read()
                except urllib.error.HTTPError as exc:
                    detail = exc.read().decode("utf-8", "replace")
                    raise RuntimeError(
                        f"go2rtc ses gonderimi basarisiz (HTTP {exc.code}): "
                        + detail.strip()[:400]
                    ) from exc
                # go2rtc starts FFmpeg asynchronously; keep the file available
                # for playback before removing it.
                print(f"[C301] Ses gonderildi: {text}")
                time.sleep(duration + 3)
            finally:
                file.unlink(missing_ok=True)

    def notify(self, key: str, text: str, *, cooldown: float = 60.0) -> bool:
        """Queue one non-blocking event alert; avoid repeated YOLO-frame alerts."""
        now = time.monotonic()
        with self._cooldown_lock:
            if self._closed or now - self._last_notice.get(key, -1e12) < cooldown:
                return False
            try:
                self._queue.put_nowait(text)
            except queue.Full:
                return False
            self._last_notice[key] = now
        return True

    def _worker_loop(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                self._queue.task_done()
                break
            try:
                self.say(text)
            except Exception as exc:
                print(f"[C301] Ses uyarisi hatasi: {exc}")
            finally:
                self._queue.task_done()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._viewer is not None and self._viewer.poll() is None:
            self._viewer.terminate()
            try:
                self._viewer.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._viewer.kill()
        self._server.shutdown()
        self._server.server_close()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Xiaomi C301 Turkish camera speaker")
    parser.add_argument("text", nargs="*", help="Kameranin soylemesini istedigin metin")
    args = parser.parse_args()
    text = " ".join(args.text).strip() or "Merhaba. C301 yapay zeka ses sistemim hazir."
    with C301Speaker() as speaker:
        speaker.say(text)
    print("[C301] Ses testi tamamlandi.")


if __name__ == "__main__":
    main()
