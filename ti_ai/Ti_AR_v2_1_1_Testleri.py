"""Regression checks for previous silent AR failure, no native MP dependency."""
from pathlib import Path
import unittest
import tempfile
import time
from unittest.mock import patch
import numpy as np
from ti_ar_worker import ARStudio,ar_preflight
from ti_ar_core import Point
from ti_ar_render import apply_face_mask,draw_object
class Checks(unittest.TestCase):
    def test_missing_hands_reports_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            issues=ar_preflight(td,require_hand=True,require_face=False)
            self.assertTrue(any('hand_landmarker.task' in x for x in issues))
    def test_missing_faces_reports_explicitly(self):
        with tempfile.TemporaryDirectory() as td:
            issues=ar_preflight(td,require_hand=False,require_face=True)
            self.assertTrue(any('face_landmarker.task' in x for x in issues))
    def test_no_models_needed_does_not_error(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(ar_preflight(td,require_hand=False,require_face=False),[])
    def test_both_models_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            issues=ar_preflight(td,require_hand=True,require_face=True)
            self.assertEqual(sum('.task' in x for x in issues),2)
    def test_empty_stub_files_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ('face_landmarker.task','hand_landmarker.task'):
                (Path(td)/name).write_bytes(b'broken')
            issues=ar_preflight(td,require_hand=True,require_face=True)
            self.assertEqual(sum('bozuk' in x for x in issues),2)
    def test_copies_at_target_frame_rate(self):
        with tempfile.TemporaryDirectory() as td:
            ar=ARStudio(td,lambda *a:None,td)
            ar.configure(fps_limit=4)
            ar.start()
            a=np.zeros((480,640,3),np.uint8)
            for i in range(25):ar.submit(a)
            self.assertLessEqual(ar._input_frames,2)
            ar.stop()
    def test_visual_path_world(self):
        a=np.zeros((360,640,3),np.uint8)
        draw_object(a,(500,155),64,'3D Dünya',1)
        self.assertTrue(a.any())
    def test_visual_path_face(self):
        import math
        a=np.zeros((360,640,3),np.uint8)
        f=[Point(.5+.1*math.cos(i*2*math.pi/478),.4+.2*math.sin(i*2*math.pi/478)) for i in range(478)]
        f[33]=Point(.42,.4);f[263]=Point(.58,.4)
        apply_face_mask(a,[f],'Muzip yüz (özgün)')
        self.assertTrue(a.any())
    def test_gui_hook_exists(self):
        text=(Path(__file__).parent/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf-8')
        for name in ('ar_diagnose','ar_visual_test','ar_preflight','AR BAŞLATILAMADI','self.ar_status.setText(status)'):
            self.assertIn(name,text)
    def test_diagnosis_cli_has_real_model_init(self):
        text=(Path(__file__).parent/'Ti_AR_Teshis.py').read_text(encoding='utf8')
        self.assertIn("md._init('hand')",text);self.assertIn("md._init('face')",text)
if __name__=='__main__':unittest.main()
