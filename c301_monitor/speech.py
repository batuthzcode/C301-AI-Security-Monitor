"""Optional, local PC-speaker voice alerts (NOT camera speaker control)."""
import queue
import threading


class PCSpeaker:
    def __init__(self):
        self._messages: queue.Queue[str | None] = queue.Queue(maxsize=2)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def say(self, message: str):
        try:
            self._messages.put_nowait(message)
        except queue.Full:
            pass

    def close(self):
        try:
            self._messages.put_nowait(None)
        except queue.Full:
            pass

    def _run(self):
        engine = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
        except Exception:
            pass
        while True:
            item = self._messages.get()
            if item is None:
                break
            try:
                if engine is not None:
                    engine.say(item)
                    engine.runAndWait()
                else:
                    import winsound
                    winsound.MessageBeep()
            except Exception:
                pass
