"""Ti AI v2.3 Control Center: Windows desktop UI and local C301 runtime.

This distributable source package starts without private camera credentials.
Hardware integrations remain opt-in and use the user's local configuration.
"""
from __future__ import annotations
from datetime import datetime
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from PySide6.QtCore import Qt, QTimer, QSize, QEvent, QRect, QRectF
from PySide6.QtGui import QFont, QImage, QPixmap, QColor, QIcon, QPainter
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QHBoxLayout,QVBoxLayout,QGridLayout,
    QLabel,QFrame,QPushButton,QLineEdit,QTextEdit,QScrollArea,QStackedWidget,QListWidget,
    QCheckBox,QSlider,QComboBox,QSpinBox,QDoubleSpinBox,QFormLayout,QTableWidget,QTableWidgetItem,
    QMessageBox,QFileDialog,QSplitter,QSizePolicy,QSystemTrayIcon,QStyle,QInputDialog)

from ti_services import Runtime, settings_load, settings_save, CAPTURES, BASE, DATA
from ti_commands import CommandRouter, open_target
from ti_spotify import SpotifyConnection
from ti_lab import KnowledgeBook, ask_ti, make_diagnostic, diagnostic_text, export_diagnostic, export_chat
from ti_v2_features import (AGENTS, ConversationMemory, VisualHistory, extension_list,
    agent_chat, vision_question, telegram_alert, home_assistant_toggle, developer_proposal)
from ti_v2_web import MobileServer
from ti_v2_developer import publish_proposal
from ti_v2_updater import latest_release
from ti_ar_core import MASKS, OBJECTS, COLORS
from ti_ar_worker import ARStudio, download_models, ar_preflight
import ti_network_guard as netguard
import ti_cyber_inventory as cyberinv

LIGHT = dict(bg='#f4f7fc',card='#ffffff',side='#f9fbff',text='#14243b',muted='#72839d',
             border='#e5ebf5',primary='#287af0',soft='#edf4ff',bad='#d54455',green='#20af71',line='#dbe4f2')
DARK = dict(bg='#111824',card='#192334',side='#141d2b',text='#eef4ff',muted='#9baec4',
            border='#2b3c50',primary='#4894ff',soft='#243751',bad='#f17e86',green='#4bd59b',line='#34465a')


def stylesheet(theme):
    c = DARK if theme=='dark' else LIGHT
    return f"""
    QMainWindow,QWidget#root {{ background:{c['bg']}; color:{c['text']}; }}
    QWidget {{ font-family:'Segoe UI'; font-size:13px; color:{c['text']}; }}
    QFrame#sidebar {{ background:{c['side']}; border-right:1px solid {c['border']}; }}
    QFrame#card {{ background:{c['card']}; border:1px solid {c['border']}; border-radius:13px; }}
    QLabel#title {{ font-size:20px; font-weight:750; }}
    QLabel#section {{ font-size:14px; font-weight:650; }}
    QLabel#muted {{ color:{c['muted']}; font-size:12px; }}
    QLabel#status {{ color:{c['green']}; font-weight:700; }}
    QLabel#camera {{ background:#101721; color:#b2c2d5; border-radius:9px; }}
    QPushButton {{ border:1px solid {c['border']}; background:{c['card']}; color:{c['text']};
                   padding:9px 13px; border-radius:9px; font-weight:500; }}
    QPushButton:hover {{ background:{c['soft']}; border-color:{c['primary']}; }}
    QPushButton:disabled {{ color:{c['muted']}; background:{c['bg']}; }}
    QPushButton[role='primary'] {{ background:{c['primary']};color:#ffffff;border-color:{c['primary']};font-weight:650; }}
    QPushButton[role='green'] {{ background:#28b477;color:#ffffff;border-color:#28b477;font-weight:650; }}
    QPushButton[role='danger'] {{ background:#fff0f2;color:#ce4050;border-color:#f6d9dd;font-weight:650; }}
    QPushButton[role='nav'] {{ text-align:left;border:0;background:transparent;padding:13px 15px;font-weight:550; }}
    QPushButton[role='active'] {{ text-align:left;background:{c['soft']};color:{c['primary']};border:0;padding:13px 15px;font-weight:650; }}
    QLineEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox {{ background:{c['card']};color:{c['text']};
       border:1px solid {c['border']};border-radius:8px;padding:8px; selection-background-color:{c['primary']}; }}
    QLineEdit:focus,QTextEdit:focus,QComboBox:focus {{ border:1px solid {c['primary']}; }}
    QListWidget,QTableWidget {{ background:{c['card']};color:{c['text']};border:0;outline:0; }}
    QListWidget::item {{padding:10px 7px;border-bottom:1px solid {c['border']};}}
    QHeaderView::section {{background:{c['soft']};padding:9px;border:0;color:{c['muted']};}}
    QScrollArea {{border:0;background:transparent;}}
    QScrollBar:vertical {{background:transparent;width:9px;}}
    QScrollBar::handle:vertical {{background:{c['line']};border-radius:4px;min-height:20px;}}
    QCheckBox {{spacing:9px;}}
    QCheckBox::indicator {{width:19px;height:19px;}}
    QSlider::groove:horizontal {{height:5px;background:{c['line']};border-radius:2px;}}
    QSlider::handle:horizontal {{background:{c['primary']};width:15px;margin:-5px 0;border-radius:7px;}}
    """



class Switch(QCheckBox):
    """Clickable switch with a real checked/unchecked state and label."""
    def __init__(self, label):
        super().__init__(label)
        self.setFixedHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip('Satırın herhangi bir yerine tıklayarak değiştirin.')

    def hitButton(self, pos):
        # A switch is PAINTED ON THE RIGHT but QCheckBox's native hit region
        # is usually ON THE LEFT. Without this, right-side clicks do nothing.
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        dark = getattr(self.window(), 'settings', {}).get('theme') == 'dark'
        p.setPen(QColor('#eef4ff' if dark else '#182940'))
        p.drawText(QRect(2, 0, max(0,self.width()-70), self.height()), Qt.AlignVCenter|Qt.AlignLeft, self.text())
        x=self.width()-53;y=(self.height()-22)/2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor('#287af0' if self.isChecked() else ('#44536a' if dark else '#cdd8e6')))
        p.drawRoundedRect(QRectF(x,y,48,22),11,11)
        p.setBrush(QColor('white'))
        p.drawEllipse(QRectF(x+(27 if self.isChecked() else 3), y+3, 16, 16))
        p.end()

def txt(s, muted=False, title=False):
    w=QLabel(str(s));w.setWordWrap(True)
    w.setObjectName('title' if title else 'muted' if muted else 'section');return w


def btn(label, func=None, role=None, min_width=None):
    b=QPushButton(label)
    if role:b.setProperty('role',role)
    if min_width:b.setMinimumWidth(min_width)
    b.setCursor(Qt.PointingHandCursor)
    if func:b.clicked.connect(func)
    return b


def card(title=None):
    f=QFrame();f.setObjectName('card')
    l=QVBoxLayout(f);l.setContentsMargins(16,16,16,16);l.setSpacing(12)
    if title:l.addWidget(txt(title))
    return f,l


