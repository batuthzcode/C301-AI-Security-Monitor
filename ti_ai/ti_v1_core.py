"""TI Control Center - v0.6 sesli asistan cekirdegi (v0.7 panel uyarlamasi).

Baslangic: "Merhaba Ti". Sonra "Ti sistem durumu ne", "Ti nasilsin".
"Ti" tek basina denirse sonraki bir komut icin kisa sure dinler.
Ses kameranin mikrofonundan RTSP/go2rtc ile alinir;
metne donusum PC'de faster-whisper ile yapilir ve cevap kamera_speaker.py
araciligiyla C301 hoparlorunden verilir.

Normal calismada ses dosyasi kaydedilmez. --mic-test kisa bir WAV kaydi olusturur.
Mevcut YOLO/GUI dosyalarini veya go2rtc ayarlarini DEGISTIRMEZ.
"""
from __future__ import annotations

import argparse
import array
import collections
import datetime as dt
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import wave

ROOT = Path(__file__).resolve().parent
STREAM = "c301_ses_test"
RTSP = "rtsp://127.0.0.1:8554"
GO2RTC = "http://127.0.0.1:1984"
SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2
WIN_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def normalize(text: str) -> str:
    """Turkce harfleri ve noktalama farklarini normalize et."""
    text = (text or "").strip().lower().replace("ı", "i")
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Komutlar cumlenin basinda olmali: "Ti" kelimesinin baska bir
# cumlenin ortasinda gecmesi asistani yanlislikla tetiklemesin.
# "t i" Whisper'in harfleri ayri yazdigi durumlar icindir.
TI_NAME = r"(?:ti|tii|t\s+i)"
WAKE_PATTERN = re.compile(rf"^(?:merhaba|hey|selam)\s+{TI_NAME}(?=\s|$)")
TI_COMMAND_PATTERN = re.compile(rf"^{TI_NAME}(?=\s|$)")


def wake_remainder(text: str) -> str | None:
    """'Merhaba Ti' ile basliyorsa komut kalani; degilse None."""
    cleaned = normalize(text)
    match = WAKE_PATTERN.match(cleaned)
    return cleaned[match.end():].strip() if match else None


def ti_command_remainder(text: str) -> str | None:
    """'Ti sistem durumu ne' -> 'sistem durumu ne'; sadece 'Ti' -> ''."""
    cleaned = normalize(text)
    match = TI_COMMAND_PATTERN.match(cleaned)
    return cleaned[match.end():].strip() if match else None


def interpret_utterance(text: str, *, active: bool, followup: bool = False) -> tuple[str, str]:
    """Donus: (wake | command | prompt | followup | ignore, komut).

    Ilk defa mutlaka 'Merhaba Ti' gerekli. Sonra her zaman
    'Ti <komut>' kabul edilir; zaman asimi yalnizca tek basina 'Ti'
    denildikten sonra komutun onsuz soylenmesi icin uygulanir.
    """
    wake = wake_remainder(text)
    if wake is not None:
        return "wake", wake
    if not active:
        return "ignore", ""
    command = ti_command_remainder(text)
    if command is not None:
        return ("command", command) if command else ("prompt", "")
    if followup and normalize(text):
        return "followup", normalize(text)
    return "ignore", ""


def is_sleep_command(command: str) -> bool:
    c = normalize(command)
    return any(phrase in c for phrase in ("uykuya gec", "iyi geceler", "gorusuruz", "sus"))


def rms(frame: bytes) -> float:
    if not frame:
        return 0.0
    values = array.array("h")
    values.frombytes(frame)
    if not values:
        return 0.0
    return math.sqrt(sum(int(v) ** 2 for v in values) / len(values))


