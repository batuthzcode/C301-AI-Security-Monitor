"""Camera-free checks for Ti v1.0. Does not rotate camera / access Spotify / shut down PC."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ti_commands import CommandRouter, battery, specs
from ti_spotify import SpotifyConnection, REDIRECT
from ti_v1_core import normalize, interpret_utterance, answer_command, movement_intent, TiPersonFollower
import ti_services


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.actions=[]
        self.settings=dict(ti_services.DEFAULTS)
        self.cmd=CommandRouter(self.settings,lambda key,val:self.actions.append((key,val)))

    def test_normalize(self):self.assertEqual(normalize('ŞİMDİ SAAT KAÇ?'),'simdi saat kac')
    def test_wake(self):self.assertEqual(interpret_utterance('Merhaba Ti',active=False),('wake',''))
    def test_reject_before_wake(self):self.assertEqual(interpret_utterance('Ti sola dön',active=False),('ignore',''))
    def test_command(self):self.assertEqual(interpret_utterance('Ti sola dön',active=True),('command','sola don'))
    def test_followup(self):self.assertEqual(interpret_utterance('saat kaç',active=True,followup=True),('followup','saat kac'))
    def test_clock(self):self.assertTrue(answer_command('saat kaç').startswith('Saat'))
    def test_date(self):self.assertIn('Bugün',answer_command('tarih ne'))
    def test_name(self):self.assertIn('Ti',answer_command('adın ne'))
    def test_motor_left(self):self.assertEqual(movement_intent('sola dön'),('move','left'))
    def test_motor_up(self):self.assertEqual(movement_intent('yukarı bak'),('move','up'))
    def test_motor_down(self):self.assertEqual(movement_intent('aşağı dön'),('move','down'))
    def test_follow_enable(self):self.assertEqual(movement_intent('beni takip et')[0],'follow_on')
    def test_follow_disable(self):self.assertEqual(movement_intent('takibi durdur')[0],'follow_off')
    def test_follow_is_horizontal(self):
        self.assertIsNone(TiPersonFollower.direction_for_offset(0,.50,vertical=False))
    def test_follow_centering(self):
        self.assertEqual(TiPersonFollower.direction_for_offset(.4,0),'right')
    def test_themes(self):
        self.cmd.run('koyu tema aç')
        self.assertIn(('action',('theme_dark',None)),self.actions)
        self.cmd.run('beyaz tema')
        self.assertIn(('action',('theme_light',None)),self.actions)
    def test_person_filter(self):
        self.cmd.run('sadece kişileri göster')
        self.assertIn(('action',('person_only',None)),self.actions)
    def test_snapshot(self):
        self.cmd.run('fotoğraf çek')
        self.assertIn(('action',('snapshot',None)),self.actions)
    def test_record(self):
        self.cmd.run('kaydı başlat');self.cmd.run('kaydı durdur')
        self.assertIn(('action',('record_on',None)),self.actions)
        self.assertIn(('action',('record_off',None)),self.actions)
    def test_shutdown_needs_confirm(self):
        self.cmd.run('bilgisayarı kapat')
        self.assertIn(('confirm','shutdown'),self.actions)
    def test_learned(self):
        self.settings['learned']={'bana motivasyon ver':'Bugün başaracaksın.'}
        self.assertEqual(self.cmd.run('bana motivasyon ver'),'Bugün başaracaksın.')
    @patch('webbrowser.open')
    def test_spotify_search(self,op):
        answer=self.cmd.run('Sezen Aksu Gülümse şarkısını aç')
        self.assertIn('Spotify',answer)
        self.assertIn('/search/',op.call_args[0][0])
    @patch('webbrowser.open')
    def test_spotify_combined(self,op):
        answer=self.cmd.run('Spotify aç ve Sezen Aksu Gülümse şarkısını aç')
        self.assertIn('Spotify',answer)
        self.assertIn('sezen',answer)
    @patch('ti_commands.open_target',return_value='Açıldı')
    def test_open_spotify(self,f):
        self.assertEqual(self.cmd.run('Spotify aç'),'Açıldı')
        f.assert_called_once_with('spotify')
    def test_cpu(self):self.assertIn('RAM',specs())
    def test_llm_disabled_fallback(self):self.assertIsNone(self.cmd.run('bana bir hikaye anlat'))

    def test_speak_scheduled_profile(self):
        self.cmd.run('gece modunu aç')
        self.assertIn(('action',('profile_night',None)),self.actions)

    def test_spotify_connection_fake(self):
        fake=SpotifyConnection();fake.access='FAKE_TOKEN';fake.expires_at=10**12
        with patch.object(fake,'_api',side_effect=[
            {'tracks':{'items':[{'name':'Gülümse','uri':'spotify:track:TEST','artists':[{'name':'Sezen Aksu'}]}]}},
            {'devices':[{'id':'test-device','is_active':True}]},{}]):
            ok,msg=fake.play_song('Gülümse')
            self.assertTrue(ok)
            self.assertIn('oynatılıyor',msg)

    def test_spotify_without_device(self):
        fake=SpotifyConnection();fake.access='FAKE_TOKEN';fake.expires_at=10**12
        with patch.object(fake,'_api',side_effect=[
            {'tracks':{'items':[{'name':'Song','uri':'spotify:track:X','artists':[{'name':'Artist'}]}]}},
            {'devices':[]}]):
            ok,msg=fake.play_song('Song')
            self.assertFalse(ok)
            self.assertIn('cihaz',msg)

    def test_spotify_redirect_loopback(self):
        self.assertEqual(REDIRECT,'http://127.0.0.1:8795/callback')

    def test_person_alert_opt_in_default_off(self):
        self.assertFalse(self.settings['alert_person'])

    def test_auto_snapshot_default_off(self):
        self.assertFalse(self.settings['auto_snapshot'])



class TestStorage(unittest.TestCase):
    def test_settings_and_events(self):
        with tempfile.TemporaryDirectory() as d:
            old_dir=ti_services.DATA;old_path=ti_services.SETTINGS_PATH
            try:
                ti_services.DATA=Path(d)
                ti_services.SETTINGS_PATH=Path(d)/'settings.json'
                s=ti_services.settings_load()
                self.assertEqual(s['theme'],'light')
                s['theme']='dark';ti_services.settings_save(s)
                self.assertEqual(ti_services.settings_load()['theme'],'dark')
                db=ti_services.EventStore()
                db.add('Ayar','Koyu tema etkin')
                self.assertIn('Koyu',db.get()[0][2])
                csv=Path(d)/'log.csv';db.export_csv(csv)
                self.assertTrue(csv.exists())
            finally:
                ti_services.DATA=old_dir;ti_services.SETTINGS_PATH=old_path

    def test_source_local_only(self):
        with tempfile.TemporaryDirectory() as d:
            old_dir=ti_services.DATA;old_path=ti_services.SETTINGS_PATH
            try:
                ti_services.DATA=Path(d);ti_services.SETTINGS_PATH=Path(d)/'settings.json'
                Path(ti_services.SETTINGS_PATH).write_text(json.dumps({'video_source':'rtsp://192.168.1.2/secret'}))
                self.assertEqual(ti_services.settings_load()['video_source'],ti_services.STREAM_URL)
            finally:ti_services.DATA=old_dir;ti_services.SETTINGS_PATH=old_path


if __name__=='__main__': unittest.main(verbosity=2)
