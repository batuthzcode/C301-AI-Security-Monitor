"""Windows PC microphone and speaker adapters (not the Xiaomi camera)."""
from __future__ import annotations


def transcribe_once(seconds: float = 5, model_name: str = "tiny") -> str:
    """Capture only after explicit user command; transcribe locally in RAM."""
    import sounddevice as sd
    from faster_whisper import WhisperModel
    if not 2 <= seconds <= 15:
        raise ValueError("Kayıt süresi 2-15 saniye arasında olmalı.")
    print("Yerel Türkçe konuşma modeli hazırlanıyor (ilk kullanımda indirilir)...", flush=True)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    print(f"🎙️ {seconds:g} saniye dinliyorum, konuşabilirsin...")
    samples = sd.rec(int(16000 * seconds), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    segments, _ = model.transcribe(samples.reshape(-1), language="tr", beam_size=3,
                                   vad_filter=True, condition_on_previous_text=False)
    return " ".join(segment.text.strip() for segment in segments).strip()


def say(text: str) -> bool:
    """Return False if Windows TTS is unavailable; never send voice to network."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        # Prefer an already-installed Turkish Windows voice, if available.
        try:
            for voice in engine.getProperty("voices") or []:
                langs = " ".join(str(a) for a in (getattr(voice,"languages",[]) or [])).lower()
                if "turkish" in voice.name.lower() or "tr-tr" in langs or "tr_tr" in langs:
                    engine.setProperty("voice", voice.id)
                    break
        except Exception:
            pass
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        return True
    except Exception:
        return False