class UtteranceGate:
    """Basit ses aktivitesi algilama; sessizlikte cumleyi sonlandirir.

    Enerji esigi ortama baglidir. Mikrofon testinden sonra --threshold ile
    degistirilebilir. Tek basina yuz/kisi/ses tanima yapmaz.
    """

    def __init__(self, threshold: float = 220, silence_ms: int = 1000,
                 min_speech_ms: int = 180, max_speech_seconds: float = 12):
        self.threshold = threshold
        self.silence_frames = max(1, silence_ms // FRAME_MS)
        self.min_frames = max(1, min_speech_ms // FRAME_MS)
        self.max_frames = max(1, int(max_speech_seconds * 1000 / FRAME_MS))
        self.preroll = collections.deque(maxlen=15)
        self.reset()

    def reset(self) -> None:
        self.recording = False
        self.frames: list[bytes] = []
        self.loud_frames = 0
        self.quiet_frames = 0
        self.start_streak = 0
        self.preroll.clear()

    def feed(self, frame: bytes) -> bytes | None:
        if len(frame) != FRAME_BYTES:
            return None
        loud = rms(frame) >= self.threshold
        if not self.recording:
            self.preroll.append(frame)
            self.start_streak = self.start_streak + 1 if loud else 0
            if self.start_streak >= 2:
                self.recording = True
                self.frames = list(self.preroll)
                self.loud_frames = self.start_streak
                self.quiet_frames = 0
            return None

        self.frames.append(frame)
        if loud:
            self.loud_frames += 1
            self.quiet_frames = 0
        else:
            self.quiet_frames += 1

        if self.quiet_frames >= self.silence_frames or len(self.frames) >= self.max_frames:
            audio = b"".join(self.frames) if self.loud_frames >= self.min_frames else None
            self.reset()
            return audio
        return None


def answer_command(command: str) -> str:
    """Bu ilk surum kural tabanli: genel sohbet/LLM henuz bagli degil."""
    c = normalize(command)
    now = dt.datetime.now()
    if not c:
        return "Merhaba. Ben Ti. Seni dinliyorum."
    # Whisper, kisa Turkce sorulari farkli eklerle yazabiliyor.
    # "Saat kac?", "Saat kaci?", "Simdi saat ne?" ayni komuttur.
    if any(x in c for x in (
        "saat kac", "saat kaci", "saat kactir", "saat kacta", "saat nedir",
        "saat ne", "saati soyle", "saati soyler", "saatin kac",
        "simdi saat", "su an saat", "su anda saat",
    )):
        return f"Saat {now.hour} {now.minute:02d}."
    if any(x in c for x in ("tarih ne", "bugun ayin", "bugun tarih", "bugun gunlerden")):
        days = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        months = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
                  "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        return f"Bugün {now.day} {months[now.month]} {now.year}, {days[now.weekday()]}."
    if any(x in c for x in ("nasilsin", "iyi misin", "keyfin nasil")):
        return "İyiyim, teşekkür ederim. Sistemim aktif, yardımcı olmaya hazırım."
    if any(x in c for x in ("adin ne", "sen kimsin", "kendini tanit")):
        return "Ben Ti. Xiaomi C301 güvenlik asistanıyım. Seni duyabilir ve kameradan cevap verebilirim."
    if any(x in c for x in ("sistem durumu", "sistemin durumu", "sistem durum", "sistem durumunu",
        "sistem ne durumda", "sistem nasil", "sistem calisiyor", "sistem acik",
        "durumun nasil", "calisiyor musun", "ses testi")):
        return "Ti sesli asistan sistemi aktif. Mikrofon üzerinden dinliyorum, kameranın hoparlöründen yanıt veriyorum."
    if any(x in c for x in ("yardim", "neler yapabilirsin", "ne yapabilirsin")):
        return "Merhaba Ti ile baslat. Sonra Ti saat kaç, Ti sistem durumu ne veya Ti nasılsın diyebilirsin."
    if any(x in c for x in ("kac kisi", "odada kim var", "beni goruyor musun")):
        return "Bu sesli asistan sürümüne canlı kişi sayımı henüz bağlanmadı. Kamera algılama sistemi ayrı çalışıyor."
    if any(x in c for x in ("tesekkur", "sag ol", "sagol")):
        return "Rica ederim."
    if any(x in c for x in ("iyi geceler", "gorusuruz", "uykuya gec", "sus")):
        return "Tamam, tekrar Merhaba Ti dediğinde buradayım."
    return "Bu komutu henüz öğrenmedim. Bana saati, tarihi veya sistem durumunu sorabilirsin."


def read_exact(pipe, size: int) -> bytes:
    """Unbuffered Windows pipe sometimes returns short reads."""
    result = bytearray()
    while len(result) < size:
        block = pipe.read(size - len(result))
        if not block:
            return b""
        result.extend(block)
    return bytes(result)




# -------- TI CAMERA MOTOR / VISUAL FOLLOW (experimental, opt-in) --------
# Local go2rtc v1.9.15 does NOT provide native PTZ by default.
# This controller only uses an explicit, separate experimental localhost endpoint.
MOTOR_CODES = {"left": 1, "right": 2, "up": 3, "down": 4}


def movement_intent(command: str) -> tuple[str, str] | None:
    c = normalize(command)
    # Order matters: stop follow before generic stop.
    if any(x in c for x in ("takibi durdur", "takip etmeyi birak", "beni takip etme")):
        return "follow_off", ""
    if any(x in c for x in ("beni takip et", "kisiyi takip et", "takibi baslat")):
        return "follow_on", ""
    if any(x in c for x in ("bana don", "beni bul", "bana bak")):
        return "center_person", ""
    if any(x in c for x in ("sesin geldigi yere", "sesime don", "sesimi takip et")):
        return "voice_direction", ""
    if any(x in c for x in ("kamerayi durdur", "hareketi durdur", "motoru durdur")):
        return "motor_stop", ""
    directions = {
        "left": ("sola don", "sola bak", "sola cevir", "sol tarafa don"),
        "right": ("saga don", "saga bak", "saga cevir", "sag tarafa don"),
        "up": ("yukari bak", "yukari don", "kamerayi kaldir"),
        "down": ("asagi bak", "asagi don", "kamerayi indir"),
    }
    for direction, phrases in directions.items():
        if any(phrase in c for phrase in phrases):
            return "move", direction
    return None


class TiMotor:
    """One step per request; never sends unknown commands or continuous rotation."""

    def __init__(self, enabled: bool = False, stream: str = STREAM):
        self.enabled = enabled
        self.stream = stream
        self._last_move = 0.0
        self._lock = threading.Lock()

    def move(self, direction: str) -> tuple[bool, str]:
        if not self.enabled:
            return False, "Motor denetimi henüz etkin değil. Önce ayrı PTZ deneme sürümünü kurmalıyız."
        if direction not in MOTOR_CODES:
            return False, "Geçersiz hareket yönü."
        with self._lock:
            if time.monotonic() - self._last_move < 2.8:
                return False, "Motor için kısa bir bekleme süresi var."
            query = urllib.parse.urlencode({"src": self.stream, "operation": MOTOR_CODES[direction]})
            req = urllib.request.Request(
                f"{GO2RTC}/api/xiaomi/motor?{query}", method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as res:
                    res.read()
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return False, "Bu go2rtc sürümünde PTZ motor kontrolü henüz bulunmuyor."
                return False, f"Motor kontrolü reddedildi. HTTP {exc.code}."
            except (OSError, urllib.error.URLError):
                return False, "Motor bağlantısına ulaşılamadı."
            self._last_move = time.monotonic()
            print(f"[Ti/Motor] {direction} icin tek adim komutu iletildi. Fiziksel hareket dogrulanmadi.", flush=True)
            return True, "Tek adımlık hareket komutu gönderildi. Kameranın gerçekten dönüp dönmediğini kontrol et."


class TiPersonFollower:
    """Bounded, opt-in visual following. No directional-audio inference.

    Horizontal-only by default. At most 4 automatic motor steps per voice
    command, stops after 60 seconds, waits for updated visual feedback, and
    stops if a step fails to move the person meaningfully toward the center.
    """

    def __init__(self, motor: TiMotor, source: str, model_path: str,
                 *, vertical: bool = False, max_steps: int = 4):
        self.motor = motor
        self.source = source
        self.model_path = model_path
        self.vertical = vertical
        self.max_steps = max(1, min(int(max_steps), 8))
        self._on = threading.Event()
        self._shutdown = threading.Event()
        self._until: float | None = None
        self._thread: threading.Thread | None = None
        self._session_id = 0

    def enable(self, *, seconds: float | None = None) -> tuple[bool, str]:
        if not self.motor.enabled:
            return False, "Motor arayüzü etkin değil. Takip modunu henüz açamam."
        try:
            import cv2  # noqa: F401
            from ultralytics import YOLO  # noqa: F401
        except ImportError:
            return False, "Görüntü takibi için OpenCV ve Ultralytics gerekiyor."
        self._session_id += 1
        self._until = time.monotonic() + min(float(seconds or 60), 60.0)
        self._on.set()
        if self._thread is None or not self._thread.is_alive():
            self._shutdown.clear()
            self._thread = threading.Thread(target=self._loop, name="ti-visual-follower", daemon=True)
            self._thread.start()
        axes = "yatay ve dikey" if self.vertical else "yalnızca yatay"
        return True, (f"Görüntüdeki tek kişiyi {axes} takip etmeyi deneyeceğim. "
                      f"Güvenlik için en fazla {self.max_steps} adım hareket edeceğim. "
                      "Kamera dışındaki kişileri bulamam.")

    def disable(self):
        self._on.clear()
        self._until = None
        self._session_id += 1

    def close(self):
        self.disable()
        self._shutdown.set()

    @staticmethod
    def direction_for_offset(x: float, y: float, *, vertical: bool = False) -> str | None:
        # Deadzone avoids oscillation from tiny detection differences.
        if abs(x) >= 0.21:
            return "right" if x > 0 else "left"
        if vertical and abs(y) >= 0.24:
            return "down" if y > 0 else "up"
        return None

    def _loop(self):
        cap = None
        try:
            import cv2
            from ultralytics import YOLO
            detector = YOLO(self.model_path)
            session_id = -1
            steps = 0
            previous_direction = None
            stable_count = 0
            pending_check = None  # (axis, error_before, move_time)
            while not self._shutdown.is_set():
                if not self._on.is_set():
                    if cap is not None:
                        cap.release()
                        cap = None
                    time.sleep(0.25)
                    continue
                if session_id != self._session_id:
                    session_id = self._session_id
                    steps = 0
                    previous_direction = None
                    stable_count = 0
                    pending_check = None
                    print("[Ti/Takip] Yeni takip oturumu. Yatay takip varsayilan; hareket limiti etkin.", flush=True)
                if self._until is None or time.monotonic() > self._until:
                    print("[Ti/Takip] Sure siniri: otomatik takip durduruldu.", flush=True)
                    self.disable()
                    continue
                if cap is None or not cap.isOpened():
                    if cap is not None:
                        cap.release()
                    cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if not cap.isOpened():
                        print("[Ti/Takip] Goruntu kaynagina baglanilamadi; takip kapatildi.", flush=True)
                        self.disable()
                        continue
                ok, frame = cap.read()
                if not ok:
                    cap.release()
                    cap = None
                    time.sleep(0.5)
                    continue
                results = detector.predict(frame, classes=[0], conf=0.5,
                                           imgsz=416, verbose=False)
                if not results or results[0].boxes is None or len(results[0].boxes) != 1:
                    stable_count = 0
                    previous_direction = None
                    time.sleep(0.35)
                    continue
                box = results[0].boxes.xyxy[0].tolist()
                h, w = frame.shape[:2]
                if w <= 0 or h <= 0:
                    continue
                x = ((box[0] + box[2]) / 2 / w) - 0.5
                y = ((box[1] + box[3]) / 2 / h) - 0.5
                now = time.monotonic()

                # Do not judge a motion until the motor AND video stream have settled.
                if pending_check is not None:
                    axis, before, moved_at = pending_check
                    if now - moved_at < 5.0:
                        time.sleep(0.35)
                        continue
                    after = x if axis == "x" else y
                    # If the signed offset did not shrink by >= 2% of frame,
                    # camera could be reversed, at a physical limit, or showing
                    # buffered frames. Stop rather than repeatedly drive motor.
                    if abs(after) > 0.10 and abs(after) >= abs(before) - 0.02:
                        print("[Ti/Takip] Hedef merkeze yaklasmadi; tekrar motor komutu gondermiyorum.", flush=True)
                        self.disable()
                        continue
                    pending_check = None
                    stable_count = 0
                    previous_direction = None

                direction = self.direction_for_offset(x, y, vertical=self.vertical)
                if direction is None:
                    stable_count = 0
                    previous_direction = None
                    time.sleep(0.45)
                    continue
                if direction == previous_direction:
                    stable_count += 1
                else:
                    previous_direction = direction
                    stable_count = 1
                if stable_count < 2:
                    time.sleep(0.45)
                    continue
                if steps >= self.max_steps:
                    print("[Ti/Takip] Motor adim sinirina ulasildi; takip kapatildi.", flush=True)
                    self.disable()
                    continue
                if not self._on.is_set() or session_id != self._session_id:
                    continue
                ok_move, message = self.motor.move(direction)
                if not ok_move:
                    # Rate-limit message can occur after manual movement;
                    # it isn't an error worth shutting down for.
                    if "bekleme süresi" not in message:
                        print("[Ti/Takip] Motor hareketi basarisiz; takip kapatildi:", message, flush=True)
                        self.disable()
                    else:
                        time.sleep(0.8)
                    continue
                steps += 1
                axis = "x" if direction in ("left", "right") else "y"
                pending_check = (axis, x if axis == "x" else y, time.monotonic())
                print(f"[Ti/Takip] Hareket {steps}/{self.max_steps}: {direction}; goruntude duzelme kontrol edilecek.", flush=True)
                time.sleep(0.5)
        except Exception as exc:
            self.disable()
            print("[Ti/Takip] Hata; takip kapatildi:", exc, flush=True)
        finally:
            if cap is not None:
                cap.release()


class TiAssistant:
    def __init__(self, *, model_name: str = "base", stream: str = STREAM,
                 threshold: float = 220, awake_seconds: float = 27.0,
                 silence_ms: int = 1000, enable_motor: bool = False,
                 tracker_source: str = "rtsp://127.0.0.1:8554/c301_h264_hw",
                 tracker_model: str = "yolo11n.pt",
                 follow_vertical: bool = False, follow_max_steps: int = 4):
        self.motor = TiMotor(enabled=enable_motor, stream=stream)
        self.follower = TiPersonFollower(self.motor, tracker_source, tracker_model,
                                         vertical=follow_vertical, max_steps=follow_max_steps)
        self.model_name = model_name
        self.stream = stream
        self.threshold = threshold
        self.awake_seconds = awake_seconds
        self.silence_ms = silence_ms
        self.stop_event = threading.Event()
        self.microphone_enabled = threading.Event()
        self.microphone_enabled.set()
        self.voice_enabled = threading.Event()
        self.voice_enabled.set()
        self.visual_detection_enabled = threading.Event()
        self.visual_detection_enabled.set()
        self.on_transcript = None
        self.on_response = None
        self.command_handler = None  # optional non-camera command router
        self.speaker_busy = threading.Event()
        self.state_lock = threading.Lock()
        self.mute_until = 0.0
        self.awake_until = 0.0   # Yalnizca 'Ti' tek basina denince sonraki komut icin.
        self.session_active = False  # Ilk 'Merhaba Ti' denene kadar pasif.
        self.followup_pending = False
        self.utterances: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self.responses: queue.Queue[str] = queue.Queue(maxsize=2)
        self.model = None
        self.speaker = None
        self._ffmpeg: subprocess.Popen | None = None

    def _answer(self, command: str) -> str:
        if callable(self.command_handler):
            handled = self.command_handler(command)
            if handled is not None:
                return handled
        intent = movement_intent(command)
        if intent is None:
            return answer_command(command)
        kind, direction = intent
        if kind == "move":
            self.follower.disable()  # manual command overrides automatic follow
            success, msg = self.motor.move(direction)
            return msg
        if kind == "motor_stop":
            self.follower.disable()
            return "Otomatik takip durduruldu. Motor komutları tek adımlı gönderiliyor."
        if kind == "follow_off":
            self.follower.disable()
            return "Görüntüden kişi takibi kapatıldı."
        if kind == "follow_on":
            if not self.visual_detection_enabled.is_set():
                return "Nesne algilama kapali. Kontrol merkezinden acabilirsin."
            success, msg = self.follower.enable()
            return msg
        if kind == "center_person":
            if not self.visual_detection_enabled.is_set():
                return "Nesne algilama kapali. Kontrol merkezinden acabilirsin."
            success, msg = self.follower.enable(seconds=12.0)
            return msg
        if kind == "voice_direction":
            return ("C301 ses akışından yön bilgisi gelmiyor. "
                    "Görüntüdeki tek kişiyi takip etmemi istersen Ti beni takip et de.")
        return answer_command(command)

    def _playback_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                sentence = self.responses.get(timeout=0.3)
            except queue.Empty:
                continue
            self.speaker_busy.set()
            try:
                print("[Ti] Yanit:", sentence, flush=True)
                assert self.speaker is not None
                if self.voice_enabled.is_set():
                    self.speaker.say(sentence)
            except Exception as exc:
                print("[Ti] Hoparlor hatasi:", exc, flush=True)
            finally:
                with self.state_lock:
                    self.mute_until = time.monotonic() + 1.2
                    # Yalnizca "Merhaba Ti" veya tek basina "Ti" cevabi
                    # bittikten sonra bir kez Ti demeden soru sorma hakki ver.
                    if self.session_active and self.followup_pending:
                        self.awake_until = time.monotonic() + self.awake_seconds
                        self.followup_pending = False
                self.speaker_busy.clear()
                self.responses.task_done()

    def _respond(self, sentence: str) -> None:
        if not self.voice_enabled.is_set():
            return
        if callable(self.on_response):
            try:
                self.on_response(sentence)
            except Exception:
                pass
        try:
            self.responses.put_nowait(sentence)
        except queue.Full:
            print("[Ti] Bir yanit hala oynatiliyor; yeni yanit atlandi.")

    def _transcribe_loop(self) -> None:
        import numpy as np
        assert self.model is not None
        while not self.stop_event.is_set():
            try:
                data = self.utterances.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                audio = np.frombuffer(data, dtype="<i2").astype("float32") / 32768.0
                segments, _ = self.model.transcribe(
                    audio, language="tr", beam_size=3, vad_filter=False,
                    condition_on_previous_text=False,
                    initial_prompt=("Türkçe sesli asistan Ti. Merhaba Ti. "
                                    "Ti sistem durumu ne? Ti nasılsın? Ti saat kaç? "
                                    "Ti bugün tarih ne? Ti adın ne?"),
                )
                words = " ".join(s.text.strip() for s in segments).strip()
                if not words:
                    continue
                print("[Mikrofon]", words, "| Normal:", normalize(words), flush=True)
                if callable(self.on_transcript):
                    try:
                        self.on_transcript(words)
                    except Exception:
                        pass
                with self.state_lock:
                    now = time.monotonic()
                    kind, command = interpret_utterance(
                        words, active=self.session_active,
                        followup=now < self.awake_until,
                    )
                    if kind == "wake":
                        self.session_active = True
                        self.followup_pending = not command
                        self.awake_until = 0.0
                    elif kind == "prompt":
                        self.followup_pending = True
                        self.awake_until = 0.0
                    elif kind in ("command", "followup"):
                        self.followup_pending = False
                        self.awake_until = 0.0
                    if kind in ("wake", "command", "followup") and is_sleep_command(command):
                        self.session_active = False
                        self.follower.disable()  # sleep must also stop auto-tracking
                        self.followup_pending = False
                        self.awake_until = 0.0
                if kind == "ignore":
                    print("[Ti] Beklemede: ilk acilis 'Merhaba Ti', sonra 'Ti <komut>'.", flush=True)
                elif kind == "prompt":
                    print("[Ti] Ti tek basina algilandi. Siradaki sorunu bekliyorum.", flush=True)
                    self._respond("Efendim? Seni dinliyorum.")
                else:
                    print(f"[Ti] Mod: {kind} | Anlasilan komut: {command or '(selamlama)'}", flush=True)
                    self._respond(self._answer(command))
            except Exception as exc:
                print("[Ti] Konusma tanima hatasi:", exc, flush=True)
            finally:
                self.utterances.task_done()

    def _read_microphone(self) -> None:
        threshold = self.threshold
        gate = UtteranceGate(threshold=threshold, silence_ms=self.silence_ms)
        for attempt in range(1, 5):
            if self.stop_event.is_set():
                break
            cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-rtsp_transport", "tcp", "-i", f"{RTSP}/{self.stream}",
                   "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
                   "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"]
            with tempfile.TemporaryFile(mode="w+b") as errors:
                try:
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors,
                                            stdin=subprocess.DEVNULL, bufsize=0,
                                            creationflags=WIN_NO_WINDOW)
                except FileNotFoundError:
                    print("[Ti] FFmpeg bulunamadi. ffmpeg -version komutunu dene.")
                    return
                self._ffmpeg = proc
                gate.reset()
                print(f"[Ti] C301 mikrofonuna baglaniliyor (deneme {attempt}/4)...", flush=True)
                assert proc.stdout is not None
                while not self.stop_event.is_set():
                    frame = read_exact(proc.stdout, FRAME_BYTES)
                    if not frame or len(frame) != FRAME_BYTES:
                        break
                    with self.state_lock:
                        blocked = time.monotonic() < self.mute_until
                    if not self.microphone_enabled.is_set() or self.speaker_busy.is_set() or blocked:
                        gate.reset()  # Hoparlorun kendi sesini tekrar dinleme
                        continue
                    utterance = gate.feed(frame)
                    if utterance:
                        try:
                            self.utterances.put_nowait(utterance)
                            print(f"[Ti] Cumle algilandi ({len(utterance)/SAMPLE_RATE/2:.1f} saniye), cozumleniyor...", flush=True)
                        except queue.Full:
                            print("[Ti] Islem yogun, bir cumle atlandi.", flush=True)
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=3)
                errors.seek(0)
                err_text = errors.read().decode("utf-8", "replace").strip()
                if err_text and not self.stop_event.is_set():
                    print("[Ti] FFmpeg:", err_text[-600:], flush=True)
            if not self.stop_event.is_set():
                print("[Ti] Mikrofon baglantisi kesildi; yeniden denenecek.", flush=True)
                time.sleep(2)

    def start(self) -> None:
        from faster_whisper import WhisperModel
        from camera_speaker import C301Speaker
        print("[Ti] Turkce konusma modeli yukleniyor. Ilk calistirmada internet gerekir...", flush=True)
        self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=4)
        print("[Ti] Model hazir.", flush=True)
        self.speaker = C301Speaker()
        try:
            talker = threading.Thread(target=self._playback_loop, daemon=True)
            recognizer = threading.Thread(target=self._transcribe_loop, daemon=True)
            talker.start()
            recognizer.start()
            print(f"[Ti] Baslangic: 'Merhaba Ti' | Sonra: 'Ti <komut>' | Enerji esigi: {self.threshold}", flush=True)
            self._read_microphone()
        finally:
            self.stop_event.set()
            self.follower.close()
            if self._ffmpeg and self._ffmpeg.poll() is None:
                self._ffmpeg.terminate()
            self.speaker.close()
            print("[Ti] Durduruldu.", flush=True)


