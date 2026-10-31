"""Tests for continuous tracking and local Ti Lab features. No camera/network calls."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from ti_follow import SharedVisualFollower
from ti_lab import KnowledgeBook, ask_ti, _api_output, make_diagnostic, export_diagnostic, export_chat
from ti_services import EventStore, DEFAULTS


class Motor:
    def __init__(self):
        self.enabled=True
        self.calls=[]
        self.done=threading.Event()
    def move(self,where):
        self.calls.append(where)
        self.done.set()
        return True,'Komut iletildi'


class TestTracking(unittest.TestCase):
    BOX=([140,10,196,160],'person',0.95)

    def test_moves_again_after_single_nonimproving_check(self):
        motor=Motor();logs=[]
        tracker=SharedVisualFollower(motor,lambda *args:logs.append(args))
        tracker.enable(seconds=600)
        tracker.on_detections([self.BOX],200,200)
        tracker.on_detections([self.BOX],200,200)
        self.assertTrue(motor.done.wait(1))
        self.assertEqual(motor.calls,['right'])
        motor.done.clear()
        later=time.monotonic()+7
        tracker.on_detections([self.BOX],200,200,now=later)
        self.assertTrue(tracker.active, 'One stale frame must not disable follow')
        tracker.on_detections([self.BOX],200,200,now=later+.9)
        self.assertTrue(motor.done.wait(1))
        self.assertEqual(motor.calls,['right','right'])
        tracker.disable()

    def test_rolling_budget_does_not_disable_tracking(self):
        motor=Motor();tracker=SharedVisualFollower(motor,lambda *args:None,max_steps=1)
        tracker.enable(seconds=600)
        tracker.on_detections([self.BOX],200,200)
        tracker.on_detections([self.BOX],200,200)
        self.assertTrue(motor.done.wait(1))
        tracker.on_detections([self.BOX],200,200,now=time.monotonic()+6)
        tracker.on_detections([self.BOX],200,200,now=time.monotonic()+7)
        self.assertEqual(len(motor.calls),1)
        self.assertTrue(tracker.active)
        tracker.disable()

    def test_configurable_session(self):
        motor=Motor();tracker=SharedVisualFollower(motor,lambda *args:None)
        tracker.enable(seconds=1800,max_steps_per_minute=6)
        self.assertEqual(tracker.max_steps,6)
        self.assertTrue(tracker.active)
        tracker.disable()

    def test_ambiguous_people(self):
        motor=Motor();tracker=SharedVisualFollower(motor,lambda *args:None)
        tracker.enable()
        for _ in range(4):tracker.on_detections([self.BOX,self.BOX],200,200)
        self.assertEqual(motor.calls,[])


class TestLocalTools(unittest.TestCase):
    def test_note_search_and_literal_percent(self):
        with tempfile.TemporaryDirectory() as td:
            kb=KnowledgeBook(Path(td)/'notes.db')
            kb.add('YOLO optimizasyon','CPU %15')
            kb.add('test','Normal')
            self.assertEqual(len(kb.search('%15')),1)
            self.assertEqual(len(kb.search('YOLO')),1)
            self.assertEqual(len(kb.search()),2)

    def test_empty_notes_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            kb=KnowledgeBook(Path(td)/'notes.db')
            with self.assertRaises(ValueError):kb.add(' ','')

    def test_event_store_search_and_json_export(self):
        with tempfile.TemporaryDirectory() as td:
            import ti_services
            with patch.object(ti_services,'DATA',Path(td)):
                ev=EventStore()
                ev.add('YOLO','kişi görüldü')
                ev.add('Sistem','başladı')
                ev.add('Sistem','başarı %100')
                self.assertEqual(len(ev.search('kişi')),1)
                self.assertEqual(len(ev.search('%100')),1)
                dest=Path(td)/'events.json'
                ev.export_json(dest)
                events=json.loads(dest.read_text(encoding='utf-8'))
                self.assertEqual(len(events),3)
                self.assertEqual(events[-1]['message'],'başarı %100')

    def test_diagnostic_exports(self):
        class Follow:active=True
        class Video:
            yolo_ready=True
            frame_count=300
            fps=11.3
        class RT:
            active=True;assistant=None;video=Video();follow_controller=Follow()
        diag=make_diagnostic(RT(),dict(DEFAULTS))
        self.assertEqual(diag['camera_fps'],11.3)
        self.assertNotIn('video_source',diag)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'report.md'
            export_diagnostic(path,diag)
            self.assertIn('Ti AI Tanı',path.read_text(encoding='utf-8'))
            export_chat(Path(td)/'chat.md',[('user','Deneme'),('ti','Merhaba')])
            self.assertIn('Merhaba',(Path(td)/'chat.md').read_text(encoding='utf-8'))

    def test_missing_api_key_is_explicit(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':''}):
            with self.assertRaisesRegex(RuntimeError,'OPENAI_API_KEY'):
                ask_ti('Bana bilim haberi getir',research=True)

    def test_ai_request_uses_web_tool_only_by_user_request(self):
        responses=[]
        def mock_post(url,body,headers=None,timeout=None):
            responses.append(body)
            return {'output':[{'type':'message','content':[{'type':'output_text','text':'Sonuç',
                'annotations':[{'type':'url_citation','url':'https://example.org/abc'}]}]}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-test-key'}), patch('ti_lab._post_json',mock_post):
            text=ask_ti('Araştır',research=True)
            self.assertIn('https://example.org/abc',text)
            self.assertEqual(responses[0]['tools'],[{'type':'web_search'}])
            self.assertFalse(responses[0]['store'])
            ask_ti('Merhaba')
            self.assertNotIn('tools',responses[1])

    def test_improvement_never_calls_shell_or_modifies_code(self):
        captured=[]
        def fake_post(url,body,headers=None,timeout=None):
            captured.append(body)
            return {'output':[{'type':'message','content':[{'type':'output_text','text':'Öneri'}]}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake-test-key'}), patch('ti_lab._post_json',fake_post):
            self.assertEqual(ask_ti('Ne düzeltelim?',improvement_context='FPS=8'), 'Öneri')
        self.assertIn('FPS=8',captured[0]['input'])
        self.assertIn('kodu değiştirme',captured[0]['instructions'])

    def test_gui_wiring_static(self):
        src=(Path(__file__).parent/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf-8')
        for marker in ('self.make_lab_page()',"elif kind=='lab_answer':",'self.toggle_privacy',
                       'self.events_filter.textChanged.connect(self.reload_logs)',
                       'self.runtime.store.export_json(dest)'):
            self.assertIn(marker,src)

if __name__=='__main__':unittest.main(verbosity=2)
