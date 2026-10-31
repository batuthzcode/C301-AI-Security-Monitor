"""Performance regression tests; uses a mock YOLO subprocess, never the real camera."""
import ast
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from ti_detector_async import AsyncDetector
import ti_services

HERE=Path(__file__).resolve().parent

class TestAsyncYOLO(unittest.TestCase):
    def test_inference_does_not_block_camera_thread_and_skips_stale_frames(self):
        det=AsyncDetector('yolo11n.pt',interval=.3,mock=True)
        try:
            deadline=time.monotonic()+8
            while time.monotonic()<deadline and not det.ready:
                for typ,val in det.poll():
                    if typ=='error':self.fail(val)
                time.sleep(.05)
            self.assertTrue(det.ready,'mock subprocess could not start')
            frame=np.zeros((480,848,3),dtype=np.uint8)
            st=time.monotonic()
            self.assertTrue(det.submit(frame,mock_delay=1.1))
            self.assertLess(time.monotonic()-st,.15,'submit must be nonblocking')
            self.assertFalse(det.submit(frame),'only one prediction in flight')
            got=None
            deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                for typ,val in det.poll():
                    if typ=='result':got=val
                    elif typ=='error':self.fail(val)
                if got is not None:break
                time.sleep(.05)
            self.assertIsNotNone(got,'mock inference result missing')
            self.assertEqual(got[0][1],'person')
            self.assertTrue(det.submit(frame,mock_delay=.05))
        finally:det.stop()
        self.assertIsNotNone(det.process.poll(),'child process must be closed')

    def test_live_video_keeps_up_during_slow_detection(self):
        import cv2
        import threading
        import ti_lowlatency
        import ti_detector_async
        events=[]
        frame=np.zeros((480,848,3),dtype=np.uint8)
        class FakeCapture:
            def __init__(self,source):self.closed=False
            def isOpened(self):return not self.closed
            def read(self):
                if self.closed:return False,None
                time.sleep(.045)
                return True,frame
            def release(self):self.closed=True
        class SlowDetector(AsyncDetector):
            def __init__(self,model,interval):
                super().__init__(model,interval=interval,mock=True)
            def submit(self,*args,**kwargs):
                return super().submit(*args,mock_delay=1.3,**kwargs)
        settings=dict(ti_services.DEFAULTS)
        settings.update(preview=True,detection=True,sharpen=0)
        video=ti_services.VideoWorker(settings,lambda kind, val=None:events.append((kind,val)))
        with patch.object(ti_lowlatency,'LatestFFmpegCapture',FakeCapture), patch.object(ti_detector_async,'AsyncDetector',SlowDetector):
            video.start()
            try:
                time.sleep(2.5)
                frames=[item for item in events if item[0]=='frame']
                self.assertGreaterEqual(len(frames),7,
                    'video should remain live while detection is busy')
                self.assertTrue(any(kind=='detection_loading' for kind,_ in events))
            finally:video.stop()
        self.assertFalse(video.thread.is_alive() if video.thread else True)

    def test_empty_detection_does_not_start_worker(self):
        worker=ti_services.VideoWorker(dict(ti_services.DEFAULTS),lambda *a:None)
        self.assertFalse(worker.settings['detection'])
        self.assertFalse(worker.yolo_ready)

    def test_camera_loop_no_direct_yolo_import_predict(self):
        src=(HERE/'ti_services.py').read_text(encoding='utf-8')
        block=src.split('class VideoWorker:',1)[1].split('class Runtime:',1)[0]
        self.assertNotIn('detector.predict(',block)
        self.assertNotIn('from ultralytics import YOLO',block)
        self.assertIn('detector.submit(',block)
        self.assertIn('detector.poll()',block)

    def test_no_laggy_qt_smooth_transform_in_live_preview(self):
        ui=(HERE/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf-8')
        self.assertIn('FastTransformation',ui)
        self.assertIn('self.timer.start(125)',ui)
        ast.parse(ui)

if __name__=='__main__':unittest.main(verbosity=2)
