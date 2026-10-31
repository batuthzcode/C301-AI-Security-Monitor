"""Ti AI v2.0 offline regression tests. No camera, cloud or real device."""
from pathlib import Path
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from ti_v2_features import (ConversationMemory,VisualHistory,safe_url,home_assistant_toggle,
                           telegram_alert,vision_question,agent_chat,developer_proposal,extension_list)
from ti_v2_web import MobileServer
from ti_follow import SharedVisualFollower
from ti_v2_developer import publish_proposal
from ti_v2_updater import latest_release

HERE=Path(__file__).resolve().parent

class DummyMotor:
    enabled=True
    def __init__(self):self.calls=[];self.event=threading.Event()
    def move(self,d):self.calls.append(d);self.event.set();return True,'ok'

class FeatureTests(unittest.TestCase):
    def test_memory_persist_and_delete(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'memory.db';memory=ConversationMemory(path)
            memory.add('user','Merhaba');memory.add('assistant','Selam')
            self.assertEqual(len(ConversationMemory(path).recent()),2)
            memory.clear();self.assertEqual(memory.recent(),[])
    def test_memory_invalid_role(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):ConversationMemory(Path(d)/'m.db').add('system','bad')
    def test_visual_event_lookup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'images';root.mkdir()
            hist=VisualHistory(Path(d)/'db.sqlite',root)
            shot=root/'foto.jpg';shot.write_bytes(b'not a real photo')
            hist.add('Kişi','Kapı yakınında kişi algılandı',shot)
            self.assertEqual(len(hist.search('Kapı')),1)
            self.assertEqual(len(hist.search('bilinmeyen')),0)
    def test_visual_path_must_be_inside_captures(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'images';root.mkdir()
            with self.assertRaises(ValueError):VisualHistory(Path(d)/'db.sqlite',root).add('Olay','test',Path(d)/'secret.png')
    def test_ha_entity_whitelist(self):
        with self.assertRaises(ValueError):home_assistant_toggle('lock.front_door',token='fake')
        with self.assertRaises(ValueError):home_assistant_toggle('light.a;shutdown',token='fake')
    def test_ha_missing_token(self):
        with patch.dict(os.environ,{'TI_HOME_ASSISTANT_TOKEN':''}):
            with self.assertRaises(RuntimeError):home_assistant_toggle('light.salon')
    def test_ha_mock_request(self):
        with patch('ti_v2_features._post_json',return_value=[]) as api:
            self.assertIn('komutu',home_assistant_toggle('switch.masa',base_url='http://127.0.0.1:8123',token='fake'))
            self.assertEqual(api.call_args.args[0],'http://127.0.0.1:8123/api/services/switch/toggle')
    def test_ha_remote_http_refused(self):
        with self.assertRaises(ValueError):safe_url('http://192.168.1.2:8123',allow_local=True)
    def test_telegram_no_secret(self):
        with patch.dict(os.environ,{'TI_TELEGRAM_BOT_TOKEN':'','TI_TELEGRAM_CHAT_ID':''}):
            with self.assertRaises(RuntimeError):telegram_alert('test')
    def test_telegram_api_mock(self):
        with patch('ti_v2_features._post_json',return_value={'ok':True}) as api:
            self.assertTrue(telegram_alert('test',token='12345678:'+'a'*36,chat_id='-123456789'))
            self.assertEqual(api.call_args.args[1]['text'],'test')
    def test_vision_refuses_image_without_key(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            with self.assertRaises(RuntimeError):vision_question(b'\xff\xd8z','Ne var?')
    def test_vision_payload_has_no_store_and_does_not_use_search(self):
        with patch('ti_v2_features._post_json',return_value={'output':[{'type':'message','content':[{'type':'output_text','text':'Kitap'}]}]}) as api:
            self.assertEqual(vision_question(b'\xff\xd8z','Ne var?',api_key='fake'),'Kitap')
            body=api.call_args.args[1]
            self.assertFalse(body['store']);self.assertIn('data:image/jpeg;base64',body['input'][0]['content'][1]['image_url'])
            self.assertNotIn('tools',body)
    def test_vision_invalid_jpeg(self):
        with self.assertRaises(ValueError):vision_question(b'private image','ne var',api_key='fake')
    def test_agent_permissions(self):
        with self.assertRaises(ValueError):agent_chat('test','unknown')
    def test_agent_memory_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            memory=ConversationMemory(Path(d)/'m.sqlite')
            with patch('ti_v2_features.ask_ti',return_value='Cevap'):
                self.assertEqual(agent_chat('Soru','arastirmaci',memory=memory),'Cevap')
            self.assertEqual(len(memory.recent()),2)
    def test_dev_proposal_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'review.md'
            with patch('ti_v2_features.ask_ti',return_value='Test ve öneri') as ai:
                self.assertEqual(developer_proposal('Kod iyileştir','fps 8',path=dest),dest)
            self.assertIn('inceleme bekleyen',dest.read_text(encoding='utf8'))
            self.assertEqual(ai.call_args.kwargs['improvement_context'],'fps 8')
    def test_pr_cannot_publish_without_confirmation(self):
        with self.assertRaises(PermissionError):publish_proposal('.','.',confirmed=False)
    def test_update_repo_is_validated(self):
        with self.assertRaises(RuntimeError):latest_release('not-a-repo')
    def test_update_metadata_mock(self):
        from io import BytesIO
        class Fake:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):return b'{"tag_name":"v2.1","html_url":"https://github.com/org/repo/releases/tag/v2.1"}'
        with patch('ti_v2_updater.urllib.request.urlopen',return_value=Fake()):
            self.assertEqual(latest_release('org/repo')['version'],'v2.1')
    def test_plugin_builtins(self):
        plugins=extension_list();self.assertGreaterEqual(len(plugins),6)
        self.assertEqual(len({name for name,*_ in plugins}),len(plugins))
    def test_click_target_no_second_motor_or_camera_thread(self):
        m=DummyMotor();f=SharedVisualFollower(m,lambda *x:None)
        f.select_target(.85,.50);f.enable()
        left=([10,10,80,180],'person',.92)
        right=([140,10,195,180],'person',.94)
        for _ in range(2):f.on_detections([left,right],200,200,track_ids=[1,2])
        self.assertTrue(m.event.wait(2))
        self.assertEqual(m.calls,['right']);self.assertEqual(f._target_id,2)
    def test_target_lost_suspends_move(self):
        m=DummyMotor();f=SharedVisualFollower(m,lambda *x:None)
        f.select_target(.85,.50);f.enable()
        left=([10,10,80,180],'person',.92)
        right=([140,10,195,180],'person',.94)
        f.on_detections([left,right],200,200,track_ids=[1,2])
        f.on_detections([left,right],200,200,track_ids=[1,2]);m.event.wait(2)
        count=len(m.calls)
        for _ in range(4):f.on_detections([left],200,200,track_ids=[1])
        self.assertEqual(len(m.calls),count)
    def test_selection_rejects_out_of_frame(self):
        with self.assertRaises(ValueError):SharedVisualFollower(DummyMotor(),lambda *_:None).select_target(-.1,1)
    def test_mobile_unauthenticated_rejected_and_explicit_action_only(self):
        calls=[]
        srv=MobileServer(lambda:{'running':True},calls.append,token='x'*32,port=0)
        srv.start()
        try:
            port=srv.server.server_address[1];conn=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            conn.request('GET','/api/status');r=conn.getresponse();self.assertEqual(r.status,401);r.read()
            conn.request('GET','/api/status',headers={'Authorization':'Bearer '+'x'*32})
            r=conn.getresponse();self.assertEqual(json.loads(r.read())['running'],True)
            conn.request('POST','/api/control',json.dumps({'action':'arbitrary_shell'}),headers={'Authorization':'Bearer '+'x'*32})
            r=conn.getresponse();self.assertEqual(r.status,400);r.read();self.assertEqual(calls,[])
            conn.request('POST','/api/control',json.dumps({'action':'follow_stop'}),headers={'Authorization':'Bearer '+'x'*32})
            r=conn.getresponse();self.assertEqual(r.status,202);r.read();self.assertEqual(calls,['follow_stop'])
            conn.close()
        finally:srv.stop()
    def test_mobile_requires_tls_on_lan(self):
        with self.assertRaises(RuntimeError):MobileServer(lambda:{},lambda x:None,token='x'*30,host='0.0.0.0',port=0)
    def test_compatibility_gui_source(self):
        code=(HERE/'Ti_Kontrol_Merkezi_v1.py').read_text(encoding='utf8')
        for item in ('self.make_v2_page()', 'def v2_query(', 'def eventFilter(',
                     'self.v2_mobile_start', "elif kind=='web_control':", 'self.v2_telegram_opt'):
            self.assertIn(item,code)
        compile(code,'Ti_Kontrol_Merkezi_v1.py','exec')
    def test_bounded_video_event_clip_and_restart(self):
        code=(HERE/'ti_services.py').read_text(encoding='utf8')
        self.assertIn('now+6.0',code)
        self.assertIn("min(30,6*recoveries)",code)
        self.assertIn('recoveries>2',code)
    def test_exe_script(self):
        self.assertIn('PyInstaller',(HERE/'Ti_EXE_OLUSTUR.bat').read_text(encoding='utf8'))
    def test_safe_rollback_protected(self):
        from Ti_GERI_AL import restore
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):restore(d)

if __name__=='__main__':unittest.main(verbosity=2)
