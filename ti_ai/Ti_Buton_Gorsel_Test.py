"""Qt-level mouse-click tests; mock backend so camera/Spotify/Windows are not touched."""
import copy
import os
import sys
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QPushButton
import Ti_Kontrol_Merkezi_v1 as gui
from ti_services import DEFAULTS

class FakeStore:
    def __init__(self):self.rows=[]
    def add(self,k,t):self.rows.insert(0,('2026-10-31T00:00:00',k,t))
    def get(self,n=120):return self.rows[:n]
    def export_csv(self,path):open(path,'w',encoding='utf8').write('Zaman,Tür,Açıklama\n')

class FakeVideo:
    def __init__(self):
        self.thread=type('T',(),{'is_alive':lambda self:True})()
        self.recording=False
    def snapshot(self):return True,'ornek.jpg'

class FakeRuntime:
    def __init__(self,settings,post):
        self.settings=settings;self.post=post;self.store=FakeStore()
        self.video=FakeVideo();self.assistant=None;self.voice_thread=None
        self.active=True;self.calls=[]
    def toggle(self,k,v):self.settings[k]=v;self.calls.append(('toggle',k,v))
    def start(self,handler):self.calls.append(('start',))
    def stop(self):self.calls.append(('stop',))
    def follow(self,on):self.calls.append(('follow',on))
    def move(self,direction):self.calls.append(('move',direction))
    def speak(self,t):self.calls.append(('speak',t))
    def close(self):self.calls.append(('close',))

class FakeSpotify:
    def __init__(self):self.connected=False
    def connect(self,client,callback):callback(True,'Spotify TEST bağlantısı (gerçek bağlantı yok)')
    def disconnect(self):pass

APP=QApplication.instance() or QApplication([])

class TestTiGUI(unittest.TestCase):
    def setUp(self):
        self.patchers=[patch.object(gui,'Runtime',FakeRuntime),
                       patch.object(gui,'SpotifyConnection',FakeSpotify),
                       patch.object(gui,'settings_load',lambda:copy.deepcopy(DEFAULTS)),
                       patch.object(gui,'settings_save',lambda settings:None),
                       patch.object(gui,'open_target',lambda name:'Test açılış: '+name)]
        for p in self.patchers:p.start()
        self.w=gui.Window();self.w.show()
        APP.processEvents()
    def tearDown(self):
        self.w.close();APP.processEvents()
        for p in reversed(self.patchers):p.stop()

    def click(self,b,position=None):
        self.assertIsNotNone(b)
        APP.processEvents()
        QTest.mouseClick(b,Qt.LeftButton,Qt.NoModifier,position or b.rect().center())
        APP.processEvents()

    def button(self,text):
        found=[b for b in self.w.findChildren(QPushButton) if b.text()==text]
        self.assertTrue(found,'Buton bulunamadı: '+text)
        return found[0]

    def test_01_every_switch_clickable_on_visible_right_edge(self):
        for name,cb in self.w.toggles.items():
            before=cb.isChecked()
            self.click(cb,QPoint(cb.width()-17,cb.height()//2))
            self.assertNotEqual(before,cb.isChecked(),name+' sağdaki anahtara tıklanamıyor')
            self.assertIn(('toggle',name,not before),self.w.runtime.calls)

    def test_02_detection_dependency_and_shutdown(self):
        w=self.w
        w.toggles['preview'].setChecked(False)
        w.toggles['detection'].setChecked(True)
        self.assertTrue(w.toggles['preview'].isChecked())
        w.toggles['person_only'].setChecked(True)
        w.toggles['detection'].setChecked(False)
        self.assertFalse(w.toggles['person_only'].isChecked())

    def test_03_nav_theme_and_core_actions(self):
        w=self.w
        for idx,b in enumerate(w.navbuttons):
            self.click(b)
            self.assertEqual(w.stack.currentIndex(),idx)
        self.click(w.theme_button)
        self.assertEqual(w.settings['theme'],'dark')
        self.click(w.theme_button)
        self.assertEqual(w.settings['theme'],'light')
        self.click(w.start_button)
        self.click(w.stop_button)
        self.assertIn(('start',),w.runtime.calls)
        self.assertIn(('stop',),w.runtime.calls)

    def test_04_speak_and_ptz(self):
        w=self.w
        w.speak_text.setPlainText('Merhaba, ben Ti.')
        self.click(self.button('▶  Söylet'))
        self.assertIn(('speak','Merhaba, ben Ti.'),w.runtime.calls)
        for arrow,direction in [('↑','up'),('↓','down'),('←','left'),('→','right')]:
            self.click(self.button(arrow))
            self.assertIn(('move',direction),w.runtime.calls)

    def test_05_follow_record_snapshot_controls(self):
        w=self.w
        self.click(self.button('◎ Takibi Başlat'))
        self.click(self.button('■ Takibi Durdur'))
        self.assertIn(('follow',True),w.runtime.calls)
        self.assertIn(('follow',False),w.runtime.calls)
        w.show_section(1)
        self.click(self.button('Fotoğraf çek'))
        self.click(self.button('Video kaydı başlat'))
        self.assertTrue(w.runtime.video.recording)
        self.click(self.button('Kaydı durdur'))
        self.assertFalse(w.runtime.video.recording)
        self.assertTrue(any('Fotoğraf kaydedildi' in row[2] for row in w.runtime.store.rows))

    def test_06_settings_zoom_profiles_and_speech_examples(self):
        w=self.w
        w.show_section(1)
        w.zoom.setValue(16)
        self.assertAlmostEqual(w.settings['digital_zoom'],1.6)
        w.show_section(3)
        self.click(self.button('☾ Koyu tema'))
        self.assertEqual(w.settings['theme'],'dark')
        self.click(self.button('Ev profili'))
        self.assertEqual(w.settings['profile'],'Ev')
        self.click(self.button('Bu ayarları kaydet'))
        w.learn_phrase.setText('selam özel');w.learn_reply.setText('Merhaba')
        self.click(self.button('Komutu kaydet'))
        self.assertEqual(w.settings['learned']['selam özel'],'Merhaba')
        w.schedule_check.setChecked(False)
        self.click(self.button('Hatırlatıcıyı kaydet'))
        self.assertFalse(w.settings['schedule_enabled'])
        w.show_section(0)
        self.click(self.button('Hoş geldiniz'))
        self.assertEqual(w.speak_text.toPlainText(),'Hoş geldiniz')

if __name__=='__main__':
    print('Ti Qt buton testi: yalnızca ARAYÜZ test edilir; kamera/motor/Spotify kontrol edilmez.')
    unittest.main(verbosity=2)