def check_stream(stream: str) -> None:
    try:
        with urllib.request.urlopen(f"{GO2RTC}/api/streams", timeout=4) as res:
            streams = json.load(res)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise RuntimeError("go2rtc kapali veya API 1984 erisilemiyor.") from exc
    if stream not in streams:
        raise RuntimeError(f"go2rtc'de '{stream}' bulunamadi. Ses test akisinin mevcut oldugunu kontrol et.")


def microphone_test(stream: str, seconds: int) -> None:
    check_stream(stream)
    out = ROOT / "ti_mikrofon_test.wav"
    cmd = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
           "-rtsp_transport", "tcp", "-i", f"{RTSP}/{stream}", "-map", "0:a:0",
           "-vn", "-t", str(seconds), "-ar", str(SAMPLE_RATE), "-ac", "1",
           "-c:a", "pcm_s16le", str(out)]
    print(f"[Ti] {seconds} saniyelik mikrofon testi. Kameraya 'Merhaba Ti' de.", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=seconds + 35,
                            creationflags=WIN_NO_WINDOW)
    if result.returncode or not out.is_file() or out.stat().st_size < 10000:
        raise RuntimeError("Mikrofondan ses alinamadi. " + result.stderr[-800:])
    print("[Ti] Kamera mikrofon testi kaydedildi:", out)
    # Calculate the loudest 250 ms chunk to assist sensitivity tuning.
    with wave.open(str(out), "rb") as wav:
        values = []
        while True:
            block = wav.readframes(4000)
            if not block:
                break
            values.append(rms(block))
    if values:
        print(f"[Ti] Mikrofon ses seviyesi: tepe RMS {max(values):.0f}; "
              "varsayilan esik 220 (ortama gore ayarla).")
    print("[Ti] WAV dosyasini dinle. Ses netse asistan moduna gecebilirsin.")
    print("[Ti] Testi dinledikten sonra WAV dosyasini silebilirsin.")


