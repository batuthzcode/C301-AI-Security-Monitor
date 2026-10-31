"""Ti AI AR Studio offline / synthetic input tests; no camera or cloud required."""
from pathlib import Path
import ast
import io
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import cv2
import numpy as np
from ti_ar_core import (Point,hand_gesture,palm_anchor,face_geometry,Drawing,MASKS,OBJECTS,COLORS,valid_png)
from ti_ar_render import (apply_face_mask,drawing_png,draw_strokes,draw_object,draw_sticker)
from ti_ar_worker import ARStudio,MediapipeModel,download_models

def make_hand(gesture):
    # Hand with wrist (0.5,0.8), MCP and PIP joints vertically upwards.
    points=[Point(.5,.8)]*21
    pts=list(points)
    for base,tip,pip,x in [(5,8,6,.39),(9,12,10,.47),(13,16,14,.55),(17,20,18,.63)]:
        pts[base]=Point(x,.62);pts[base+1]=Point(x,.56)
        pts[pip]=Point(x,.55)
        pts[tip]=Point(x,.32 if (gesture=='palm' or gesture=='draw' and tip==8 or gesture=='select' and tip in (8,12)) else .67)
    pts[4]=Point(.24,.60)
    if gesture=='erase':pts[4]=pts[8]
    return pts

