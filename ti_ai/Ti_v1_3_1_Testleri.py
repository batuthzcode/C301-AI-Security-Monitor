"""Additional camera-free tests for v1.3.1 stop/start and visible-launch safeguards."""
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
import ti_services
import ti_lowlatency

ROOT=Path(__file__).resolve().parent


class TestQuickStop(unittest.TestCase):
    def test_slow_capture_release_does_not_block_caller_and_restart_works(self):
        frame=np.zeros((480,848,3),dtype=np.uint8)
        class SlowCapture:
            def __init__(self,source):self.closed=False
            def isOpened(self):return not self.closed
            def read(self):
                time.sleep(.035)
                return (False,None) if self.closed else (True,frame)
            def release(self):
                time.sleep(.7)  # Simulate a slow FFmpeg cleanup on Windows.
                self.closed=True
        settings=dict(ti_services.DEFAULTS)
        settings.update(preview=True,detection=False)
        events=[];worker=ti_services.VideoWorker(settings,lambda k,v=None:events.append((k,v)))
        with patch.object(ti_lowlatency,'LatestFFmpegCapture',SlowCapture):
            worker.start()
            time.sleep(.15)
            start=time.monotonic()
            worker.stop()
            self.assertLess(time.monotonic()-start,.35,'GUI must not wait for FFmpeg cleanup')
            worker.start()  # Immediately reenable: request must survive slow cleanup.
            deadline=time.monotonic()+3
            while time.monotonic()<deadline and len([x for x in events if x[0]=='frame'])<5:
                time.sleep(.04)
            self.assertGreaterEqual(len([x for x in events if x[0]=='frame']),5)
            worker.stop()
            if worker.thread:worker.thread.join(timeout=2)

    def test_launcher_does_not_use_invisible_pythonw(self):
        cmd=(ROOT/'Ti_Baslat.cmd').read_text(encoding='utf-8')
        self.assertIn('Ti_Guvenli_Baslat.py',cmd)
        self.assertNotIn('pythonw.exe',cmd)
        self.assertIn('pause',cmd)
        launcher=(ROOT/'Ti_Guvenli_Baslat.py').read_text(encoding='utf-8')
        self.assertIn('ti_baslatma_hata.log',launcher)


if __name__=='__main__':unittest.main(verbosity=2)
