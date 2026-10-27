"""TI - Xiaomi C301 sesli asistan v0.2: Turkce saat komutu iyilestirmesi.

Uyandirma: "Merhaba Ti". Ses kameranin mikrofonundan RTSP/go2rtc ile alinir;
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


WAKE_PATTERN = re.compile(r"(?:^|\s)(?:merhaba|hey|selam)\s+(?:ti|t\s+i|tii|t)(?=\s|$)")


def wake_remainder(text: str) -> str | None:
    """None: uyandirma yok; bos metin: yalnizca 'Merhaba Ti'."""
    cleaned = normalize(text)
    match = WAKE_PATTERN.search(cleaned)
    if not match:
        return None
    return cleaned[match.end():].strip()


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

    def __init__(self, threshold: float = 350, silence_ms: int = 720,
                 min_speech_ms: int = 300, max_speech_seconds: float = 9):
        self.threshold = threshold
        self.silence_frames = max(1, silence_ms // FRAME_MS)
        self.min_frames = max(1, min_speech_ms // FRAME_MS)
        self.max_frames = max(1, int(max_speech_seconds * 1000 / FRAME_MS))
        self.preroll = collections.deque(maxlen=12)
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
            if self.start_streak >= 3:
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
    if any(x in c for x in ("adin ne", "sen kimsin", "kendini tanit")):
        return "Ben Ti. Xiaomi C301 güvenlik asistanıyım. Seni duyabilir ve kameradan cevap verebilirim."
    if any(x in c for x in ("sistem durumu", "durumun nasil", "calisiyor musun", "ses testi")):
        return "Ti sesli asistan sistemi aktif. Mikrofon üzerinden dinliyorum, kameranın hoparlöründen yanıt veriyorum."
    if any(x in c for x in ("yardim", "neler yapabilirsin", "ne yapabilirsin")):
        return "Bana saati, tarihi, adımı veya sistem durumunu sorabilirsin."
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


class TiAssistant:
    def __init__(self, *, model_name: str = "base", stream: str = STREAM,
                 threshold: float = 350, awake_seconds: float = 22.0):
        self.model_name = model_name
        self.stream = stream
        self.threshold = threshold
        self.awake_seconds = awake_seconds
        self.stop_event = threading.Event()
        self.speaker_busy = threading.Event()
        self.state_lock = threading.Lock()
        self.mute_until = 0.0
        self.awake_until = 0.0
        self.utterances: queue.Queue[bytes] = queue.Queue(maxsize=2)
        self.responses: queue.Queue[str] = queue.Queue(maxsize=2)
        self.model = None
        self.speaker = None
        self._ffmpeg: subprocess.Popen | None = None

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
                self.speaker.say(sentence)
            except Exception as exc:
                print("[Ti] Hoparlor hatasi:", exc, flush=True)
            finally:
                with self.state_lock:
                    self.mute_until = time.monotonic() + 1.2
                    # Ti yanit verirken kullanicinin konusmasini dinlemiyoruz.
                    # Yanit bittiginde uyandirilmissa komut suresini yenile.
                    if self.awake_until > 0 and sentence != "Tamam, tekrar Merhaba Ti dediğinde buradayım.":
                        self.awake_until = time.monotonic() + self.awake_seconds
                self.speaker_busy.clear()
                self.responses.task_done()

    def _respond(self, sentence: str) -> None:
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
                    initial_prompt="Türkçe konuşma. Asistanın adı Ti. Merhaba Ti. Saat kaç? Saat kaç oldu? Bugün tarih ne?",
                )
                words = " ".join(s.text.strip() for s in segments).strip()
                if not words:
                    continue
                print("[Mikrofon]", words, "| Komut:", normalize(words), flush=True)
                rest = wake_remainder(words)
                now = time.monotonic()
                if rest is not None:
                    self.awake_until = now + self.awake_seconds
                    self._respond(answer_command(rest))
                elif now < self.awake_until:
                    command = normalize(words)
                    self.awake_until = now + self.awake_seconds
                    self._respond(answer_command(command))
                    if any(x in command for x in ("uykuya gec", "iyi geceler", "gorusuruz")):
                        self.awake_until = 0
                else:
                    print("[Ti] Uyandirma suresi dolmus. 'Merhaba Ti' de veya 'Merhaba Ti, saat kac' diye tek cumlede sor.", flush=True)
            except Exception as exc:
                print("[Ti] Konusma tanima hatasi:", exc, flush=True)
            finally:
                self.utterances.task_done()

    def _read_microphone(self) -> None:
        threshold = self.threshold
        gate = UtteranceGate(threshold=threshold)
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
                    if self.speaker_busy.is_set() or blocked:
                        gate.reset()  # Hoparlorun kendi sesini tekrar dinleme
                        continue
                    utterance = gate.feed(frame)
                    if utterance:
                        try:
                            self.utterances.put_nowait(utterance)
                            print("[Ti] Cumle algilandi, cozumleniyor...", flush=True)
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
            print(f"[Ti] Dinliyorum: 'Merhaba Ti' | Enerji esigi: {self.threshold}", flush=True)
            self._read_microphone()
        finally:
            self.stop_event.set()
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
              "varsayilan esik 350 (ortama gore ayarla).")
    print("[Ti] WAV dosyasini dinle. Ses netse asistan moduna gecebilirsin.")
    print("[Ti] Testi dinledikten sonra WAV dosyasini silebilirsin.")


def main() -> None:
    p = argparse.ArgumentParser(description="Ti: Xiaomi C301 kameradan Turkce sesli asistan")
    p.add_argument("--stream", default=STREAM, help="go2rtc ses akisi ismi")
    p.add_argument("--model", default="base", help="Whisper modeli: tiny/base/small")
    p.add_argument("--threshold", type=float, default=350,
                   help="Mikrofon ses algilama esigi (varsayilan: 350)")
    p.add_argument("--mic-test", type=int, metavar="SANIYE", help="Ses kaydet, asistani baslatma")
    args = p.parse_args()
    try:
        if args.mic_test is not None:
            microphone_test(args.stream, max(3, min(args.mic_test, 20)))
        else:
            check_stream(args.stream)
            TiAssistant(stream=args.stream, model_name=args.model,
                        threshold=args.threshold).start()
    except KeyboardInterrupt:
        print("\n[Ti] Klavyeden durduruldu.")
    except (RuntimeError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print("[Ti] Hata:", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