def diagnose_recording(model_name: str) -> None:
    """Speech-to-text from recorded WAV, bypassing live sentence detector.

    A good test for separating poor mic audio from over-aggressive VAD.
    """
    import numpy as np
    from faster_whisper import WhisperModel
    wav_path = ROOT / "ti_mikrofon_test.wav"
    with wave.open(str(wav_path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
    if sample_rate != SAMPLE_RATE or channels != 1:
        raise RuntimeError(f"Beklenmeyen WAV formati: {sample_rate} Hz, {channels} kanal")
    audio = np.frombuffer(frames, dtype="<i2").astype("float32") / 32768.0
    clip_percent = float(np.mean(np.abs(audio) >= 0.98) * 100)
    total_rms = float(np.sqrt(np.mean(audio ** 2))) * 32768.0
    print(f"[Ti/Teshis] Kayit {len(audio)/SAMPLE_RATE:.1f} sn, ortalama RMS {total_rms:.0f}, "
          f"kirpilma {clip_percent:.2f}%.", flush=True)
    print("[Ti/Teshis] WAV dosyasini Windows ile dinle. Sesin netligini RMS degerinden anlayamayiz.", flush=True)
    print(f"[Ti/Teshis] '{model_name}' modeliyle tam kayit cozumleniyor...", flush=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4)
    segments, _ = model.transcribe(audio, language="tr", beam_size=5,
                                   vad_filter=False, condition_on_previous_text=False,
                                   initial_prompt="Merhaba Ti. Sistem durumu nedir? Saat kaç?")
    recognized = " ".join(x.text.strip() for x in segments).strip()
    print("[Ti/Teshis] Duyulan metin:", recognized if recognized else "(Bos; komut anlasilamadi)", flush=True)
    print("[Ti/Teshis] Dosya:", wav_path, flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Ti v0.6: Merhaba Ti, sonra Ti <komut> sesli asistan")
    p.add_argument("--stream", default=STREAM, help="go2rtc ses akisi ismi")
    p.add_argument("--model", default="small", help="Whisper modeli: tiny/base/small (varsayilan: small)")
    p.add_argument("--threshold", type=float, default=220,
                   help="Mikrofon ses algilama esigi (varsayilan: 220)")
    p.add_argument("--awake-seconds", type=float, default=27.0,
                   help="Tek basina Ti denildikten sonra yanit suresi (varsayilan 27 saniye)")
    p.add_argument("--silence-ms", type=int, default=1000,
                   help="Cumleyi bitiren sessizlik, milisaniye (varsayilan: 1000)")
    p.add_argument("--diagnose", type=int, metavar="SANIYE",
                   help="Mikrofondan WAV kaydet ve taninabilen kelimeleri yazdir")
    p.add_argument("--mic-test", type=int, metavar="SANIYE", help="Ses kaydet, asistani baslatma")
    p.add_argument("--enable-motor", action="store_true",
                   help="DENEYSEL yerel PTZ arayuzu uzerinden tek adimlik fiziksel hareket")
    p.add_argument("--tracker-source", default="rtsp://127.0.0.1:8554/c301_h264_hw",
                   help="YOLO kisiyi takip icin video URL")
    p.add_argument("--tracker-model", default="yolo11n.pt",
                   help="YOLO kisi bulma modeli")
    p.add_argument("--follow-vertical", action="store_true",
                   help="DENEYSEL: otomatik takipte yukari/asagi harekete de izin ver")
    p.add_argument("--follow-max-steps", type=int, default=4,
                   help="Her takip komutunda en fazla motor adimi: 1-8 (varsayilan: 4)")
    args = p.parse_args()
    try:
        if args.diagnose is not None:
            microphone_test(args.stream, max(5, min(args.diagnose, 25)))
            diagnose_recording(args.model)
        elif args.mic_test is not None:
            microphone_test(args.stream, max(3, min(args.mic_test, 20)))
        else:
            check_stream(args.stream)
            TiAssistant(stream=args.stream, model_name=args.model,
                        threshold=args.threshold,
                        awake_seconds=max(5.0, min(120.0, args.awake_seconds)),
                        silence_ms=max(450, min(2200, args.silence_ms)),
                        enable_motor=args.enable_motor,
                        tracker_source=args.tracker_source,
                        tracker_model=args.tracker_model,
                        follow_vertical=args.follow_vertical,
                        follow_max_steps=args.follow_max_steps).start()
    except KeyboardInterrupt:
        print("\n[Ti] Klavyeden durduruldu.")
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print("[Ti] Hata:", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
