"""Use C301 camera speaker for the existing person alert; no YOLO changes."""
from camera_speaker import C301Speaker


class C301CameraVoice:
    def __init__(self):
        self._speaker = C301Speaker()

    def say(self, message: str):
        # Nonblocking, rate-limited. One alert per person event at most per minute.
        return self._speaker.notify("person", message, cooldown=60.0)

    def person_entered(self, message: str):
        # Giris mantigi Worker'da; sesi tekrar yollamayi engelle.
        return self._speaker.notify("person-presence", message, cooldown=1.0)

    def close(self):
        self._speaker.close()
