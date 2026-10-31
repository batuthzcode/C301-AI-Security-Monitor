"""Backend and source-contract tests. No physical camera/PTZ/voice/GUI execution."""
from pathlib import Path
import ast
import threading
import unittest
from unittest.mock import patch
import ti_services

class FakeAssistant:
    def __init__(self):
        self.speaker=object()
        self.calls=[]
        self.finished=threading.Event()
    def _respond(self,text):
        self.calls.append(text)
        self.finished.set()

class TestUIContracts(unittest.TestCase):
    def test_custom_switch_right_side_hit_test_present(self):
        src=(Path(__file__).parent/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf8')
        tree=ast.parse(src)
        cls=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='Switch')
        self.assertIn('hitButton',[n.name for n in cls.body if isinstance(n,ast.FunctionDef)])
        self.assertIn('self.rect().contains(pos)',src)

    def test_every_primary_button_constructor_has_action(self):
        src=(Path(__file__).parent/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf8')
        tree=ast.parse(src)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='btn']
        missing=[]
        for n in calls:
            # Skip declaration of helper. Calls must pass callback second arg or func keyword.
            if len(n.args)<2 and not any(k.arg=='func' for k in n.keywords):
                missing.append(n.lineno)
        self.assertFalse(missing,'Callback atanmadığı için çalışmayan butonlar: '+str(missing))
        self.assertGreaterEqual(len(calls),25)

    def test_all_switches_have_runtime_binding(self):
        src=(Path(__file__).parent/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf8')
        self.assertIn('cb.toggled.connect(lambda state,k=key:self.changed_toggle(k,state))',src)
        self.assertIn('self.runtime.toggle(key,state)',src)

    def test_preview_toggle_restarts_video(self):
        settings=dict(ti_services.DEFAULTS)
        events=[]
        with patch.object(ti_services,'EventStore'), patch.object(ti_services,'settings_save'):
            runtime=ti_services.Runtime(settings,lambda *args:events.append(args))
            runtime.active=True
            with patch.object(runtime.video,'start') as start:
                runtime.toggle('preview',False)
                runtime.toggle('preview',True)
                runtime.toggle('detection',True)
                self.assertTrue(settings['preview'])
                self.assertTrue(settings['detection'])
                self.assertEqual(start.call_count,2)
                self.assertTrue(any(x[0]=='info' for x in events))

    def test_speech_runs_in_background(self):
        settings=dict(ti_services.DEFAULTS)
        msgs=[]
        with patch.object(ti_services,'EventStore'), patch.object(ti_services,'settings_save'):
            runtime=ti_services.Runtime(settings,lambda *args:msgs.append(args))
            assistant=FakeAssistant();runtime.assistant=assistant
            runtime.speak('Merhaba!')
            self.assertTrue(assistant.finished.wait(2))
            self.assertEqual(assistant.calls,['Merhaba!'])
            self.assertTrue(any(k=='info' for k,_ in msgs))

if __name__=='__main__':unittest.main(verbosity=2)