class ARCoreTests(unittest.TestCase):
    def test_hand_gesture_draw(self):self.assertEqual(hand_gesture(make_hand('draw')),'draw')
    def test_hand_gesture_select(self):self.assertEqual(hand_gesture(make_hand('select')),'select')
    def test_hand_gesture_palm(self):self.assertEqual(hand_gesture(make_hand('palm')),'palm')
    def test_hand_gesture_erase(self):self.assertEqual(hand_gesture(make_hand('erase')),'erase')
    def test_short_landmarks(self):self.assertEqual(hand_gesture([]),'none')
    def test_geometry_rejects_short_face(self):self.assertIsNone(face_geometry([],640,480))
    def test_drawing_bounded(self):
        d=Drawing(max_points=55,max_strokes=3)
        for i in range(10):
            d.begin();[d.point(j/100, i/11) for j in range(50)];d.end()
        self.assertLessEqual(len(d),55)
        self.assertLessEqual(len(d.strokes),3)
    def test_eraser_near_stroke(self):
        d=Drawing();d.begin();d.point(.5,.5);d.end()
        self.assertEqual(d.erase(.51,.51),1);self.assertEqual(len(d),0)
    def test_bounded_coordinates(self):
        d=Drawing();d.begin();d.point(3,-2)
        self.assertEqual(d.strokes[0]['points'][0],(1,0))
    def test_save_png_alpha(self):
        d=Drawing();d.begin();d.point(.5,.5);d.point(.6,.6)
        out=drawing_png(d,160,90)
        self.assertEqual(out.shape,(90,160,4))
        self.assertTrue(out[:,:,3].any())
    def test_png_validation(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'x.png';f.write_bytes(b'png')
            self.assertEqual(valid_png(f),f)
            with self.assertRaises(ValueError):valid_png(Path(td)/'nothing.png')
    def test_no_unbounded_object_palette(self):
        self.assertIn('3D Dünya',OBJECTS);self.assertIn('Muzip yüz (özgün)',MASKS)
        self.assertIn('Futbol',OBJECTS)

class ARRenderingTests(unittest.TestCase):
    def setUp(self):self.frame=np.zeros((400,640,3),np.uint8)
    def test_all_spheres_render(self):
        for kind in OBJECTS[1:]:
            out=draw_object(self.frame.copy(),(320,180),70,kind,rotation=.8)
            self.assertEqual(out.shape,self.frame.shape)
            self.assertTrue(out.any(),kind)
    def test_globe_changes_with_rotation(self):
        a=draw_object(self.frame.copy(),(300,180),80,'3D Dünya',0)
        b=draw_object(self.frame.copy(),(300,180),80,'3D Dünya',1.3)
        self.assertGreater(np.count_nonzero(a!=b),100)
    def test_all_filters_render(self):
        face=[Point(.36 + .14*np.cos(i*2*np.pi/478),.4+.20*np.sin(i*2*np.pi/478)) for i in range(478)]
        face[33]=Point(.39,.39);face[263]=Point(.61,.39)
        for kind in MASKS[1:-1]:
            out=apply_face_mask(self.frame.copy(),[face],kind)
            self.assertTrue(out.any(),kind)
    def test_custom_rgba_image(self):
        with tempfile.TemporaryDirectory() as td:
            custom=np.zeros((140,140,4),dtype=np.uint8);custom[:,:,:3]=[10,200,200];custom[:,:,3]=180
            filename=Path(td)/'custom.png';cv2.imwrite(str(filename),custom)
            face=[Point(.5,.5)]*478;face[33]=Point(.39,.4);face[263]=Point(.61,.4)
            face[1]=Point(.38,.3);face[2]=Point(.63,.7)
            apply_face_mask(self.frame,[face],'Özel PNG',filename)
            self.assertTrue(self.frame.any())
    def test_stickers(self):
        for kind in ('Kalp','Yıldız','Ok'):
            out=draw_sticker(self.frame.copy(),(.5,.5),kind)
            self.assertTrue(out.any())
    def test_draw_on_frame(self):
        d=Drawing();d.begin();d.point(.4,.5);d.point(.5,.6)
        self.assertTrue(draw_strokes(self.frame.copy(),d).any())
    def test_no_effect_when_none(self):
        a=self.frame.copy();draw_object(a,(120,120),70,'Kapalı');self.assertFalse(a.any())

class WorkerTests(unittest.TestCase):
    def test_optional_models_missing_shows_error(self):
        with tempfile.TemporaryDirectory() as td:
            d=MediapipeModel(td)
            with self.assertRaisesRegex(RuntimeError,'eksik'):d._init('hand')
    def test_config_validation(self):
        with tempfile.TemporaryDirectory() as td:
            w=ARStudio(td,lambda *args:None,td)
            with self.assertRaises(ValueError):w.configure(mask='unknown')
            with self.assertRaises(ValueError):w.configure(color=(1,2,3))
            w.configure(fps_limit=500,brush=100)
            self.assertEqual(w.fps_limit,15);self.assertEqual(w.brush,25)
    def test_sticker_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            w=ARStudio(td,lambda *args:None,td)
            for i in range(70):w.add_sticker('Kalp')
            self.assertEqual(len(w.stickers),30)
    def test_worker_latest_frame_no_model(self):
        with tempfile.TemporaryDirectory() as td:
            notices=[];w=ARStudio(td,lambda *args:notices.append(args),td)
            w.start();w.submit(np.ones((800,1200,3),np.uint8)*60)
            deadline=time.monotonic()+3
            while w.snapshot() is None and time.monotonic()<deadline:time.sleep(.025)
            img=w.snapshot();self.assertIsNotNone(img)
            self.assertLessEqual(max(img.shape[:2]),640)
            self.assertEqual(img.shape[2],3)
            saved=w.save_photo();self.assertTrue(saved.is_file())
            w.stop()
            self.assertIsNone(w.snapshot())
    def test_no_start_duplicate_while_old_closes(self):
        with tempfile.TemporaryDirectory() as td:
            w=ARStudio(td,lambda *args:None,td);w.start();w.start()
            self.assertEqual(w.worker.name,'Ti-AR-LatestOnly');w.stop()
    def test_model_download_injected(self):
        with tempfile.TemporaryDirectory() as td:
            class Resp(io.BytesIO):
                def __enter__(self):return self
                def __exit__(self,*args):self.close()
            with patch('urllib.request.urlopen',side_effect=lambda *a,**k:Resp(b'd'*70000)):
                self.assertEqual(len(download_models(td)),2)
            self.assertTrue((Path(td)/'face_landmarker.task').exists())
    def test_ar_renders_simulated_hand_without_mediapipe(self):
        with tempfile.TemporaryDirectory() as td:
            w=ARStudio(td,lambda *args:None,td)
            w.configure(obj='3D Dünya',drawing_on=True)
            out=w._render(np.zeros((280,480,3),np.uint8),[make_hand('palm')],[],'Kapalı','3D Dünya',True,None,1.)
            self.assertTrue(out.any())
            out=w._render(np.zeros((280,480,3),np.uint8),[make_hand('draw')],[],'Kapalı','Kapalı',True,None,2.)
            self.assertGreater(len(w.draw),0)
            self.assertTrue(out.any())
    def test_gui_static_wiring(self):
        root=Path(__file__).resolve().parent
        tree=ast.parse((root/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Window')
        methods={n.name for n in cls.body if isinstance(n,ast.FunctionDef)}
        expected=['make_ar_page','ar_start','ar_stop','ar_poll','ar_photo','ar_save_drawing',
                  'ar_record_start','ar_record_stop','ar_clear','ar_load_png','ar_choose_sticker',
                  'ar_download_models','ar_media_key']
        self.assertTrue(set(expected).issubset(methods))
        text=(root/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf8')
        self.assertIn('self.stack.addWidget(self.make_ar_page())',text)
        self.assertIn('if self.stack.currentIndex()==8',text)
    def test_record_control_and_png(self):
        with tempfile.TemporaryDirectory() as td:
            w=ARStudio(td,lambda *args:None,td)
            w.draw.begin();w.draw.point(.5,.5);w.draw.end()
            self.assertTrue(w.save_drawing().is_file())
            w.set_recording(True);self.assertTrue(w.recording);w.set_recording(False)

if __name__=='__main__':unittest.main()
