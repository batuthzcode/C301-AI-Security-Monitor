"""Camera-free, motor-free regression tests for Ti's shared person follower."""
from __future__ import annotations
import ast
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from ti_follow import SharedVisualFollower
import ti_services

HERE=Path(__file__).resolve().parent


class FakeMotor:
    def __init__(self, *, enabled=True, ok=True, message='ok', delay=0):
        self.enabled=enabled
        self.ok=ok
        self.message=message
        self.delay=delay
        self.calls=[]
        self.event=threading.Event()
    def move(self, direction):
        self.calls.append(direction)
        if self.delay:time.sleep(self.delay)
        self.event.set()
        return self.ok,self.message


class TestSharedFollower(unittest.TestCase):
    PERSON_LEFT=(([10,10,90,150],'person',0.93))
    PERSON_RIGHT=(([130,10,195,150],'person',0.93))
    PERSON_CENTER=(([60,10,140,150],'person',0.93))
    def setUp(self):
        self.motor=FakeMotor()
        self.status=[]
        self.follower=SharedVisualFollower(self.motor,lambda k,v:self.status.append((k,v)))
    def feed(self, box, now=None):
        self.follower.on_detections([box] if box else [],200,200,now=now)

    def test_disabled_does_not_move(self):
        self.feed(self.PERSON_RIGHT);self.feed(self.PERSON_RIGHT)
        self.assertFalse(self.motor.calls)

    def test_two_stable_observations_move_once_without_gui_block(self):
        self.follower.enable()
        self.feed(self.PERSON_RIGHT)
        self.assertFalse(self.motor.calls)
        start=time.monotonic()
        self.feed(self.PERSON_RIGHT)
        self.assertLess(time.monotonic()-start,.10)
        self.assertTrue(self.motor.event.wait(1))
        self.assertEqual(self.motor.calls,['right'])
        self.feed(self.PERSON_RIGHT)
        self.assertEqual(len(self.motor.calls),1,'pending post-move verification prevents repeated commands')

    def test_multiple_people_never_triggers_motor(self):
        self.follower.enable()
        for _ in range(4):
            self.follower.on_detections([self.PERSON_LEFT,self.PERSON_RIGHT],200,200)
        self.assertFalse(self.motor.calls)
        self.assertIn('Birden fazla',self.status[-1][1])

    def test_disable_stops_future_commands(self):
        self.follower.enable()
        self.feed(self.PERSON_RIGHT)
        self.follower.disable()
        self.feed(self.PERSON_RIGHT)
        self.assertFalse(self.motor.calls)

    def test_no_motor_allow_visual_tracking_but_no_physical_move(self):
        self.motor.enabled=False
        self.follower.enable()
        self.feed(self.PERSON_LEFT);self.feed(self.PERSON_LEFT)
        self.assertFalse(self.motor.calls)
        self.assertIn('Motor Kontrolü kapalı',self.status[-1][1])

    def test_unsupported_ptz_shows_diagnostic_and_disables(self):
        self.motor.ok=False
        self.motor.message='Bu go2rtc sürümünde PTZ motor kontrolü henüz bulunmuyor.'
        self.follower.enable()
        self.feed(self.PERSON_RIGHT);self.feed(self.PERSON_RIGHT)
        self.assertTrue(self.motor.event.wait(1))
        end=time.monotonic()+1
        while self.follower.active and time.monotonic()<end:time.sleep(.01)
        self.assertFalse(self.follower.active)
        self.assertTrue(any('PTZ kullanılamadı' in v for k,v in self.status))

    def test_timeout(self):
        self.follower.enable(seconds=5)
        self.follower.on_detections([self.PERSON_RIGHT],200,200,now=time.monotonic()+7)
        self.assertFalse(self.follower.active)

    def test_no_new_yolo_or_rtsp_in_shared_follow_module(self):
        code=(HERE/'ti_follow.py').read_text(encoding='utf-8')
        self.assertNotIn('VideoCapture',code)
        self.assertNotIn('ultralytics',code)
        src=(HERE/'ti_services.py').read_text(encoding='utf-8')
        self.assertIn('self.follower.on_detections(boxes,w,h,now=now)',src)

    def test_gui_auto_enables_detection_and_status_text(self):
        src=(HERE/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf-8')
        ast.parse(src)
        self.assertIn("for key in ('preview','detection','person_only'):",src)
        self.assertIn("elif kind=='follow_status':",src)

    def test_runtime_video_only_can_enable_follow(self):
        class DummyStore:pass
        with patch.object(ti_services,'EventStore',return_value=DummyStore()):
            rt=ti_services.Runtime(dict(ti_services.DEFAULTS),lambda k,v:self.status.append((k,v)))
            rt.active=True
            rt.settings['detection']=True
            rt.assistant=None # reproduce missing microphone/voice backend
            rt.follow(True)
            self.assertTrue(rt.follow_controller.active)
            rt.follow(False)
            self.assertFalse(rt.follow_controller.active)


if __name__=='__main__':unittest.main(verbosity=2)
