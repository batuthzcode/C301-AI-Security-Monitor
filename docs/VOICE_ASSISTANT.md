# Milestone 022 — Turkish voice/weather assistant, optional companion (v0.2.0 preview)

**Date:** 2026-10-26

## What this proves

- Separate Windows-PC voice assistant entry point, `voice_assistant.py`, that can run *alongside* camera monitoring without modifying its source video pipeline or Xiaomi firmware.
- Turkish voice command recognition using a **locally run** `faster-whisper` multilingual model (`tiny`/CPU/int8 by default). The model downloads on first use.
- Turkish responses through Windows speech synthesis (`pyttsx3`) when a voice engine exists. A Turkish Windows voice may need to be installed for correct pronunciation.
- Current weather for a chosen city using **Open-Meteo**. The app sends the **city name/coordinates only** (not recorded audio) to a public weather endpoint. Requires internet and compliance with provider usage terms.
- Simple local commands: "Saat kaç?" and "Merhaba". Questions about camera events are explicitly **not implemented yet**.
- Microphone recording happens only after a manual `--listen` action, in memory. No raw audio file or transcript history is persisted by the app.

## Installation on Windows

Keep the existing go2rtc and C301 monitor setup unchanged. Copy these new files into the existing project after taking a ZIP backup, preserving relative locations:

- `voice_assistant.py`
- `requirements-voice.txt`
- `c301_monitor/assistant_core.py`
- `c301_monitor/assistant_audio.py`

Copy these **four** new files only; do not overwrite the working `main.py`,
`gui.py`, `worker.py`, `.venv`, or private `go2rtc.yaml`.

Then open PowerShell in the same project folder where `.venv` is installed:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-voice.txt
```

Test text-first (no microphone and no speaking):

```powershell
.\.venv\Scripts\python.exe voice_assistant.py --text "Ankara hava nasıl?" --city Ankara --mute
```

If successful, test PC speaker output:

```powershell
.\.venv\Scripts\python.exe voice_assistant.py --text "Hava nasıl?" --city Ankara
```

Then test microphone, once per invocation:

```powershell
.\.venv\Scripts\python.exe voice_assistant.py --listen --city Ankara
```

Say "Hava nasıl?" within the default 5-second listening window. This is **push-to-talk** via a CLI action, not continuous microphone monitoring or a wake-word assistant. Run the camera UI in another terminal if desired; additional CPU usage may increase video delay. Prefer `--model tiny` while performance is unknown.

Switch city explicitly:

```powershell
.\.venv\Scripts\python.exe voice_assistant.py --listen --city Istanbul --seconds 6
```

## Privacy and scope

- Camera source `xiaomi://` token, Xiaomi login information, and go2rtc YAML are **not accessed** by this companion.
- Voice input is processed locally, but the speech model is downloaded from the internet on first use; weather questions send the selected city to Open-Meteo over HTTPS.
- Microphone access depends on Windows Privacy > Microphone permissions and the selected audio input device.
- The voice response is played from the **computer speaker**, not the C301 built-in speaker. Two-way camera audio requires separate testing; `audio=0` on the current stream specifically disables upstream audio extraction.
- No general-purpose conversational model is included. Weather/time/greeting are deterministic commands with AI speech-to-text. Camera event querying, wake-word recognition, GUI microphone button, PC voice choice, camera speaker playback and free-form chat are future work.

## Tests and current limitations

Tests mock weather HTTP responses so no live weather values are fabricated. Real microphone, Turkish TTS, and Open-Meteo connectivity cannot be validated from the build environment; verify on the user's Windows system. Existing video latency is still ~2 seconds in FFplay; no live performance improvement claimed.

## References

- https://github.com/SYSTRAN/faster-whisper
- https://open-meteo.com/en/docs
- https://go2rtc.org/internal/xiaomi/