def scroll_widget():
    area=QScrollArea();area.setWidgetResizable(True)
    inner=QWidget();v=QVBoxLayout(inner);v.setContentsMargins(0,0,0,0);v.setSpacing(14)
    area.setWidget(inner)
    return area,v


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings=settings_load()
        self.events=queue.Queue(maxsize=70)
        self._video_lock=threading.Lock()
        self._latest_video_packet=None
        self.runtime=Runtime(self.settings,self.post)
        self.spotify=SpotifyConnection()
        self.lab_history=[]
        self.lab_busy=False
        self.net_busy=False
        self.net_last_report=None
        self.v2_busy=False
        self.mobile_server=None
        self.ar=ARStudio(BASE / "Ti_AR_Modeller", self.post, CAPTURES)
        self.ar_place_sticker=None
        self._ar_started_at=0
        self._ar_last_frame_at=0
        self._v2_memory=None
        self._v2_sights=None
        self._v2_proposal_path=None
        self.knowledge=None
        self._privacy_previous=None
        self.router=CommandRouter(self.settings,self.post,self.spotify)
        self.last_frame=None
        self.counter=0;self.changing=False;self.shutting_down=False
        self.last_schedule_date=None
        self.navbuttons=[]
        self.setWindowTitle('Ti AI v2.3 • Cyber SOC')
        self.resize(1560,910)
        self.setMinimumSize(1040,680)
        self.build()
        self.set_theme(self.settings['theme'], save=False)
        self.show_section(0)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(125)
        self.periodic=QTimer(self);self.periodic.timeout.connect(self.periodic_update);self.periodic.start(1000)
        self.reload_logs()
        self.tray=QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        if QSystemTrayIcon.isSystemTrayAvailable():self.tray.show()
        self.log('Ti Kontrol Merkezi hazır. Sistemi başlatabilirsin.')

    def post(self,kind,val=None):
        # Never enqueue video frames: one slot always holds the freshest.
        # Avoids 70-frame memory/latency buildup under UI load.
        if kind == 'frame':
            with self._video_lock:self._latest_video_packet=val
            return
        try:self.events.put_nowait((kind,val))
        except queue.Full:
            try:self.events.get_nowait();self.events.put_nowait((kind,val))
            except queue.Empty:pass

    def log(self,message,kind='Sistem'):
        message=str(message)
        self.runtime.store.add(kind,message)
        self.info_label.setText(message[:130])
        self.reload_logs()

    def build(self):
        root=QWidget();root.setObjectName('root');self.setCentralWidget(root)
        wrap=QVBoxLayout(root);wrap.setContentsMargins(0,0,0,0);wrap.setSpacing(0)
        header=QFrame();hl=QHBoxLayout(header);hl.setContentsMargins(24,12,24,12)
        brand=QLabel('Ti');brand.setFixedSize(42,42);brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet('background:#287af0;border-radius:13px;color:#fff;font-size:21px;font-weight:800;')
        hl.addWidget(brand);hl.addSpacing(8)
        names=QVBoxLayout();names.setSpacing(1);names.addWidget(txt('Ti Kontrol Merkezi',title=True));names.addWidget(txt('Gözlemle. Kontrol et. Seninle.',muted=True))
        hl.addLayout(names);hl.addStretch()
        self.status=txt('● Hazır');self.status.setObjectName('status');hl.addWidget(self.status)
        self.clock=txt('');hl.addSpacing(26);hl.addWidget(self.clock)
        self.theme_button=btn('☾  Gece modu',lambda:self.set_theme('light' if self.settings['theme']=='dark' else 'dark'));hl.addSpacing(18);hl.addWidget(self.theme_button)
        self.settings_button=btn('⚙  Ayarlar',lambda:self.show_section(3));hl.addWidget(self.settings_button)
        wrap.addWidget(header)
        body=QHBoxLayout();body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        wrap.addLayout(body,1)
        sidebar=QFrame();sidebar.setObjectName('sidebar');sidebar.setFixedWidth(184)
        sv=QVBoxLayout(sidebar);sv.setContentsMargins(12,20,12,16);sv.setSpacing(8)
        for i,(icon,name) in enumerate([('⌂','Ana Sayfa'),('▣','Kamera'),('◎','Kontroller'),('⚙','Ayarlar'),('▤','Kayıtlar'),('ⓘ','Hakkında'),('✦','Ti Laboratuvarı'),('✧','Ti v2.3'),('✦','AR Studio'),('🛡','Ağ Güvenliği')]):
            b=btn(f'{icon}   {name}',lambda checked=False,n=i:self.show_section(n),'nav')
            sv.addWidget(b);self.navbuttons.append(b)
        sv.addStretch()
        sv.addWidget(txt('Ti Control Center  •  v2.3',muted=True))
        body.addWidget(sidebar)
        self.stack=QStackedWidget();body.addWidget(self.stack,1)
        self.stack.addWidget(self.make_home())
        self.stack.addWidget(self.make_camera_page())
        self.stack.addWidget(self.make_controls_page())
        self.stack.addWidget(self.make_settings_page())
        self.stack.addWidget(self.make_events_page())
        self.stack.addWidget(self.make_about_page())
        self.stack.addWidget(self.make_lab_page())
        self.stack.addWidget(self.make_v2_page())
        self.stack.addWidget(self.make_ar_page())
        self.stack.addWidget(self.make_network_page())
        footer=QFrame();fl=QHBoxLayout(footer);fl.setContentsMargins(18,6,18,6)
        self.info_label=txt('Bağlantı kurulmadı',muted=True);fl.addWidget(self.info_label,1)
        self.heard_label=txt('Ti henüz bir komut duymadı',muted=True)
        self.heard_label.setMaximumWidth(460);fl.addWidget(self.heard_label)
        wrap.addWidget(footer)

    def make_home(self):
        area,v=scroll_widget()
        col=QHBoxLayout();col.setSpacing(14);v.addLayout(col,1)
        main=QWidget();mv=QVBoxLayout(main);mv.setContentsMargins(0,0,0,0);mv.setSpacing(14)
        right=QWidget();rv=QVBoxLayout(right);rv.setContentsMargins(0,0,0,0);rv.setSpacing(14)
        col.addWidget(main,7);col.addWidget(right,4)
        video,vl=card();main.setMinimumWidth(550)
        top=QHBoxLayout();top.addWidget(txt('▣  Canlı Kamera Görüntüsü'));top.addStretch()
        self.live_badge=txt('● Bağlantı bekleniyor',muted=True);top.addWidget(self.live_badge)
        vl.addLayout(top)
        self.camera_label=QLabel('Kameradan görüntü bekleniyor\n\n▶ Sistemi Başlat düğmesine basın')
        self.camera_label.setObjectName('camera');self.camera_label.setMinimumHeight(345)
        self.camera_label.setAlignment(Qt.AlignCenter);self.camera_label.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        vl.addWidget(self.camera_label,1)
        self.camera_label.installEventFilter(self) # click to select person for tracking
        camrow=QHBoxLayout();camrow.addWidget(txt('Ti Kamera 1  •  Xiaomi C301',muted=True));camrow.addStretch()
        self.fps_label=txt('0 FPS',muted=True);camrow.addWidget(self.fps_label)
        camrow.addWidget(btn('▣ Fotoğraf çek',self.snapshot))
        camrow.addWidget(btn('⛶ Tam ekran',self.fullscreen_preview))
        vl.addLayout(camrow);vl.addWidget(txt('Görüntü sıkışırsa: Ayarlar → Kamera görüş açısı → Orijinal C301. Dijital zoom 1.0x.',muted=True));mv.addWidget(video,3)
        bottom=QHBoxLayout();bottom.setSpacing(14)
        speech,sl=card('◉  Ti’ye Söylet')
        self.speak_text=QTextEdit();self.speak_text.setPlaceholderText('Ti’ye söylemesini istediğin metni yaz...')
        self.speak_text.setMaximumHeight(74);sl.addWidget(self.speak_text)
        row=QHBoxLayout();row.addWidget(txt('Örnek: Merhaba, ben Ti. Hoş geldin.',muted=True));row.addStretch();row.addWidget(btn('▶  Söylet',self.speak,role='primary'));sl.addLayout(row)
        chips=QHBoxLayout()
        for phrase in ('Hoş geldiniz','Sistem hazır','Güvende olun'):
            chips.addWidget(btn(phrase,lambda checked=False,p=phrase:self.speak_text.setPlainText(p)))
        sl.addLayout(chips);bottom.addWidget(speech,5)
        ptz,pl=card('⊕  PTZ Motor Kontrolü')
        grid=QGridLayout();grid.setSpacing(5)
        for r,c,letter,dir_ in [(0,1,'↑','up'),(1,0,'←','left'),(1,2,'→','right'),(2,1,'↓','down')]:
            b=btn(letter,lambda checked=False,d=dir_:self.move(d));b.setMinimumSize(50,35);grid.addWidget(b,r,c)
        grid.addWidget(btn('■',self.stop_follow),1,1)
        pl.addLayout(grid);bottom.addWidget(ptz,3)
        mv.addLayout(bottom,0)
        controls,cl=card('Sistem Kontrolleri')
        row=QHBoxLayout();self.start_button=btn('▶  Sistemi Başlat',self.start,role='green');row.addWidget(self.start_button)
        self.stop_button=btn('■ Durdur',self.stop,role='danger');row.addWidget(self.stop_button);cl.addLayout(row)
        row=QHBoxLayout();row.addWidget(btn('◎ Takibi Başlat',self.start_follow,role='primary'))
        row.addWidget(btn('■ Takibi Durdur',self.stop_follow,role='danger'));cl.addLayout(row)
        tracker_opts=QHBoxLayout()
        tracker_opts.addWidget(txt('Takip dk:',muted=True))
        self.follow_minutes=QSpinBox();self.follow_minutes.setRange(1,30)
        self.follow_minutes.setValue(self.settings.get('follow_minutes',10))
        self.follow_minutes.valueChanged.connect(lambda value:self.update_setting('follow_minutes',value))
        tracker_opts.addWidget(self.follow_minutes)
        tracker_opts.addWidget(txt('Adım/dk:',muted=True))
        self.follow_steps=QSpinBox();self.follow_steps.setRange(1,12)
        self.follow_steps.setValue(self.settings.get('follow_steps_per_minute',4))
        self.follow_steps.valueChanged.connect(lambda value:self.update_setting('follow_steps_per_minute',value))
        tracker_opts.addWidget(self.follow_steps)
        cl.addLayout(tracker_opts)
        cl.addWidget(txt('Takip sürekli yeniden değerlendirir; hareketsiz hedefte 30 sn motor dinlenmesi uygulanır.',muted=True))
        cl.addWidget(txt('Özellikler'))
        self.toggles={}
        for key,label in [('microphone','Mikrofon'),('voice','Ti Konuşma'),('preview','Canlı Görüntü'),
                         ('detection','Nesne Algılama'),('person_only','Sadece Kişi'),('motor','Motor Kontrolü'),
                         ('alert_person','Sesli Kişi Uyarısı'),('desktop_notice','Masaüstü Bildirimi')]:
            self.add_toggle(cl,key,label)
        self.detection_status=txt('YOLO: Kapalı',muted=True)
        cl.addWidget(self.detection_status)
        self.follow_status=txt('Takip: Kapalı',muted=True)
        cl.addWidget(self.follow_status)
        rv.addWidget(controls)
        events,el=card('Son Etkinlikler')
        self.recent=QListWidget();self.recent.setMinimumHeight(245);el.addWidget(self.recent,1)
        el.addWidget(btn('Tüm Kayıtlar',lambda:self.show_section(4)))
        rv.addWidget(events,1)
        v.addStretch(0)
        self._home_scroll=area
        return area

    def add_toggle(self,layout,key,label):
        cb=Switch(label)
        cb.setObjectName('switch_'+key)
        cb.setAccessibleName(label)
        cb.setChecked(bool(self.settings[key]))
        cb.toggled.connect(lambda state,k=key:self.changed_toggle(k,state))
        layout.addWidget(cb)
        self.toggles[key]=cb

    def make_ar_page(self):
        area,v=scroll_widget()
        v.addWidget(txt('Ti AR Studio v2.1 • Yüz Efektleri, Havaya Çizim, 3D Objeler',title=True))
        v.addWidget(txt('Ana kamera/YOLO/PTZ dokunulmadan kalır. AR yalnızca bu sekmede ve sen açınca çalışır. El/yüz modelleri isteğe bağlıdır.',muted=True))
        view,vl=card('AR Canlı Önizleme (işlem arka planda, son kare ilkesi)')
        self.ar_preview=QLabel('Önce Sistemi Başlat, ardından AR Modunu Aç.\nAR modelleri yoksa Modelleri İndir düğmesini kullan.')
        self.ar_preview.setObjectName('camera');self.ar_preview.setMinimumHeight(320)
        self.ar_preview.setAlignment(Qt.AlignCenter)
        self.ar_preview.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding)
        self.ar_preview.installEventFilter(self)
        vl.addWidget(self.ar_preview)
        self.ar_status=txt('AR kapalı',muted=True);vl.addWidget(self.ar_status)
        row=QHBoxLayout()
        row.addWidget(btn('▶ AR Modunu Aç',self.ar_start,role='green'))
        row.addWidget(btn('■ AR Modunu Kapat',self.ar_stop,role='danger'))
        row.addWidget(btn('Modelleri İndir',self.ar_download_models))
        row.addWidget(btn('AR Teşhis',self.ar_diagnose))
        row.addWidget(btn('Görsel Test',self.ar_visual_test))
        vl.addLayout(row)
        vl.addWidget(txt('Görsel Test sadece SENTETİK yüz ve el noktalarıyla çizim motorunu sınar. AR Teşhis gerçek MediaPipe kurulumunu ve modelleri kontrol eder.',muted=True))
        v.addWidget(view)

        effects,el=card('1. Yüz maskeleri ve 3D objeler')
        row=QHBoxLayout();row.addWidget(txt('Yüz filtresi'))
        self.ar_mask=QComboBox();self.ar_mask.addItems(MASKS)
        self.ar_mask.setCurrentText('Muzip yüz (özgün)')
        self.ar_mask.currentTextChanged.connect(lambda value:self.ar.configure(mask=value))
        row.addWidget(self.ar_mask,1)
        row.addWidget(btn('Özel PNG Yükle',self.ar_load_png))
        el.addLayout(row)
        row=QHBoxLayout();row.addWidget(txt('Avuç içi 3D'))
        self.ar_object=QComboBox();self.ar_object.addItems(OBJECTS)
        self.ar_object.setCurrentText('3D Dünya')
        self.ar_object.currentTextChanged.connect(lambda value:self.ar.configure(obj=value))
        row.addWidget(self.ar_object,1)
        el.addLayout(row)
        el.addWidget(txt('Açık avuç: 3D dünya. İki eli açıp uzaklaştır: büyüt; yakınlaştır: küçült. 3D küre ışıklandırmalı matematiksel yüzey olarak çizilir; kamera derinlik sensörü değildir.',muted=True))
        v.addWidget(effects)

        paint,pl=card('2. Havaya Çizim, Renk, Silgi ve Yazı')
        self.ar_draw_on=QCheckBox('Havada çizim açık: işaret parmağı çiz, başparmak+işaret kıstır sil, iki parmak renk değiştir, yumruk duraklat.')
        self.ar_draw_on.setChecked(True)
        self.ar_draw_on.toggled.connect(lambda value:self.ar.configure(drawing_on=value))
        pl.addWidget(self.ar_draw_on)
        row=QHBoxLayout();row.addWidget(txt('Renk'))
        self.ar_colors=QComboBox()
        for label,color in zip(('Sarı','Mavi','Kırmızı','Yeşil','Mor','Beyaz'),COLORS):self.ar_colors.addItem(label,color)
        self.ar_colors.currentIndexChanged.connect(lambda _:self.ar.configure(color=self.ar_colors.currentData()))
        row.addWidget(self.ar_colors)
        row.addWidget(txt('Fırça'))
        self.ar_brush=QSpinBox();self.ar_brush.setRange(1,25);self.ar_brush.setValue(5)
        self.ar_brush.valueChanged.connect(lambda n:self.ar.configure(brush=n))
        row.addWidget(self.ar_brush)
        pl.addLayout(row)
        row=QHBoxLayout()
        row.addWidget(btn('Çizimi Sil',self.ar_clear))
        row.addWidget(btn('Çizimi PNG Kaydet',self.ar_save_drawing))
        row.addWidget(btn('AR Fotoğrafı Çek',self.ar_photo))
        pl.addLayout(row)
        row=QHBoxLayout()
        self.ar_text=QLineEdit();self.ar_text.setPlaceholderText('Ekrana yazı veya imza adı ekle (Türkçe karakterler fonta bağlı)')
        self.ar_text.textChanged.connect(lambda v:self.ar.configure(typed_text=v))
        row.addWidget(self.ar_text)
        pl.addLayout(row)
        v.addWidget(paint)

        stickers,sl=card('3. Sanal Sticker, Lazer, Fotoğraf ve Video')
        row=QHBoxLayout()
        for name in ('Kalp','Yıldız','Ok'):
            row.addWidget(btn('Ekrana '+name,lambda checked=False,k=name:self.ar_choose_sticker(k)))
        sl.addLayout(row)
        sl.addWidget(txt('Sticker düğmesine basıp AR önizlemesinde istediğin noktaya tıkla. Yıldız/kalp/ok çizimleri kayıtlı fotoğrafa da geçer.',muted=True))
        row=QHBoxLayout()
        row.addWidget(btn('● AR Video Kaydını Başlat',self.ar_record_start))
        row.addWidget(btn('■ AR Video Kaydını Bitir',self.ar_record_stop))
        sl.addLayout(row)
        self.ar_gesture_photo=QCheckBox('Başparmak hareketini 2 saniye tutunca otomatik fotoğraf (8 sn bekleme)')
        self.ar_gesture_photo.toggled.connect(lambda val:self.ar.configure(photo_on_thumbs=val))
        sl.addWidget(self.ar_gesture_photo)
        self.ar_gesture_music=QCheckBox('Başparmak hareketiyle medya oynat/duraklat (Windows, 8 sn bekleme)')
        self.ar_gesture_music.toggled.connect(lambda val:self.ar.configure(music_on_thumbs=val))
        sl.addWidget(self.ar_gesture_music)
        self.ar_laser=QCheckBox('İşaret parmağından lazer efekti')
        self.ar_laser.toggled.connect(lambda val:self.ar.configure(laser_on=val))
        sl.addWidget(self.ar_laser)
        self.ar_throw=QCheckBox('Açık avuçtan yumruğa geçince 3D objeyi fırlat')
        self.ar_throw.toggled.connect(lambda val:self.ar.configure(throw_on=val))
        sl.addWidget(self.ar_throw)
        v.addWidget(stickers)

        perf,fl=card('4. Optimizasyon ve Gizlilik')
        row=QHBoxLayout();row.addWidget(txt('AR kare/saniye (CPU sınırı)'))
        self.ar_fps=QSpinBox();self.ar_fps.setRange(4,15);self.ar_fps.setValue(6)
        self.ar_fps.valueChanged.connect(lambda n:self.ar.configure(fps_limit=n))
        row.addWidget(self.ar_fps);fl.addLayout(row)
        fl.addWidget(txt('İşlem 640 piksel genişlik/yükseklik sınırıyla yapılır. Dolu kuyruk yerine en yeni kare alınır. Yüz/el modeli yalnızca ilgili efekt seçilince çalışır. AR kapalıyken model belleği serbest bırakılır.',muted=True))
        fl.addWidget(txt('Uyarı: AR modu ayrı bir ekran görüntüsüdür; gerçek ortamda elin üzerinde fiziksel hologram oluşturmaz. Farklı ışık/pozlarda el tanıma hataları olabilir.',muted=True))
        v.addWidget(perf);v.addStretch()
        return area

    def ar_start(self):
        if not self.runtime.active:
            self.ar_status.setText('Önce ana ekranda Sistemi Başlat.');return
        if not self.settings.get('preview'):
            self.ar_status.setText('Canlı Görüntü kapalı. Ana ekrandan aç.');return
        self.ar.configure(mask=self.ar_mask.currentText(),obj=self.ar_object.currentText(),
                          drawing_on=self.ar_draw_on.isChecked(),color=self.ar_colors.currentData(),
                          brush=self.ar_brush.value(),fps_limit=min(self.ar_fps.value(),4) if self.settings.get('detection') else self.ar_fps.value(),
                          photo_on_thumbs=self.ar_gesture_photo.isChecked(),music_on_thumbs=self.ar_gesture_music.isChecked(),
                          laser_on=self.ar_laser.isChecked(),throw_on=self.ar_throw.isChecked())
        # Refuse to pretend AR is running while required native models are missing.
        need_hand=(self.ar_draw_on.isChecked() or self.ar_object.currentText()!='Kapalı'
                   or self.ar_laser.isChecked() or self.ar_gesture_photo.isChecked()
                   or self.ar_gesture_music.isChecked())
        need_face=self.ar_mask.currentText()!='Kapalı'
        issues=ar_preflight(BASE/'Ti_AR_Modeller',require_hand=need_hand,require_face=need_face)
        if issues:
            self.ar_status.setText('AR BAŞLATILAMADI: '+' | '.join(issues))
            self.log('AR eksik bileşen: '+' | '.join(issues),'AR Hata')
            if not any('MediaPipe kurulu değil' in err for err in issues) and any('.task' in err for err in issues):
                # Consent-gated one-click recovery; never download automatically without permission.
                self.ar_download_models(autostart=True)
            return
        self.ar.max_side=512 if self.settings.get('detection') else 640
        try:self.ar.start()
        except RuntimeError as exc:return self.ar_status.setText(str(exc))
        self._ar_started_at=time.monotonic();self._ar_last_frame_at=0
        self.ar_status.setText('AR modeli başlatılıyor; ilk çalıştırma uzun sürebilir...' + (' 512px / 4 FPS.' if self.settings.get('detection') else ' 640px / 6 FPS.'))

    def ar_stop(self):
        self.ar.set_recording(False);self.ar.stop()
        self.ar_status.setText('AR kapalı, normal kamera/takip çalışmaya devam eder.')

    def ar_diagnose(self):
        """Run native model loading in an isolated subprocess, never the Qt UI thread."""
        script=BASE/'Ti_AR_Teshis.py'
        if not script.is_file():
            self.ar_status.setText('Ti_AR_Teshis.py eksik. AR yamasını yeniden kur.');return
        self.ar_status.setText('AR gerçek model teşhisi arka planda çalışıyor...')
        def job():
            try:
                result=subprocess.run([sys.executable,str(script),'--models'],
                    cwd=str(BASE),capture_output=True,text=True,timeout=90,creationflags=(0x08000000 if os.name=='nt' else 0))
                info=(result.stdout+' '+result.stderr).strip().splitlines()
                summary=' | '.join(info[-5:])[-650:]
                self.post('ar_status',('AR teşhis BAŞARILI: ' if result.returncode==0 else 'AR teşhis HATA: ')+summary)
            except Exception as ex:self.post('ar_status','AR teşhis çalıştırılamadı: '+str(ex)[:200])
        threading.Thread(target=job,daemon=True,name='Ti-AR-Diagnostic').start()

    def ar_visual_test(self):
        """Exercise overlay/QImage display with simulated landmarks, not real inference."""
        try:
            import numpy as np
            from ti_ar_core import Point
            from ti_ar_render import apply_face_mask, draw_object, draw_strokes
            import math
            frame=np.zeros((360,640,3),dtype=np.uint8)
            frame[:]=(38,29,24)
            face=[Point(.5+.105*math.cos(i*2*math.pi/478),.38+.22*math.sin(i*2*math.pi/478)) for i in range(478)]
            face[33]=Point(.43,.38);face[263]=Point(.57,.38)
            apply_face_mask(frame,[face],'Muzip yüz (özgün)')
            draw_object(frame,(485,185),64,'3D Dünya',.8)
            cv2=__import__('cv2')
            cv2.line(frame,(85,270),(165,245),(0,255,255),4,cv2.LINE_AA)
            cv2.putText(frame,'DEMO', (260,331),cv2.FONT_HERSHEY_SIMPLEX,.8,(250,250,250),2,cv2.LINE_AA)
            h,w=frame.shape[:2]
            img=QImage(frame.data,w,h,frame.strides[0],QImage.Format_BGR888).copy()
            self.ar_pixmap=QPixmap.fromImage(img)
            self.ar_preview.setPixmap(self.ar_pixmap.scaled(self.ar_preview.size(),Qt.KeepAspectRatio,Qt.FastTransformation))
            self.ar_status.setText('SENTETİK GÖRSEL TEST: Çizim yolu çalışıyor; gerçek kamera/el/yüz algılaması bu testle doğrulanmaz.')
        except Exception as exc:
            self.ar_status.setText('Görsel test hatası: '+str(exc)[:200])

    def ar_download_models(self,autostart=False):
        if QMessageBox.question(self,'AR Model Dosyaları','Google MediaPipe resmi sunucusundan el ve yüz modelleri indirilsin mi?\nYaklaşık 12 MB. İnternet gerekir.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.ar_status.setText('Model indirme başladı...')
        def worker():
            try:
                downloaded=download_models(BASE/'Ti_AR_Modeller',lambda msg:self.post('ar_status',msg))
                self.post('ar_status','AR model kontrolü tamam. İndirilen: '+(', '.join(downloaded) or 'Mevcut'))
                if autostart:self.post('ar_models_ready',True)
            except Exception as ex:self.post('ar_status','Model indirme hatası: '+str(ex)[:160])
        threading.Thread(target=worker,daemon=True,name='Ti-AR-Download').start()

    def ar_load_png(self):
        file,_=QFileDialog.getOpenFileName(self,'RGBA maske PNG dosyası seç','', 'PNG görselleri (*.png)')
        if not file:return
        try:
            self.ar.configure(custom_png=file,mask='Özel PNG');self.ar_mask.setCurrentText('Özel PNG')
            self.ar_status.setText('Özel maske hazır: '+Path(file).name)
        except Exception as ex:self.ar_status.setText(str(ex))

    def ar_choose_sticker(self,kind):
        self.ar_place_sticker=kind;self.ar_status.setText(kind+' için AR görüntüsüne tıkla.')

    def ar_clear(self):
        self.ar.clear();self.ar_status.setText('Çizim ve stickerlar temizlendi.')

    def ar_save_drawing(self):
        try:self.ar_status.setText('Çizim kaydedildi: '+str(self.ar.save_drawing()))
        except Exception as ex:self.ar_status.setText('Kayıt hatası: '+str(ex))

    def ar_photo(self):
        try:self.ar_status.setText('AR fotoğrafı: '+str(self.ar.save_photo()))
        except Exception as ex:self.ar_status.setText('Fotoğraf hatası: '+str(ex))

    def ar_record_start(self):
        if not self.ar.running:return self.ar_status.setText('Önce AR Modunu Aç.')
        self.ar.set_recording(True);self.ar_status.setText('AR video kaydı başlıyor (sessiz MP4).')

    def ar_record_stop(self):
        self.ar.set_recording(False);self.ar_status.setText('AR video kaydı sonlandırılıyor.')

    def ar_media_key(self):
        if not self.ar_gesture_music.isChecked():return
        if sys.platform!='win32':return self.ar_status.setText('Medya tuşu yalnızca Windows üzerinde destekleniyor.')
        try:
            import ctypes
            VK_MEDIA_PLAY_PAUSE=0xB3
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE,0,0,0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE,0,2,0)
            self.ar_status.setText('Windows oynat/duraklat tuşu gönderildi.')
        except Exception as ex:self.ar_status.setText('Medya tuşu hatası: '+str(ex)[:130])

    def ar_poll(self):
        if not self.ar.running:return
        item=self.ar.pop_frame()
        if item is None and self._ar_last_frame_at==0 and time.monotonic()-self._ar_started_at>5:
            self.ar_status.setText('AR için kamera karesi gelmedi (5+ sn). Ana sayfada Canlı Görüntü, go2rtc bağlantısı ve AR Teşhis kontrol edilmeli.')
        if item is not None:
            frame,status=item
            h,w=frame.shape[:2]
            qimg=QImage(frame.data,w,h,frame.strides[0],QImage.Format_BGR888).copy()
            self.ar_pixmap=QPixmap.fromImage(qimg)
            self.ar_preview.setPixmap(self.ar_pixmap.scaled(self.ar_preview.size(),Qt.KeepAspectRatio,Qt.FastTransformation))
            self._ar_last_frame_at=time.monotonic()
            # Do not hide model load errors behind the latest video frame.
            self.ar_status.setText(status)

    def make_network_page(self):
        area,v=scroll_widget()
        v.addWidget(txt('Ti Ağ Güvenliği • Savunma ve Trafik Teşhisi',title=True))
        v.addWidget(txt('Yalnızca kendi bilgisayarında veya izleme izni bulunan ağda kullan. Ti arka planda dinleme başlatmaz; kısa süreli örnekleme için düğmeye basman gerekir.',muted=True))
        header,hl=card('IP ve uygulama bağlantıları')
        line=QHBoxLayout()
        line.addWidget(btn('Yerel IP Bilgilerim',lambda:self.net_launch('ip'),role='primary'))
        line.addWidget(btn('Bu PC Bağlantıları',lambda:self.net_launch('connections')))
        line.addWidget(btn('Yerel ARP Komşuları',lambda:self.net_launch('arp')))
        line.addWidget(btn('Genel IP Sorgula',self.net_public_ip))
        hl.addLayout(line)
        hl.addWidget(txt('ARP, geçmişte görülmüş cihazları gösterir; ağdaki tüm bağlı kullanıcıların listesi değildir. Genel IP sorgusu üçüncü taraf ipify servisine isteğe bağlı istek gönderir.',muted=True))
        v.addWidget(header)
        capture,cl=card('Wireshark / TShark • Kısıtlı ve izinli canlı analiz')
        cl.addWidget(txt('Yakalama: 12 saniye, en çok 800 satır, promiscuous kapalı; ham paket kaydı yok. Seçilen ağ arayüzünde DNS, TLS SNI, IP ve port metaverisi değerlendirilir.',muted=True))
        r=QHBoxLayout()
        self.net_adapter=QComboBox();self.net_adapter.addItem('Önce adaptörleri listele',None)
        r.addWidget(self.net_adapter,1)
        r.addWidget(btn('Adaptörleri Listele',lambda:self.net_launch('adaptors')))
        r.addWidget(btn('12 sn Trafiği Analiz Et',self.net_capture,role='primary'))
        cl.addLayout(r)
        cl.addWidget(txt('Ağda saldırı olmadığını kanıtlamaz. Port taraması gibi yalnızca şüpheli örüntüleri belirtir. HTTPS, VPN, DoH ve ECH tam site/URL geçmişini gizleyebilir.',muted=True))
        v.addWidget(capture)
        result,rl=card('Teşhis ve son rapor')
        self.net_state=txt('Henüz tarama yapılmadı.',muted=True);rl.addWidget(self.net_state)
        self.net_output=QTextEdit();self.net_output.setReadOnly(True);self.net_output.setMinimumHeight(280)
        self.net_output.setPlainText('Önce Yerel IP Bilgilerim veya Adaptörleri Listele düğmesine bas.')
        rl.addWidget(self.net_output)
        rl.addWidget(btn('Son raporu JSON dışa aktar (isteğe bağlı)',self.net_export))
        v.addWidget(result)
        cyber_box,cb=card('ZTE H3600 • Cihaz Envanteri (manuel JSON)')
        cb.addWidget(txt('Topoloji sayfasının Response JSON içeriğini yerel olarak içe aktar. Otomatik modem oturumu henüz yok; veriler Ti bilgisayarından dışarı gönderilmez.',muted=True))
        rr=QHBoxLayout()
        rr.addWidget(btn('Panodan Topoloji JSON İçe Aktar',self.cyber_import_clipboard,role='primary'))
        rr.addWidget(btn('JSON Dosyası Aç',self.cyber_import_file))
        rr.addWidget(btn('Son Envanteri Göster',self.cyber_show_devices))
        cb.addLayout(rr)
        self.cyber_status=txt('İlk içe aktarım başlangıç listesi olacak.',muted=True);cb.addWidget(self.cyber_status)
        self.cyber_output=QTextEdit();self.cyber_output.setReadOnly(True);self.cyber_output.setMinimumHeight(200)
        self.cyber_output.setPlainText('Chrome Network → Topoloji menuData isteği → Response → Copy response. Sonra bu düğmeye bas.')
        cb.addWidget(self.cyber_output)
        v.addWidget(cyber_box)
        return area

    @staticmethod
    def _net_format_report(title,payload):
        import json
        if title=='capture':
            domains=payload.get('observed_domains',[])
            alerts=payload.get('alerts',[])
            lines=['Tİ AĞ ANALİZ RAPORU',f"Gözlenen paket sayısı: {payload.get('packet_count',0)}",
                   payload.get('conclusion',''),'', 'ŞÜPHE GÖSTERGELERİ:']
            lines += [f"- {a['tur']}: {a['aciklama']}" for a in alerts] or ['- Bu kısa örneklemde kural eşiği aşılmadı.']
            lines += ['', 'GÖZLENEN ALAN ADLARI (ziyaret kanıtı değil):']
            lines += [f'- {name} ({count} alan adı alanı görüldü)' for name,count in domains[:25]] or ['- Görünür DNS/SNI/HTTP host verisi yok.']
            lines += ['', 'EN SIK GÖRÜLEN IP ÇİFTLERİ:']
            lines += [f"- {p['src']} → {p['dst']} ({p['packets']} paket)" for p in payload.get('ip_pairs',[])[:15]]
            lines += ['',payload.get('limits','')]
            return '\n'.join(lines)
        if title=='connections':
            lines=['BU BİLGİSAYARDA AÇIK AĞ BAĞLANTILARI', 'Başka cihazların tarayıcı geçmişi değildir.', '']
            lines += [f"{r['uygulama']} [PID {r['pid']}]  {r['yerel']} → {r['uzak']}  ({r['durum']})" for r in payload]
            return '\n'.join(lines)
        return title+'\n'+json.dumps(payload,ensure_ascii=False,indent=2)

    def net_launch(self,mode):
        if self.net_busy:return self.net_state.setText('Önceki ağ işlemi sürüyor.')
        self.net_busy=True;self.net_state.setText('Çalışıyor: '+mode)
        def task():
            try:
                funcs={'ip':netguard.ip_inventory,'connections':netguard.local_connections,
                       'arp':netguard.arp_neighbors,'adaptors':netguard.interfaces,
                       'public':netguard.public_ip_lookup}
                answer=funcs[mode]()
                self.post('net_result',(mode,answer))
            except Exception as ex:self.post('net_error',str(ex)[:600])
        threading.Thread(target=task,daemon=True,name='Ti-Network-'+mode).start()

    def net_public_ip(self):
        answer=QMessageBox.question(self,'Dış IP için izin',
            'Genel IP adresini öğrenmek için https://api.ipify.org adresine istek gönderilecek. Devam edilsin?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer==QMessageBox.Yes:self.net_launch('public')

    def net_capture(self):
        interface=self.net_adapter.currentData()
        if not interface:return self.net_state.setText('Önce adaptörleri listele ve seç.')
        answer=QMessageBox.question(self,'İzinli ağ analizi',
            'Yalnızca yetkili olduğun ağda, seçilen adaptörü 12 saniye pasif olarak gözlemleyeceğiz. '
            'Ham paket kaydedilmez; görünen alan adları hassas olabilir. Başlatılsın mı?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer!=QMessageBox.Yes:return
        if self.net_busy:return
        self.net_busy=True;self.net_state.setText('TShark örnekleme çalışıyor (12 saniye).')
        def task():
            try:
                ips=netguard.ip_inventory()['local_ips']
                result=netguard.capture(interface,local_ips=ips)
                self.post('net_result',('capture',result))
            except Exception as ex:self.post('net_error',str(ex)[:600])
        threading.Thread(target=task,daemon=True,name='Ti-TShark-OptIn').start()

    def net_export(self):
        if self.net_last_report is None:
            return self.net_state.setText('Henüz dışa aktarılabilecek rapor yok.')
        path,_=QFileDialog.getSaveFileName(self,'Ağ güvenliği raporu',str(BASE/'Ti_Ag_Raporu.json'),'JSON (*.json)')
        if path:
            try:
                dest=netguard.export_json(path,self.net_last_report)
                self.net_state.setText('Dışa aktarıldı: '+str(dest))
            except Exception as ex:self.net_state.setText('Rapor hatası: '+str(ex)[:200])

    def cyber_import_clipboard(self):
        # User initiated only. Clipboard contents are parsed in memory, never logged.
        payload=QApplication.clipboard().text()
        self.cyber_import_text(payload)

    def cyber_import_file(self):
        selected,_=QFileDialog.getOpenFileName(self,'ZTE Topoloji JSON Seç',str(BASE),'JSON (*.json);;Metin (*.txt)')
        if not selected:return
        try:
            from pathlib import Path
            target=Path(selected)
            if target.stat().st_size>1_500_000:raise ValueError('Dosya 1,5 MB sınırını aşıyor.')
            self.cyber_import_text(target.read_text(encoding='utf-8-sig'))
        except Exception as ex:self.cyber_status.setText('Dosya hatası: '+str(ex)[:140])

    def cyber_import_text(self,raw):
        try:
            outcome=cyberinv.import_snapshot(raw,DATA/'ti_cyber_inventory.sqlite3')
            label=('İlk kayıt: ' if outcome['baseline'] else 'Envanter güncellendi: ')
            label+=f"{outcome['count']} cihaz, {outcome['new_count']} yeni kimlik."
            self.cyber_status.setText(label)
            self.cyber_output.setPlainText(cyberinv.describe(outcome))
            if outcome['new_count']:
                self.log(f"Topoloji içe aktarımında {outcome['new_count']} yeni cihaz kimliği. Ağ saldırısı kanıtı değildir.",'Cyber SOC')
        except Exception as ex:
            self.cyber_status.setText('JSON içe aktarma hatası: '+str(ex)[:180])

    def cyber_show_devices(self):
        try:
            state=cyberinv.latest(DATA/'ti_cyber_inventory.sqlite3')
            self.cyber_output.setPlainText(cyberinv.describe(state))
            self.cyber_status.setText(state.get('note','Son aktarım görüntülendi.'))
        except Exception as ex:self.cyber_status.setText('Envanter okuma hatası: '+str(ex)[:140])

    def make_camera_page(self):
        a,v=scroll_widget();v.addWidget(txt('Kamera ve Kayıtlar',title=True))
        control,cl=card('Kamera komutları')
        row=QHBoxLayout()
        for label,fn in [('Fotoğraf çek',self.snapshot),('Video kaydı başlat',self.record_start),('Kaydı durdur',self.record_stop),
                          ('Kayıt klasörü',lambda:self.do_open('camera_folder'))]:row.addWidget(btn(label,fn))
        cl.addLayout(row)
        cl.addWidget(txt('Fotoğraf ve video kayıtları Ti_Kayitlar klasörüne kaydedilir. Video gerçek RTSP görüntüsünden alınır.',muted=True))
        privacy,pr=card('Hızlı Gizlilik Kilidi')
        self.privacy_button=btn('Gizlilik Modunu Aç (Kamera ve Mikrofonu Durdur)',self.toggle_privacy)
        pr.addWidget(self.privacy_button)
        pr.addWidget(txt('Açıldığında önizleme, YOLO, mikrofon ve otomatik fotoğraf çekimi kapatılır; canlı RTSP okuması bırakılır. Tekrar açınca önceki düğme durumları geri yüklenir.',muted=True))
        v.addWidget(privacy)
        v.addWidget(control)
        zoom,zl=card('Yakınlaştırma ve görüntü düzeltme')
        zl.addWidget(txt('Dijital yakınlaştırma (optik zoom değil)',muted=True))
        self.zoom=QSlider(Qt.Horizontal);self.zoom.setRange(10,30);self.zoom.setValue(round(self.settings['digital_zoom']*10))
        self.zoom.valueChanged.connect(self.change_zoom)
        zl.addWidget(self.zoom)
        self.zoom_text=txt(f"{self.settings['digital_zoom']:.1f}x",muted=True);zl.addWidget(self.zoom_text)
        zl.addWidget(txt('Yazılımsal netlik / keskinlik (kameranın optik odağı değil)',muted=True))
        self.sharpen=QSlider(Qt.Horizontal);self.sharpen.setRange(0,3);self.sharpen.setValue(int(self.settings['sharpen']))
        self.sharpen.valueChanged.connect(lambda x:self.update_setting('sharpen',x))
        zl.addWidget(self.sharpen);v.addWidget(zoom)
        explanation,ex=card('PTZ hakkında')
        ex.addWidget(txt('Dört yön tuşu gerçek Xiaomi motoruna yalnızca tek adım gönderir. Kamera modelinde motorlu optik yakınlaştırma, manuel odak ve donanımsal hız API’si doğrulanmadı. Bu kontroller bu yüzden dijital olarak sunulur.',muted=True))
        v.addWidget(explanation);v.addStretch()
        return a

    def make_controls_page(self):
        a,v=scroll_widget();v.addWidget(txt('Komutlar ve Kontroller',title=True))
        actions,al=card('Windows ve Medya')
        g=QGridLayout();entries=[('Spotify', 'spotify'),('YouTube','youtube'),('GitHub','github'),('Tarayıcı','browser'),
           ('Not Defteri','notepad'),('Hesap Makinesi','calculator'),('Dosya Gezgini','explorer'),('Görev Yöneticisi','taskmgr')]
        for idx,(title,target) in enumerate(entries):g.addWidget(btn('↗ '+title,lambda checked=False,t=target:self.do_open(t)),idx//4,idx%4)
        al.addLayout(g)
        controls=QHBoxLayout()
        for key,title in [('play','▶ / ⏸'),('previous','⏮'),('next','⏭'),('down','Ses -'),('up','Ses +'),('mute','Sessize al')]:
            controls.addWidget(btn(title,lambda checked=False,k=key:self.send_media(k)))
        al.addLayout(controls)
        al.addWidget(txt('Spotify’da şarkı araması açılır. Arama sonucunu otomatik oynatmak için resmi Spotify OAuth/Premium bağlantısı gerekir.',muted=True))
        v.addWidget(actions)
        cmds,cl=card('Ti ile konuşabileceğin örnekler')
        sentences=['Merhaba Ti','Ti nasılsın','Ti sistem durumu ne','Ti saat kaç','Ti tarih ne',
            'Ti Spotify aç','Ti Sezen Aksu Gülümse şarkısını aç','Ti sonraki şarkı','Ti müziği durdur',
            'Ti sesi yükselt','Ti sesini kıs','Ti Chrome aç','Ti not defterini aç',
            'Ti Google aç','Ti YouTube aç','Ti RAM kullanımını söyle','Ti pil kaç',
            'Ti koyu tema aç','Ti açık tema','Ti fotoğraf çek','Ti kaydı başlat',
            'Ti kaydı durdur','Ti nesne algılamayı aç','Ti sadece kişileri göster',
            'Ti sola dön','Ti sağa dön','Ti yukarı bak','Ti aşağı bak','Ti beni takip et','Ti takibi durdur',
            'Ti hava durumu nasıl','Ti bilgisayarı kapat']
        for text in sentences:
            row=QHBoxLayout();row.addWidget(QLabel('•  '+text),1)
            row.addWidget(btn('Dene',lambda checked=False,s=text:self.test_command(s)))
            cl.addLayout(row)
        v.addWidget(cmds);v.addStretch()
        return a

    def make_settings_page(self):
        a,v=scroll_widget();v.addWidget(txt('Ayarlar',title=True))
        appearance,ap=card('Görünüm ve profiller')
        row=QHBoxLayout();row.addWidget(btn('☀ Açık tema',lambda:self.set_theme('light')))
        row.addWidget(btn('☾ Koyu tema',lambda:self.set_theme('dark')));ap.addLayout(row)
        row=QHBoxLayout()
        for item in ['Ev','Gece','Sessiz']:
            row.addWidget(btn(item+' profili',lambda checked=False,p=item:self.apply_profile(p)))
        ap.addLayout(row);v.addWidget(appearance)
        autos,asol=card('Olay fotoğrafı ve bildirim')
        self.auto_snap=QCheckBox('Kişi algılanınca otomatik fotoğraf çek (25 sn aralıklı)')
        self.auto_snap.setChecked(self.settings['auto_snapshot'])
        self.auto_snap.toggled.connect(lambda x:self.update_setting('auto_snapshot',x))
        asol.addWidget(self.auto_snap)
        v.addWidget(autos)
        mic,ml=card('Mikrofon ve YOLO')
        form=QFormLayout()
        self.model=QComboBox();self.model.addItems(['tiny','base','small']);self.model.setCurrentText(self.settings['whisper'])
        form.addRow('Türkçe tanıma modeli',self.model)
        self.threshold=QSpinBox();self.threshold.setRange(80,3000);self.threshold.setValue(int(self.settings['threshold']))
        form.addRow('Mikrofon ses eşiği',self.threshold)
        self.confidence=QDoubleSpinBox();self.confidence.setRange(.15,.90);self.confidence.setSingleStep(.05);self.confidence.setValue(self.settings['confidence'])
        form.addRow('YOLO güven eşiği',self.confidence)
        self.source=QComboBox()
        self.source.addItem('GENİŞ AÇI • Orijinal C301 (önerilen)', 'rtsp://127.0.0.1:8554/c301')
        self.source.addItem('H.264 yazılım dönüşümü', 'rtsp://127.0.0.1:8554/c301_h264')
        self.source.addItem('H.264 donanım • Dar kadraj olabilir', 'rtsp://127.0.0.1:8554/c301_h264_hw')
        selection=self.source.findData(self.settings['video_source'])
        self.source.setCurrentIndex(max(0,selection))
        form.addRow('Kamera görüş açısı / akış',self.source)
        self.city=QLineEdit(self.settings['city']);form.addRow('Hava durumu şehri',self.city)
        self.move_delay=QSpinBox();self.move_delay.setRange(3,8);self.move_delay.setValue(self.settings['manual_move_pause'])
        form.addRow('PTZ komut arası bekleme (sn)',self.move_delay)
        ml.addLayout(form)
        presets=QHBoxLayout()
        for level,conf in [('Hassas (.25)',.25),('Dengeli (.45)',.45),('Sakin (.70)',.70)]:
            presets.addWidget(btn(level,lambda checked=False,c=conf:self.apply_confidence_preset(c)))
        ml.addLayout(presets)
        ml.addWidget(btn('Bu ayarları kaydet',self.save_advanced,role='primary'))
        ml.addWidget(txt('Önerilen: Orijinal C301 geniş açı. Bu akış yaklaşık 848×480 çözünürlüktedir. Görüş açısı için Xiaomi Home ile karşılaştırın. Akış değişikliği sistemi yeniden başlatınca uygulanır.',muted=True))
        v.addWidget(mic)
        chat,chatl=card('İnsansı konuşma — İsteğe bağlı yerel yapay zekâ')
        self.llm_check=QCheckBox('Ollama yerel sohbet modelini kullan (bilinmeyen komutlarda)')
        self.llm_check.setChecked(self.settings['llm_enabled']);chatl.addWidget(self.llm_check)
        self.llm_model=QLineEdit(self.settings['llm_model'])
        chatl.addWidget(txt('Yerel model adı (örn. llama3.2:3b)',muted=True));chatl.addWidget(self.llm_model)
        self.persona=QComboBox();self.persona.addItems(['Samimi','Resmi','Kısa'])
        self.persona.setCurrentText(self.settings['voice_personality']);chatl.addWidget(self.persona)
        chatl.addWidget(btn('Sohbet ayarlarını kaydet',self.save_llm,role='primary'))
        chatl.addWidget(txt('Ollama kurulu ve model bilgisayara indirilmiş olmalı. Ses sentezi hâlâ gTTS üzerinden internete metin gönderir. Ti, gerçek insan değil yazılımdır.',muted=True))
        v.addWidget(chat)
        spotify_box,spl=card('Spotify hesabı bağlantısı')
        spl.addWidget(txt('Spotify Developer Client ID (şifre değil)',muted=True))
        self.spotify_id=QLineEdit(self.settings.get('spotify_client_id',''))
        self.spotify_id.setPlaceholderText('Spotify Developer uygulamasının Client ID değeri')
        spl.addWidget(self.spotify_id)
        row=QHBoxLayout();row.addWidget(btn('Spotify hesabını bağla',self.connect_spotify,role='primary'))
        row.addWidget(btn('Bağlantıyı kes',self.disconnect_spotify));spl.addLayout(row)
        spl.addWidget(txt('Spotify Developer panelinde Redirect URI: http://127.0.0.1:8795/callback. Spotify Premium ve aktif cihaz gerekir. Bağlanırken resmi Spotify sayfası açılır; hesap şifreni Ti içine yazma. Token yalnızca uygulama açıkken bellekte saklanır.',muted=True))
        v.addWidget(spotify_box)
        learn,ll=card('Ti’ye yeni komut öğret')
        ll.addWidget(txt('Kişisel komut (Ti kelimesi olmadan):',muted=True))
        self.learn_phrase=QLineEdit();self.learn_phrase.setPlaceholderText('örnek: bana motivasyon ver');ll.addWidget(self.learn_phrase)
        self.learn_reply=QLineEdit();self.learn_reply.setPlaceholderText('örnek: Bugün güzel şeyler başaracaksın.');ll.addWidget(self.learn_reply)
        row=QHBoxLayout();row.addWidget(btn('Komutu kaydet',self.save_learned,role='primary'))
        row.addWidget(btn('Öğretilenleri göster',self.show_learned));ll.addLayout(row)
        v.addWidget(learn)
        schedule,sh=card('Günlük zamanlı seslendirme')
        self.schedule_check=QCheckBox('Günlük hatırlatıcıyı etkinleştir');self.schedule_check.setChecked(self.settings['schedule_enabled'])
        sh.addWidget(self.schedule_check)
        self.schedule_time=QLineEdit(self.settings['scheduled_time']);self.schedule_time.setPlaceholderText('09:00');sh.addWidget(self.schedule_time)
        self.schedule_message=QLineEdit(self.settings['scheduled_speech']);self.schedule_message.setPlaceholderText('Ti bu saatte ne söylesin?');sh.addWidget(self.schedule_message)
        sh.addWidget(btn('Hatırlatıcıyı kaydet',self.save_schedule,role='primary'))
        sh.addWidget(txt('Bu hatırlatıcı yalnızca Ti Kontrol Merkezi açık ve hoparlör bağlantısı hazırken çalışır.',muted=True))
        v.addWidget(schedule);v.addStretch()
        return a

    def make_events_page(self):
        a,v=scroll_widget();v.addWidget(txt('Olay Kayıtları',title=True))
        container,l=card('Sistem, kamera ve komut geçmişi')
        row=QHBoxLayout();row.addWidget(btn('Yenile',self.reload_logs))
        row.addWidget(btn('CSV dışa aktar',self.export_events))
        row.addWidget(btn('JSON dışa aktar',self.export_events_json));row.addStretch();l.addLayout(row)
        self.events_filter=QLineEdit();self.events_filter.setPlaceholderText('Kayıtlarda ara (ör. Takip, YOLO, kişi)')
        self.events_filter.textChanged.connect(self.reload_logs)
        l.addWidget(self.events_filter)
        self.events_table=QTableWidget(0,3);self.events_table.setHorizontalHeaderLabels(['Tarih / Saat','Tür','Açıklama'])
        self.events_table.horizontalHeader().setStretchLastSection(True);self.events_table.setColumnWidth(0,190)
        self.events_table.setColumnWidth(1,115);self.events_table.setMinimumHeight(450)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        l.addWidget(self.events_table);v.addWidget(container);v.addStretch()
        return a

    def make_about_page(self):
        a,v=scroll_widget();v.addWidget(txt('Ti Control Center',title=True))
        p,pl=card('Kişisel güvenlik ve asistan sistemi')
        pl.addWidget(txt('Windows üzerinde yerel Xiaomi C301 kamera görüntüsü, YOLO kişi/nesne tanıma, motor kontrolü, Faster-Whisper Türkçe algılama, gTTS ile kameradan konuşma ve isteğe bağlı Ollama sohbeti.',muted=True))
        pl.addWidget(txt('Gizlilik: Mikrofon konuşması varsayılan olarak kaydedilmez. Fotoğraf/video yalnızca sen kayıt başlattığında dosyaya yazılır. Olaylar yerel SQLite veritabanına kaydedilir. gTTS çevrimiçi hizmet kullanır.',muted=True))
        pl.addWidget(txt('Kamera güvenlik belirteçleri bu uygulamanın ayarlarına eklenmez. go2rtc.yaml dosyasını ve günlüklerdeki gizli URL’leri GitHub’a yükleme.',muted=True))
        pl.addWidget(txt('Donanım özellikleri: C301’de optik zoom/manuel fokus ve sesin geldiği yönü bulma bu uygulamada desteklenmiyor. Ekrandaki yakınlaştırma dijitaldir.',muted=True))
        pl.addWidget(txt('Sürüm 2.0 • PY Side6 / RTSP / YOLO / Home Assistant / açık rızalı AI bağlantıları',muted=True))
        v.addWidget(p);v.addStretch();return a

    def make_lab_page(self):
        area,v=scroll_widget();v.addWidget(txt('Ti Laboratuvarı • Araştırma ve Gelişim',title=True))
        chat,c=card('Ti ile sohbet / internette araştırma')
        c.addWidget(txt('Sohbet: OPENAI_API_KEY veya Ayarlar’dan açık Ollama. İnternet araştırması yalnızca OpenAI API ile çalışır; ücret doğabilir. Sorular API sağlayıcısına gönderilir. Kamera, mikrofon ve kişisel dosyalar gönderilmez.',muted=True))
        self.lab_key=QLineEdit();self.lab_key.setPlaceholderText('OpenAI API anahtarı (isteğe bağlı, kaydedilmez)')
        self.lab_key.setEchoMode(QLineEdit.Password)
        c.addWidget(self.lab_key)
        self.lab_question=QTextEdit();self.lab_question.setPlaceholderText('Ti, merhaba! ...')
        self.lab_question.setMaximumHeight(85);c.addWidget(self.lab_question)
        row=QHBoxLayout()
        row.addWidget(btn('Ti’ye Sor',lambda:self.ai_request('chat'),role='primary'))
        row.addWidget(btn('İnternette Araştır',lambda:self.ai_request('research')))
        row.addWidget(btn('Gelişim Planı Öner',lambda:self.ai_request('improve')))
        c.addLayout(row)
        self.lab_answer=QTextEdit();self.lab_answer.setReadOnly(True)
        self.lab_answer.setPlaceholderText('Ti yanıtları burada görünecek.');self.lab_answer.setMinimumHeight(240)
        c.addWidget(self.lab_answer)
        c.addWidget(btn('Bu oturumun sohbetini .md kaydet',self.export_lab_chat))
        v.addWidget(chat)
        notes,n=card('Ti yerel bilgi defteri')
        n.addWidget(txt('Notları yalnızca sen kaydedersin; yerel SQLite’da kalır, modele otomatik gönderilmez.',muted=True))
        self.note_title=QLineEdit();self.note_title.setPlaceholderText('Not başlığı');n.addWidget(self.note_title)
        self.note_body=QTextEdit();self.note_body.setPlaceholderText('Unutulmaması gereken teknik bilgi...')
        self.note_body.setMaximumHeight(110);n.addWidget(self.note_body)
        row=QHBoxLayout();row.addWidget(btn('Notu Kaydet',self.lab_save_note,role='primary'))
        row.addWidget(btn('Notları Göster',self.lab_search_notes));n.addLayout(row)
        self.note_search=QLineEdit();self.note_search.setPlaceholderText('Notlarda ara...')
        self.note_search.returnPressed.connect(self.lab_search_notes);n.addWidget(self.note_search)
        self.note_results=QTextEdit();self.note_results.setReadOnly(True)
        self.note_results.setMinimumHeight(110);n.addWidget(self.note_results)
        v.addWidget(notes)
        diag,d=card('Performans ve Sistem Sağlığı')
        self.lab_diag=QTextEdit();self.lab_diag.setReadOnly(True)
        self.lab_diag.setMinimumHeight(140);d.addWidget(self.lab_diag)
        row=QHBoxLayout();row.addWidget(btn('Sağlığı Yenile',self.refresh_diag,role='primary'))
        row.addWidget(btn('Tanı Raporu .md',self.export_lab_diag));d.addLayout(row)
        v.addWidget(diag);v.addStretch()
        return area

    def make_v2_page(self):
        area,v=scroll_widget();v.addWidget(txt('Ti AI v2.0 • Gelişmiş Özellikler',title=True))
        v.addWidget(txt('Tüm dış bağlantılar isteğe bağlıdır. Mobil ağ, görsel analiz, Telegram ve Home Assistant için kullanıcı izinleri gerekir.',muted=True))
        targets,c=card('1–2 • Kişi seçimi ve güvenli motor kalibrasyonu')
        c.addWidget(txt('Ana sayfadaki canlı görüntüde kişinin üzerine tıkla: Ti yalnızca seçilen kişi kimliğini takip eder. Kimlik kaybolursa motor durur. Donanım hareketi garantisi yoktur.',muted=True))
        line=QHBoxLayout();line.addWidget(btn('Hedefi Temizle',lambda:self.runtime.follow_controller.clear_target()))
        line.addWidget(btn('Motor Kalibrasyon Raporu',self.v2_calibration));c.addLayout(line)
        self.v2_calib=txt('Kalibrasyon için gerçek PTZ hareketi gerekli',muted=True);c.addWidget(self.v2_calib);v.addWidget(targets)
        shortcuts,c=card('3 • Güvenli Windows Komutları')
        line=QHBoxLayout()
        for label,target in [('Spotify','spotify'),('Chrome','chrome'),('İndirilenler','downloads_folder'),('Ekran Resmi','desktop_screenshot')]:
            line.addWidget(btn(label,lambda checked=False,x=target:self.v2_shortcut(x)))
        c.addLayout(line);v.addWidget(shortcuts)
        ai,c=card('4–6–8–9 • Ti Developer, görsel soru ve görev ajanları')
        c.addWidget(txt('Görsel soru göndermek için önce onay verilir: o anki kamera JPEG karesi bulut API’sine gönderilir. Konuşma hafızası isteğe bağlı ve yereldir.',muted=True))
        self.v2_agent=QComboBox()
        for key in AGENTS:self.v2_agent.addItem(key.title(),key)
        c.addWidget(self.v2_agent)
        self.v2_memory_opt=QCheckBox('Bu sohbette yerel konuşma hafızasını kullan (izinli)');c.addWidget(self.v2_memory_opt)
        self.v2_prompt=QTextEdit();self.v2_prompt.setPlaceholderText('Ti, masada ne var? / Kodumu nasıl geliştirebilirim?')
        self.v2_prompt.setMaximumHeight(85);c.addWidget(self.v2_prompt)
        line=QHBoxLayout()
        line.addWidget(btn('Ajanla Sohbet Et',lambda:self.v2_query('chat'),role='primary'))
        line.addWidget(btn('Görüntüye Sor',lambda:self.v2_query('vision')))
        line.addWidget(btn('Geliştirici Önerisi .md',lambda:self.v2_query('developer')))
        c.addLayout(line)
        line=QHBoxLayout()
        line.addWidget(btn('GitHub Taslak PR Oluştur (Onaylı)',self.v2_github_pr))
        c.addLayout(line)
        c.addWidget(btn('Yerel Sohbet Hafızasını Sil',self.v2_clear_memory))
        self.v2_result=QTextEdit();self.v2_result.setReadOnly(True);self.v2_result.setMinimumHeight(155)
        c.addWidget(self.v2_result);v.addWidget(ai)
        history,c=card('5–11 • Görsel olay hafızası ve kayıt arama')
        c.addWidget(txt('Algılanan olaylar zaman damgasıyla yerel veritabanındadır. İsteğe bağlı otomatik fotoğraf için Ayarlar → Otomatik Fotoğraf açılabilir.',muted=True))
        self.v2_find=QLineEdit();self.v2_find.setPlaceholderText('Ara: kişi, hareket, fotoğraf...')
        c.addWidget(self.v2_find)
        self.v2_clip_opt=QCheckBox('Kişi algılanınca 6 saniyelik olay videosu kaydet (disk alanı kullanır)')
        self.v2_clip_opt.setChecked(self.settings.get('event_clip',False))
        self.v2_clip_opt.toggled.connect(lambda val:self.update_setting('event_clip',val))
        c.addWidget(self.v2_clip_opt)
        c.addWidget(btn('Olay Hafızasında Ara',self.v2_search_sights))
        self.v2_sight_result=QTextEdit();self.v2_sight_result.setReadOnly(True)
        self.v2_sight_result.setMinimumHeight(100);c.addWidget(self.v2_sight_result);v.addWidget(history)
        alerts,c=card('7–13 • Telefon bildirimi ve Home Assistant')
        c.addWidget(txt('Telegram: TI_TELEGRAM_BOT_TOKEN ve TI_TELEGRAM_CHAT_ID ortam değişkenleriyle. Home Assistant: TI_HOME_ASSISTANT_URL ve TI_HOME_ASSISTANT_TOKEN; yalnızca light/switch toggle.',muted=True))
        self.v2_telegram_opt=QCheckBox('Kişi algılanınca Telegram bildirimi (açık rıza)')
        self.v2_telegram_opt.setChecked(self.settings.get('telegram_notice',False))
        self.v2_telegram_opt.toggled.connect(lambda val:self.update_setting('telegram_notice',val))
        c.addWidget(self.v2_telegram_opt)
        c.addWidget(btn('Telegram Test Bildirimi Gönder',self.v2_telegram_test))
        self.v2_ha_entity=QLineEdit();self.v2_ha_entity.setPlaceholderText('light.salon veya switch.masa')
        c.addWidget(self.v2_ha_entity);c.addWidget(btn('Cihazı Aç/Kapat (Onaylı)',self.v2_ha_toggle))
        v.addWidget(alerts)
        mobile,c=card('12 • Mobil Kontrol: Yetkili Web Paneli')
        c.addWidget(txt('Varsayılan yalnızca bu bilgisayar (127.0.0.1). Telefon/LAN için geçerli TLS sertifikası gerekir; doğrudan şifresiz LAN açılmaz.',muted=True))
        self.v2_web_token=QLineEdit();self.v2_web_token.setEchoMode(QLineEdit.Password)
        self.v2_web_token.setPlaceholderText('Geçici güçlü panel tokeni (24+ karakter) veya TI_WEB_TOKEN')
        c.addWidget(self.v2_web_token)
        line=QHBoxLayout();line.addWidget(btn('Mobil Paneli Aç',self.v2_mobile_start))
        line.addWidget(btn('Mobil Paneli Kapat',self.v2_mobile_stop));c.addLayout(line)
        self.v2_mobile_status=txt('Panel kapalı',muted=True);c.addWidget(self.v2_mobile_status);v.addWidget(mobile)
        plugins,c=card('10–14–15 • Kurtarma, Eklentiler ve Windows EXE')
        c.addWidget(txt('YOLO için otomatik sınırlı yeniden başlatma denemeleri var. EXE oluşturma ve yedekten dönme betikleri paketle birlikte gelir; Windows üzerinde ayrı çalıştırılır.',muted=True))
        c.addWidget(txt('Modül kayıtları: '+', '.join(item[1] for item in extension_list()),muted=True))
        c.addWidget(btn('Tanı Raporu Oluştur',self.refresh_diag))
        c.addWidget(btn('GitHub Sürümünü Kontrol Et (İndirme/Kurma Yok)',self.v2_update_check))
        c.addWidget(btn('Güncel Devam Notlarını Aç',lambda:self.v2_open_notes()))
        v.addWidget(plugins);v.addStretch()
        return area

    def eventFilter(self,obj,event):
        if hasattr(self,'ar_preview') and obj is self.ar_preview and event.type()==QEvent.MouseButtonPress:
            if self.ar_place_sticker and hasattr(self,'ar_pixmap'):
                scaled=self.ar_pixmap.scaled(self.ar_preview.size(),Qt.KeepAspectRatio,Qt.FastTransformation)
                dx=(self.ar_preview.width()-scaled.width())/2
                dy=(self.ar_preview.height()-scaled.height())/2
                x=(event.position().x()-dx)/max(1,scaled.width())
                y=(event.position().y()-dy)/max(1,scaled.height())
                if 0<=x<=1 and 0<=y<=1:
                    self.ar.add_sticker(self.ar_place_sticker,(x,y))
                    self.ar_status.setText('Sticker eklendi: '+self.ar_place_sticker)
                    self.ar_place_sticker=None
            return True
        if hasattr(self,'camera_label') and obj is self.camera_label and event.type()==QEvent.MouseButtonPress:
            if not self.last_frame or not self.runtime.active:return False
            target=self.last_frame.scaled(self.camera_label.size(),Qt.KeepAspectRatio,Qt.FastTransformation)
            dx=(self.camera_label.width()-target.width())/2
            dy=(self.camera_label.height()-target.height())/2
            x=(event.position().x()-dx)/max(1,target.width());y=(event.position().y()-dy)/max(1,target.height())
            if 0<=x<=1 and 0<=y<=1:
                self.runtime.follow_controller.select_target(x,y)
                self.log('Takip hedefi seçildi; Takibi Başlat ile devam et.','Takip')
            return True
        return super().eventFilter(obj,event)

    def v2_calibration(self):
        self.v2_calib.setText(self.runtime.follow_controller.calibration_report())

    def v2_shortcut(self,target):
        threading.Thread(target=lambda:self.post('info',open_target(target)),daemon=True).start()

    def _v2_memory_db(self):
        if self._v2_memory is None:self._v2_memory=ConversationMemory(DATA/'ti_conversation.sqlite3')
        return self._v2_memory

    def _v2_visual_db(self):
        if self._v2_sights is None:self._v2_sights=VisualHistory(DATA/'visual_history.sqlite3',CAPTURES)
        return self._v2_sights

    def v2_clear_memory(self):
        if QMessageBox.question(self,'Hafızayı Sil','Yerel sohbet geçmişi kalıcı olarak silinsin mi?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self._v2_memory_db().clear();self.v2_result.setPlainText('Yerel sohbet hafızası silindi.')

    def v2_query(self,mode):
        if self.v2_busy:return self.v2_result.setPlainText('Önceki isteğin tamamlanması bekleniyor.')
        question=self.v2_prompt.toPlainText().strip()
        if not question:return self.v2_result.setPlainText('Önce soru yaz.')
        session_key=self.lab_key.text().strip()
        memory=self._v2_memory_db() if self.v2_memory_opt.isChecked() else None
        jpeg=None
        if mode=='vision':
            reply=QMessageBox.question(self,'Kamera görüntüsü paylaşımı','Şu anki kamera görüntüsü OpenAI API’ye gönderilsin mi?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if reply!=QMessageBox.Yes:return
            with self.runtime.video.frame_lock:
                frame=None if self.runtime.video.frame is None else self.runtime.video.frame.copy()
            if frame is None:return self.v2_result.setPlainText('Kamera görüntüsü henüz gelmedi.')
            import cv2
            h,w=frame.shape[:2]
            frame=cv2.resize(frame,(min(w,768),int(h*min(w,768)/w))) if w>768 else frame
            ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,72])
            if not ok:return self.v2_result.setPlainText('JPEG kodlama hatası')
            jpeg=encoded.tobytes()
        self.v2_busy=True;self.v2_result.setPlainText('Ti işliyor...')
        agent=self.v2_agent.currentData()
        local_model=self.settings.get('llm_model') if self.settings.get('llm_enabled') else None
        context=diagnostic_text(make_diagnostic(self.runtime,self.settings)) if mode=='developer' else None
        def worker():
            try:
                if mode=='vision':answer=vision_question(jpeg,question,api_key=session_key)
                elif mode=='developer':
                    dest=DATA/('Ti_Developer_Oneri_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.md')
                    developer_proposal(question,context,api_key=session_key,local_model=local_model,path=dest)
                    self._v2_proposal_path=dest
                    answer=f'Onay bekleyen öneri dosyası oluşturuldu: {dest.name}. Otomatik kod değişikliği/PR yapılmadı.'
                else:answer=agent_chat(question,agent,api_key=session_key,local_model=local_model,memory=memory)
                self.post('v2_answer',answer)
            except Exception as exc:self.post('v2_error',str(exc)[:350])
        threading.Thread(target=worker,daemon=True,name='Ti-v2-Worker').start()

    def v2_github_pr(self):
        path=self._v2_proposal_path
        if not path or not path.is_file():
            self.v2_result.setPlainText('Önce Geliştirici Önerisi .md oluştur.');return
        folder=QFileDialog.getExistingDirectory(self,'GitHub kaynak deposunu seç',str(BASE))
        if not folder:return
        confirm=QMessageBox.question(self,'GitHub PR Yayınlama Onayı',
              'Yalnızca Ti Developer öneri Markdown dosyası seçilen GitHub deposuna gönderilecek, taslak PR açılacak. Onaylıyor musun?',
              QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if confirm!=QMessageBox.Yes:return
        def worker():
            try:
                link=publish_proposal(folder,path,confirmed=True)
                self.post('v2_answer','GitHub taslak PR: '+link)
            except Exception as exc:self.post('v2_error','GitHub PR: '+str(exc)[:260])
        self.v2_busy=True;self.v2_result.setPlainText('GitHub taslak PR gönderiliyor...')
        threading.Thread(target=worker,daemon=True).start()

    def v2_search_sights(self):
        try:
            rows=self._v2_visual_db().search(self.v2_find.text())
            self.v2_sight_result.setPlainText('\n'.join(f'{ts} • {kind}: {note} {img}' for ts,kind,note,img in rows) or 'Kayıt bulunamadı.')
        except (ValueError,OSError) as exc:self.v2_sight_result.setPlainText(str(exc))

    def v2_telegram_test(self):
        threading.Thread(target=lambda:self._v2_send_telegram('Ti AI v2.0 test bildirimi'),daemon=True).start()

    def _v2_send_telegram(self,text):
        try:telegram_alert(text);self.post('info','Telegram bildirimi gönderildi.')
        except Exception as exc:self.post('error','Telegram: '+str(exc)[:180])

    def v2_ha_toggle(self):
        entity=self.v2_ha_entity.text().strip()
        if QMessageBox.question(self,'Home Assistant','"'+entity+'" cihazı değiştirilsin mi?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        def worker():
            try:self.post('info',home_assistant_toggle(entity))
            except Exception as exc:self.post('error','Home Assistant: '+str(exc)[:180])
        threading.Thread(target=worker,daemon=True).start()

    def v2_mobile_start(self):
        if self.mobile_server:return
        try:
            host=os.environ.get('TI_WEB_HOST','127.0.0.1')
            self.mobile_server=MobileServer(
                lambda:{'running':bool(self.runtime.active),'tracking':bool(self.runtime.follow_controller.active),
                        'detection':bool(self.settings['detection']),'fps':round(self.runtime.video.fps,1)},
                lambda name:self.post('web_control',name),
                token=self.v2_web_token.text().strip(),host=host,
                certfile=os.environ.get('TI_WEB_TLS_CERT'),keyfile=os.environ.get('TI_WEB_TLS_KEY'))
            url=self.mobile_server.start()
            self.v2_mobile_status.setText('Mobil panel: '+url+' (Token yalnızca kullanıcıda)')
        except Exception as exc:
            self.mobile_server=None;self.v2_mobile_status.setText('Açılamadı: '+str(exc)[:180])

    def v2_mobile_stop(self):
        server=self.mobile_server;self.mobile_server=None
        if server:threading.Thread(target=server.stop,daemon=True).start()
        self.v2_mobile_status.setText('Mobil panel kapalı')

    def v2_update_check(self):
        def worker():
            try:
                release=latest_release()
                self.post('v2_answer','Son yayınlanan sürüm: '+release['version']+' | '+release['url']+'\nTi otomatik indirme veya kurulum yapmaz.')
            except Exception as exc:self.post('v2_error','Sürüm kontrolü: '+str(exc)[:200])
        threading.Thread(target=worker,daemon=True).start()

    def v2_open_notes(self):
        path=BASE/'DEVAM_NOTLARI.md'
        self.log('Devam notları: '+str(path),'Bilgi')
        if path.is_file():
            import webbrowser
            webbrowser.open(path.as_uri())

    def ai_request(self,mode):
        if self.lab_busy:
            self.lab_answer.setPlainText('Önceki Ti yanıtı devam ediyor.');return
        question=self.lab_question.toPlainText().strip()
        if not question:
            self.lab_answer.setPlainText('Önce sorunu yaz.');return
        self.lab_busy=True
        self.lab_answer.setPlainText('Ti isteği işliyor...')
        self.lab_history.append(('user',question))
        context=None
        session_api_key=self.lab_key.text().strip()
        if mode=='improve':
            context=diagnostic_text(make_diagnostic(self.runtime,self.settings))
        def worker():
            try:
                answer=ask_ti(question,research=(mode=='research'),
                              improvement_context=context if mode=='improve' else None,
                              local_model=self.settings.get('llm_model') if self.settings.get('llm_enabled') and mode!='research' else None,
                              api_key=session_api_key)
                self.post('lab_answer',answer)
            except Exception as exc:
                self.post('lab_error',str(exc)[:450])
        threading.Thread(target=worker,daemon=True,name='ti-lab-ai').start()

    def _book(self):
        if self.knowledge is None:
            self.knowledge=KnowledgeBook(DATA/'ti_notes.sqlite3')
        return self.knowledge

    def lab_save_note(self):
        try:
            self._book().add(self.note_title.text(),self.note_body.toPlainText())
            self.note_title.clear();self.note_body.clear()
            self.lab_search_notes()
            self.log('Yerel bilgi defterine not kaydedildi.','Bilgi')
        except (ValueError,OSError) as exc:
            self.note_results.setPlainText('Not kaydedilemedi: '+str(exc))

    def lab_search_notes(self):
        try:
            rows=self._book().search(self.note_search.text())
            self.note_results.setPlainText('\n\n'.join(f'{ts} | {title}\n{body}' for _,ts,title,body in rows) or 'Not bulunamadı.')
        except (OSError,ValueError) as exc:
            self.note_results.setPlainText('Not arama hatası: '+str(exc))

    def refresh_diag(self):
        self.lab_diag.setPlainText(diagnostic_text(make_diagnostic(self.runtime,self.settings)))

    def export_lab_diag(self):
        dest,_=QFileDialog.getSaveFileName(self,'Tanı raporu kaydet',str(DATA/'Ti_Tani_Raporu.md'),'Markdown (*.md)')
        if not dest:return
        try:
            export_diagnostic(dest,make_diagnostic(self.runtime,self.settings))
            self.log('Tanı raporu kaydedildi.','Tanı')
        except OSError as exc:self.log('Rapor hatası: '+str(exc),'Hata')

    def export_lab_chat(self):
        dest,_=QFileDialog.getSaveFileName(self,'Sohbeti kaydet',str(DATA/'Ti_Sohbet.md'),'Markdown (*.md)')
        if not dest:return
        try:
            export_chat(dest,self.lab_history)
            self.log('Bu oturumun sohbeti .md dosyasına kaydedildi.','Sohbet')
        except OSError as exc:self.log('Sohbet kaydı hatası: '+str(exc),'Hata')

    def toggle_privacy(self):
        if self._privacy_previous is None:
            self.ar_stop()
            self._privacy_previous={key:self.toggles[key].isChecked() for key in ('preview','detection','person_only','microphone')}
            self._privacy_previous['auto_snapshot']=self.settings.get('auto_snapshot',False)
            for key in ('preview','detection','microphone'):
                self.toggles[key].setChecked(False)
            self.update_setting('auto_snapshot',False)
            if hasattr(self,'auto_snap'):self.auto_snap.setChecked(False)
            self.privacy_button.setText('Gizlilik Modunu Kapat (Önceki Ayarlara Dön)')
            self.log('Gizlilik kilidi etkin: kamera ve mikrofon kapatıldı.','Gizlilik')
        else:
            previous=self._privacy_previous;self._privacy_previous=None
            for key in ('preview','detection','person_only','microphone'):
                self.toggles[key].setChecked(bool(previous[key]))
            self.update_setting('auto_snapshot',bool(previous['auto_snapshot']))
            if hasattr(self,'auto_snap'):self.auto_snap.setChecked(bool(previous['auto_snapshot']))
            self.privacy_button.setText('Gizlilik Modunu Aç (Kamera ve Mikrofonu Durdur)')
            self.log('Gizlilik kilidi kaldırıldı; önceki ayarlar geri yüklendi.','Gizlilik')

    def apply_confidence_preset(self,value):
        self.confidence.setValue(value)
        self.update_setting('confidence',float(value))
        self.log('YOLO güven eşiği ayarlandı: '+str(value),'Algılama')

    def show_section(self,index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.navbuttons):
            b.setProperty('role','active' if i==index else 'nav')
            b.style().unpolish(b);b.style().polish(b)
        if index==4:self.reload_logs()
        if index==0 and self.last_frame:self._paint_video()
        if index!=8 and self.ar.running:self.ar_stop()

    def set_theme(self,name,save=True):
        self.settings['theme']=name
        self.setStyleSheet(stylesheet(name))
        self.theme_button.setText('☀  Açık mod' if name=='dark' else '☾  Gece modu')
        if save:settings_save(self.settings);self.log('Tema değişti: '+name)

    def changed_toggle(self,key,state):
        # Automatically enable prerequisites, instead of an invisible no-op.
        if key=='person_only' and state and not self.toggles['detection'].isChecked():
            self.toggles['detection'].setChecked(True)
        if key=='detection' and state and not self.toggles['preview'].isChecked():
            self.toggles['preview'].setChecked(True)
        if key=='detection' and not state and self.toggles['person_only'].isChecked():
            self.toggles['person_only'].setChecked(False)
        if key=='preview' and not state and self.ar.running:self.ar_stop()
        if key=='preview' and not state and self.toggles['detection'].isChecked():
            self.toggles['detection'].setChecked(False)
        self.runtime.toggle(key,state)
        labels={'microphone':'Mikrofon','voice':'Ti konuşma','preview':'Canlı görüntü',
                'detection':'Nesne algılama','person_only':'Sadece kişi',
                'motor':'Motor kontrolü','alert_person':'Sesli kişi uyarısı',
                'desktop_notice':'Masaüstü bildirimi'}
        if key=='detection':
            self.detection_status.setText('YOLO: Model bekleniyor' if state and self.runtime.active else
                'YOLO: Sistem başlatılınca açılacak' if state else 'YOLO: Kapalı')
        if key=='preview' and not state:
            self.camera_label.clear()
            self.camera_label.setText('Canlı görüntü kapalı')
            self.live_badge.setText('● Görüntü kapalı')
        suffix='' if self.runtime.active else ' (sistem başlatılınca uygulanacak)'
        self.log(f'{labels.get(key,key)}: {"açık" if state else "kapalı"}{suffix}','Ayar')

    def update_setting(self,key,val):
        self.settings[key]=val;settings_save(self.settings)

    def change_zoom(self,val):
        self.update_setting('digital_zoom',val/10)
        self.zoom_text.setText(f'{val/10:.1f}x • dijital yakınlaştırma')

    def start(self):
        self.status.setText('● Başlatılıyor...')
        if self.settings['detection']:
            self.detection_status.setText('YOLO: Kamera açılışı bekleniyor')
        self.runtime.start(self.router.run)

    def stop(self):
        self.ar_stop()
        self.runtime.stop();self.status.setText('● Durduruldu')
        self.live_badge.setText('● Bağlı değil');self.camera_label.setPixmap(QPixmap())
        self.camera_label.setText('Kamera durduruldu')
        self.log('Ti durduruldu')

    def start_follow(self):
        if not self.runtime.active:
            self.log('Takip için önce Sistemi Başlat düğmesini kullan.','Uyarı')
            return
        # Required switches are exposed to the user and remain consistent.
        for key in ('preview','detection','person_only'):
            if not self.toggles[key].isChecked():
                self.toggles[key].setChecked(True)
        self.runtime.follow(True)
    def stop_follow(self):self.runtime.follow(False)
    def move(self,direction):self.runtime.move(direction)

    def speak(self):
        s=self.speak_text.toPlainText().strip()
        if not s:return self.log('Söyletmek için bir cümle yaz.','Uyarı')
        if len(s)>450:return self.log('En fazla 450 karakter olabilir.','Uyarı')
        self.runtime.speak(s)

    def snapshot(self):
        ok,message=self.runtime.video.snapshot()
        self.log(('Fotoğraf kaydedildi: ' if ok else 'Fotoğraf hatası: ')+message,'Fotoğraf')

    def record_start(self):
        if not self.runtime.video.thread or not self.runtime.video.thread.is_alive():
            return self.log('Önce canlı kamera görüntüsünü aç.','Uyarı')
        self.runtime.video.recording=True;self.log('Video kaydı başlatıldı.','Video')
    def record_stop(self):
        self.runtime.video.recording=False;self.log('Video kaydı durdurma istendi.','Video')

    def do_open(self,target):self.log(open_target(target),'Komut')

    def send_media(self,key):
        from ti_commands import media_key
        self.log(('Medya komutu gönderildi' if media_key(key) else 'Medya tuşu Windows gerektiriyor')+': '+key,'Medya')

    def apply_profile(self,name):
        if name=='Ev': values=dict(microphone=True,voice=True,preview=True,detection=True,person_only=True,alert_person=False)
        elif name=='Gece': values=dict(microphone=True,voice=True,preview=True,detection=True,person_only=True,alert_person=True)
        else:values=dict(microphone=False,voice=False,preview=True,detection=True,person_only=True,alert_person=False)
        for k,val in values.items():
            if k in self.toggles:self.toggles[k].setChecked(val)
            else:self.runtime.toggle(k,val)
        self.settings['profile']=name;settings_save(self.settings)
        self.log('Profil açıldı: '+name,'Profil')

    def save_advanced(self):
        source=self.source.currentData()
        if not source.startswith('rtsp://127.0.0.1:8554/') or len(source)>230:
            QMessageBox.warning(self,'Ti','RTSP kaynağı yalnızca 127.0.0.1:8554 üzerinde olabilir.');return
        self.settings.update(whisper=self.model.currentText(),threshold=float(self.threshold.value()),
            confidence=float(self.confidence.value()),video_source=source,city=self.city.text().strip()[:70],
            manual_move_pause=self.move_delay.value())
        settings_save(self.settings);self.log('Gelişmiş ayarlar kaydedildi; yeni başlangıçta uygulanacak.','Ayar')

    def save_llm(self):
        self.settings['llm_enabled']=self.llm_check.isChecked()
        self.settings['llm_model']=self.llm_model.text().strip()[:100] or 'llama3.2:3b'
        self.settings['voice_personality']=self.persona.currentText()
        settings_save(self.settings)
        self.log('Yerel sohbet: '+('açık' if self.settings['llm_enabled'] else 'kapalı'),'Ayar')

    def connect_spotify(self):
        client=self.spotify_id.text().strip()
        self.settings['spotify_client_id']=client
        settings_save(self.settings)
        self.log('Spotify yetkilendirme sayfası açılıyor.','Spotify')
        self.spotify.connect(client,lambda ok,msg:self.post('info' if ok else 'error',msg))

    def disconnect_spotify(self):
        self.spotify.disconnect()
        self.log('Spotify bağlantısı kapatıldı.','Spotify')

    def save_learned(self):
        phrase=self.learn_phrase.text().strip();reply=self.learn_reply.text().strip()
        if len(phrase)<3 or len(reply)<2:return QMessageBox.warning(self,'Ti','Komut ve cevap gir.')
        self.settings['learned'][phrase[:100]]=reply[:400]
        settings_save(self.settings)
        self.log('Yeni komut öğretildi: '+phrase,'Komut')
        self.learn_phrase.clear();self.learn_reply.clear()

    def show_learned(self):
        text='\n'.join(k+' → '+v for k,v in self.settings['learned'].items()) or 'Henüz özel komut yok.'
        QMessageBox.information(self,'Öğretilen Komutlar',text[:3800])

    def save_schedule(self):
        hhmm=self.schedule_time.text().strip(); msg=self.schedule_message.text().strip()
        import re
        if self.schedule_check.isChecked() and (not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',hhmm) or not msg):
            QMessageBox.warning(self,'Ti','Saat HH:MM biçiminde olmalı ve mesaj boş olmamalı.');return
        self.settings.update(schedule_enabled=self.schedule_check.isChecked(),scheduled_time=hhmm,scheduled_speech=msg[:400])
        settings_save(self.settings);self.log('Hatırlatıcı ayarları kaydedildi.','Ayar')

    def test_command(self,sentence):
        cleaned=sentence.removeprefix('Ti ').removeprefix('Merhaba Ti').strip()
        if not cleaned:return self.log('Sesli uyandırma için kameraya Merhaba Ti de.','Komut')
        self.log('Komut işleniyor: '+cleaned,'Komut')
        # Spotify and Ollama can take seconds; NEVER block Qt's event loop.
        def command_worker():
            try:
                response=self.router.run(cleaned)
                if response is None:
                    if self.runtime.assistant:response=self.runtime.assistant._answer(cleaned)
                    else:
                        from ti_v1_core import answer_command
                        response=answer_command(cleaned)
                self.post('command_result',(cleaned,str(response)))
                if self.runtime.assistant and self.settings['voice']:
                    self.runtime.speak(str(response))
            except Exception as exc:
                self.post('error','Komut işlenemedi: '+str(exc)[:180])
        threading.Thread(target=command_worker,daemon=True,name='ti-manual-command').start()

    def export_events_json(self):
        dest,_=QFileDialog.getSaveFileName(self,'JSON olarak kaydet',str(CAPTURES/'Ti_Olaylar.json'),'JSON (*.json)')
        if dest:
            try:self.runtime.store.export_json(dest);self.log('JSON olay kaydı dışa aktarıldı.','Kayıt')
            except (OSError,ValueError) as exc:self.log('JSON dışa aktarma hatası: '+str(exc),'Hata')

    def export_events(self):
        fn,_=QFileDialog.getSaveFileName(self,'CSV olarak kaydet',str(CAPTURES/'Ti_Olaylar.csv'),'CSV (*.csv)')
        if fn:
            try:self.runtime.store.export_csv(fn);self.log('CSV dışa aktarıldı: '+fn,'Kayıt')
            except OSError as ex:QMessageBox.warning(self,'Ti',str(ex))

    def reload_logs(self):
        if not hasattr(self,'events_table'):return
        items=self.runtime.store.search(self.events_filter.text(),90) if hasattr(self,'events_filter') and self.events_filter.text().strip() else self.runtime.store.get(90)
        if hasattr(self,'recent'):
            self.recent.clear()
            for ts,kind,msg in items[:9]:self.recent.addItem(f'{ts[11:16]}  •  {msg[:65]}')
        if self.stack.currentIndex()==4:
            self.events_table.setRowCount(len(items))
            for row,(ts,kind,msg) in enumerate(items):
                for col,val in enumerate((ts.replace('T',' '),kind,msg)):
                    self.events_table.setItem(row,col,QTableWidgetItem(str(val)))

    def confirm_action(self,action):
        labels={'shutdown':'Bilgisayar kapatılsın mı?','restart':'Bilgisayar yeniden başlatılsın mı?',
                'lock':'Windows oturumu kilitlensin mi?'}
        if action not in labels:return
        reply=QMessageBox.question(self,'Ti — Güvenlik Onayı',labels[action],QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if reply!=QMessageBox.Yes:self.log('Sistem işlemi iptal edildi.','Güvenlik');return
        try:
            if action=='shutdown':subprocess.Popen(['shutdown','/s','/t','30'])
            elif action=='restart':subprocess.Popen(['shutdown','/r','/t','30'])
            elif os.name=='nt':
                import ctypes;ctypes.windll.user32.LockWorkStation()
            self.log('Sistem işlemi kullanıcı onayıyla istendi: '+action,'Güvenlik')
        except OSError as ex:self.log('Sistem işleminde hata: '+str(ex),'Hata')

    def take_action(self,action):
        name,val=action
        if name in ('theme_dark','theme_light'):
            self.set_theme('dark' if name=='theme_dark' else 'light');return
        if name=='cyber_open':self.show_section(9);self.cyber_show_devices();return
        if name=='snapshot':self.snapshot();return
        if name=='record_on':self.record_start();return
        if name=='record_off':self.record_stop();return
        if name.startswith('profile_'):
            self.apply_profile({'profile_night':'Gece','profile_quiet':'Sessiz','profile_home':'Ev'}[name]);return
        toggles={'preview_on':('preview',True),'preview_off':('preview',False),
            'detect_on':('detection',True),'detect_off':('detection',False),
            'person_only':('person_only',True),'detect_all':('person_only',False)}
        if name in toggles:
            k,v=toggles[name]
            if k in self.toggles:self.toggles[k].setChecked(v)

    def poll(self):
        if self.shutting_down:return
        frame=None;received=0
        with self._video_lock:
            frame=self._latest_video_packet
            self._latest_video_packet=None
        for _ in range(30):
            try:kind,val=self.events.get_nowait()
            except queue.Empty:break
            if kind=='frame':frame=val;received+=1
            elif kind=='video_status':self.live_badge.setText('● '+str(val)[:40])
            elif kind=='detection_loading':
                self.detection_status.setText('YOLO: Model yükleniyor...')
                self.log('YOLO modeli yükleniyor; ilk çalıştırmada indirilebilir.','Algılama')
            elif kind=='detection_retry':
                self.detection_status.setText('YOLO: Kurtarma deneniyor...')
                self.log('YOLO otomatik yeniden deneme: '+str(val)[:190],'Hata')
            elif kind=='detection_ready':
                self.detection_status.setText('● YOLO aktif — nesneler işaretleniyor')
                self.log('YOLO nesne algılama çalışıyor.','Algılama')
            elif kind=='lab_answer':
                self.lab_busy=False
                self.lab_answer.setPlainText(str(val))
                self.lab_history.append(('ti',str(val)))
            elif kind=='v2_answer':
                self.v2_busy=False;self.v2_result.setPlainText(str(val))
            elif kind=='v2_error':
                self.v2_busy=False;self.v2_result.setPlainText('Ti v2.3: '+str(val))
            elif kind=='net_result':
                self.net_busy=False
                title,payload=val
                if title=='adaptors':
                    self.net_adapter.clear()
                    for item in payload:self.net_adapter.addItem(item['name'],item['id'])
                    self.net_output.setPlainText('Ağ adaptörü listesi yüklendi. Analiz yalnızca seçilen adaptör ve verilen izinle başlar.')
                else:
                    self.net_last_report=payload if isinstance(payload,dict) else None
                    self.net_output.setPlainText(self._net_format_report(title,payload))
                self.net_state.setText('Hazır • '+title)
            elif kind=='net_error':
                self.net_busy=False;self.net_state.setText('HATA')
                self.net_output.setPlainText('Ağ Güvenliği: '+str(val))
            elif kind=='ar_status':self.ar_status.setText(str(val))
            elif kind=='ar_models_ready':
                if val and self.stack.currentIndex()==8:self.ar_start()
            elif kind=='ar_photo':
                if self.ar_gesture_photo.isChecked():self.ar_photo()
            elif kind=='ar_music':self.ar_media_key()
            elif kind=='web_control':
                if val=='follow_start':self.start_follow()
                elif val=='follow_stop':self.stop_follow()
                elif val=='privacy_on':
                    if self._privacy_previous is None:self.toggle_privacy()
                elif val=='snapshot':self.snapshot()
            elif kind=='lab_error':
                self.lab_busy=False
                self.lab_answer.setPlainText('Ti Laboratuvar: '+str(val))
            elif kind=='follow_status':
                self.follow_status.setText('Takip: '+str(val)[:130])
                self.log(str(val),'Takip')
            elif kind=='detection_failed':
                self.detection_status.setText('YOLO: HATA — Kayıtlar sayfasını incele')
                cb=self.toggles['detection']
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
                self.runtime.toggle('detection',False)
                self.log('Nesne algılama açılamadı: '+str(val)[:220]+' | Ti_Kur.cmd ile paketleri denetle.','Hata')
            elif kind=='runtime_started':
                self.status.setText('● Ti açık' if val=='all' else '● Video modu')
                self.log('Servis başlatıldı: '+val)
            elif kind=='voice_stopped':self.log('Sesli asistan kapandı.','Sistem')
            elif kind=='runtime_stopped':self.status.setText('● Durduruldu')
            elif kind=='transcript':self.heard_label.setText('Duyulan: '+str(val)[:80])
            elif kind=='command_result':
                command,response=val
                self.log(f'{command} → {response}','Komut')
            elif kind=='reply':self.log('Ti: '+str(val)[:180],'Konuşma')
            elif kind=='person_event':
                self.log(str(val),'Algılama')
                if self.settings.get('telegram_notice'):
                    threading.Thread(target=self._v2_send_telegram,args=(str(val),),daemon=True).start()
                if self.settings['desktop_notice'] and self.tray.isVisible():
                    self.tray.showMessage('Ti Güvenlik',str(val),QSystemTrayIcon.Information,5000)
                if self.settings['alert_person'] and self.settings['voice'] and self.runtime.assistant and self.runtime.assistant.speaker:
                    self.runtime.assistant.speaker.notify('person','Dikkat. Kamera görüntüsünde kişi algılandı.',cooldown=50)
            elif kind=='info':self.log(str(val),'Sistem')
            elif kind=='error':
                self.log(str(val),'Hata')
            elif kind=='action':self.take_action(val)
            elif kind=='confirm':self.confirm_action(val)
        if frame is not None:self.update_video(*frame)
        if self.stack.currentIndex()==8:self.ar_poll()

    def update_video(self,frame,count,fps):
        if self.stack.currentIndex()==8:
            if self.ar.running:self.ar.submit(frame)
            return
        if self.stack.currentIndex() not in (0,1):return
        h,w=frame.shape[:2]
        img=QImage(frame.data,w,h,frame.strides[0],QImage.Format_BGR888).copy()
        self.last_frame=QPixmap.fromImage(img)
        self._paint_video()
        if hasattr(self,'fullscreen_label') and self.fullscreen_label.isVisible():
            self.fullscreen_label.setPixmap(self.last_frame.scaled(self.fullscreen_label.size(),Qt.KeepAspectRatio,Qt.FastTransformation))
        self.live_badge.setText(('● CANLI   |  '+str(count)+' nesne') if self.settings['detection'] else '● CANLI')
        self.fps_label.setText(f'{fps:.1f} FPS • {w}×{h} • En güncel kare')

    def _paint_video(self):
        if self.last_frame:
            self.camera_label.setPixmap(self.last_frame.scaled(self.camera_label.size(),Qt.KeepAspectRatio,Qt.FastTransformation))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.last_frame:self._paint_video()

    def fullscreen_preview(self):
        if self.last_frame:
            if not hasattr(self,'preview_dialog'):
                self.preview_dialog=QWidget(None,Qt.Window)
                self.preview_dialog.setWindowTitle('Ti • Canlı kamera')
                box=QVBoxLayout(self.preview_dialog)
                self.fullscreen_label=QLabel();self.fullscreen_label.setAlignment(Qt.AlignCenter)
                self.fullscreen_label.setMinimumSize(700,410)
                box.addWidget(self.fullscreen_label)
                box.addWidget(btn('Pencereyi kapat', self.preview_dialog.close))
            self.fullscreen_label.setPixmap(self.last_frame.scaled(1300,850,Qt.KeepAspectRatio,Qt.FastTransformation))
            self.preview_dialog.resize(1200,730)
            self.preview_dialog.show()
        else:self.log('Henüz kamera görüntüsü yok.','Uyarı')

    def periodic_update(self):
        self.clock.setText(datetime.now().strftime('%d.%m.%Y  %H:%M:%S'))
        if self.runtime.assistant and self.runtime.voice_thread and self.runtime.voice_thread.is_alive():
            state='● Ti dinliyor' if self.runtime.assistant.speaker else '● Model yükleniyor'
            self.status.setText(state)
        if self.settings['schedule_enabled'] and self.runtime.active:
            now=datetime.now();today=now.strftime('%Y-%m-%d')
            if self.last_schedule_date!=today and now.strftime('%H:%M')==self.settings['scheduled_time']:
                self.last_schedule_date=today
                self.runtime.speak(self.settings['scheduled_speech'])
                self.log('Günlük hatırlatıcı çalıştırıldı.','Zamanlama')

    def closeEvent(self,event):
        if self.shutting_down:return
        self.shutting_down=True
        self.timer.stop();self.periodic.stop()
        self.v2_mobile_stop()
        self.ar_stop()
        self.runtime.close()
        if hasattr(self,'tray'):self.tray.hide()
        event.accept()


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('Ti Kontrol Merkezi')
    app.setStyle('Fusion')
    w=Window();w.show()
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(1100,app.quit)
    return app.exec()


if __name__=='__main__':sys.exit(main())
