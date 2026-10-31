"""Local camera/voice runtime for Ti; leaves original C301 project untouched."""
from __future__ import annotations
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.request
from typing import Callable

from ti_v1_core import TiAssistant, TiMotor
from ti_follow import SharedVisualFollower

BASE = Path(__file__).resolve().parent
PROJECT = BASE
LOCAL = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
GO_DIR = LOCAL / "C301-go2rtc-audio-fix"
PTZ_EXE = GO_DIR / "go2rtc_ti_ptz_experimental.exe"
VOICE_EXE = GO_DIR / "go2rtc_audio_fixed.exe"
# Never assume a specific Windows account or copy a private camera config into
# this repository.  Users may point to their own local go2rtc configuration.
CONFIG_PATH = Path(os.environ.get(
    "TI_GO2RTC_CONFIG",
    str(LOCAL / "C301-go2rtc" / "go2rtc.yaml"),
)).expanduser()
DATA = BASE / "Ti_Veriler"
CAPTURES = BASE / "Ti_Kayitlar"
SETTINGS_PATH = DATA / "settings.json"
STREAM_URL = "rtsp://127.0.0.1:8554/c301"
API = "http://127.0.0.1:1984/api/streams"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DEFAULTS = {
    "theme": "light", "microphone": True, "voice": True, "preview": True,
    "detection": False, "person_only": False, "motor": True,
    "alert_person": False, "desktop_notice": True, "confidence": 0.45, "whisper": "small", "threshold": 220.0,
    "video_source": STREAM_URL, "source_v11_confirmed": True, "yolo_model": "yolo11n.pt", "digital_zoom": 1.0,
    "sharpen": 0, "city": "Ankara", "profile": "Ev", "llm_enabled": False,
    "llm_model": "llama3.2:3b", "spotify_client_id": "", "learned": {}, "voice_personality": "Samimi",
    "telegram_notice": False, "event_clip": False, "manual_move_pause": 3, "follow_minutes": 10, "follow_steps_per_minute": 4, "auto_snapshot": False, "scheduled_speech": "", "scheduled_time": "", "schedule_enabled": False,
}


def settings_load():
    DATA.mkdir(parents=True, exist_ok=True)
    settings = dict(DEFAULTS)
    saved = {}
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        for key in settings:
            if key in saved and isinstance(saved[key], type(settings[key])):
                settings[key] = saved[key]
    except (ValueError, OSError):
        pass
    settings["video_source"] = settings["video_source"] if settings["video_source"].startswith("rtsp://127.0.0.1:8554/") else STREAM_URL
    # V1 default HW transcode cropped the field of view on this camera.
    # Migrate its default to the original, wide C301 stream.
    if (settings["video_source"] == "rtsp://127.0.0.1:8554/c301_h264_hw"
            and "source_v11_confirmed" not in saved):
        settings["video_source"] = STREAM_URL
        settings["digital_zoom"] = 1.0
    settings["digital_zoom"] = min(3.0, max(1.0, float(settings["digital_zoom"])))
    settings["confidence"] = min(.90, max(.15, float(settings["confidence"])))
    settings["threshold"] = min(3000, max(80, float(settings["threshold"])))
    settings["whisper"] = settings["whisper"] if settings["whisper"] in ("base", "small", "tiny") else "small"
    settings["sharpen"] = max(0, min(3, int(settings["sharpen"])))
    settings["manual_move_pause"] = max(3, min(8, int(settings["manual_move_pause"])))
    settings["follow_minutes"] = max(1, min(30, int(settings["follow_minutes"])))
    settings["follow_steps_per_minute"] = max(1, min(12, int(settings["follow_steps_per_minute"])))
    settings["learned"] = {str(k)[:100]: str(v)[:400] for k,v in settings.get("learned", {}).items()} if isinstance(settings.get("learned"),dict) else {}
    return settings


def settings_save(settings):
    DATA.mkdir(parents=True, exist_ok=True)
    safe = {k: settings.get(k, v) for k,v in DEFAULTS.items()}
    tmp = SETTINGS_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)


def get_streams():
    try:
        with urllib.request.urlopen(API, timeout=2) as r:
            result = json.load(r)
            return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), .5):
            return True
    except OSError:
        return False


class EventStore:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.path = DATA / "events.sqlite3"
        with closing(self.connect()) as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL)")
            db.commit()

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def add(self, kind, detail):
        # Do not store microphone audio / full transcriptions by default.
        with closing(self.connect()) as db:
            db.execute("INSERT INTO events(ts,kind,detail) VALUES(?,?,?)", (datetime.now().isoformat(timespec="seconds"),kind,str(detail)[:250]))
            db.commit()

    def get(self, limit=120):
        with closing(self.connect()) as db:
            return db.execute("SELECT ts,kind,detail FROM events ORDER BY id DESC LIMIT ?", (min(2000, int(limit)),)).fetchall()

    def search(self, term='', limit=200):
        """Search without SQL string interpolation or wildcard confusion."""
        term=str(term).strip()[:120]
        if not term:return self.get(limit)
        escape=term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        like='%'+escape+'%'
        with closing(self.connect()) as db:
            return db.execute("SELECT ts,kind,detail FROM events WHERE kind LIKE ? ESCAPE '\\' OR detail LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?",
                              (like,like,min(2000,int(limit)))).fetchall()

    def export_json(self,filename):
        with closing(self.connect()) as db:
            rows=db.execute('SELECT ts,kind,detail FROM events ORDER BY id').fetchall()
        path=Path(filename)
        if path.suffix.lower() != '.json':raise ValueError('JSON uzantısı gerekli.')
        path.write_text(json.dumps([{'time':ts,'type':kind,'message':message} for ts,kind,message in rows],
                       indent=2,ensure_ascii=False),encoding='utf-8')

    def export_csv(self, filename):
        import csv
        with closing(self.connect()) as db, open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f);writer.writerow(["Zaman", "Tür", "Açıklama"])
            writer.writerows(db.execute("SELECT ts,kind,detail FROM events ORDER BY id"))


class VideoWorker:
    """Decodes REAL RTSP frames. YOLO optional; record, screenshot and digital zoom are real."""
    def __init__(self, settings, post, follower=None):
        self.settings=settings; self.post=post
        self.follower=follower
        self.stopped=threading.Event()
        self.thread=None
        self.frame_lock=threading.Lock()
        self.frame=None
        self.recording=False
        self.writer=None
        self._last_person=0.0
        self._was_person=False
        self.frame_count=0
        self.fps=0
        self.yolo_ready=False
        self._rec_last=0.0
        self.capture=None
        self._detector_failed=False
        self._clip_writer=None;self._clip_until=0.0;self._clip_last=0.0
        self._start_lock=threading.RLock()
        self._deferred_start=False

    def start(self):
        with self._start_lock:
            if self.thread and self.thread.is_alive():
                # A rapid stop/start must not leave preview permanently off.
                if self.stopped.is_set() and not self._deferred_start:
                    self._deferred_start=True
                    old_thread=self.thread
                    threading.Thread(target=self._restart_when_closed,args=(old_thread,),
                                     daemon=True,name='ti-camera-restart').start()
                return
            self.stopped.clear()
            self.thread=threading.Thread(target=self._loop,daemon=True,name="ti-camera")
            self.thread.start()

    def _restart_when_closed(self,old_thread):
        old_thread.join()  # Background only: never waits on the Qt UI thread.
        with self._start_lock:
            restart=self._deferred_start
            self._deferred_start=False
            if restart:
                self.stopped.clear()
                self.thread=threading.Thread(target=self._loop,daemon=True,name='ti-camera')
                self.thread.start()

    def stop(self):
        with self._start_lock:
            self.stopped.set()
            self._deferred_start=False
            old_thread=self.thread
        # The worker releases FFmpeg in its finally block. Calling release()
        # here could block the Qt thread for several seconds on Windows.
        if old_thread and old_thread.is_alive() and threading.current_thread()!=old_thread:
            old_thread.join(timeout=.12)

    def snapshot(self):
        try: import cv2
        except ImportError: return False,"OpenCV bulunamadı."
        CAPTURES.mkdir(parents=True,exist_ok=True)
        with self.frame_lock:
            frame=self.frame.copy() if self.frame is not None else None
        if frame is None:return False,"Henüz kamera görüntüsü yok."
        out=CAPTURES / ("Ti_Fotograf_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".jpg")
        ok, jpg=cv2.imencode('.jpg',frame)
        if ok: out.write_bytes(jpg.tobytes())
        return bool(ok),str(out) if ok else "Fotoğraf kaydedilemedi."

    def _loop(self):
        try: import cv2
        except ImportError:
            self.post("error","OpenCV kurulu değil; kamera gösterilemiyor.");return
        from ti_lowlatency import LatestFFmpegCapture
        from ti_detector_async import AsyncDetector

        cap=None; detector=None; boxes=[]; track_ids=[]; last_result=0.0; last_post=0.0; recoveries=0; recover_at=0
        counter=0; counter_start=time.monotonic()
        try:
            while not self.stopped.is_set():
                if not self.settings["preview"]:
                    if self.writer:
                        self.writer.release();self.writer=None
                        self.post("info","Önizleme kapandığı için video dosyası tamamlandı")
                    if cap:cap.release();cap=None;self.capture=None
                    if detector:detector.stop();detector=None
                    boxes=[];self.yolo_ready=False
                    self.stopped.wait(.25)
                    continue
                if cap is None:
                    try:
                        cap=LatestFFmpegCapture(self.settings["video_source"])
                        self.capture=cap
                    except (OSError,RuntimeError,ValueError) as exc:
                        self.post("video_status","Video açılamadı; FFmpeg/RTSP kontrol et")
                        self.post("error","Kamera başlatma: "+str(exc)[:160])
                        self.stopped.wait(3);continue
                    if not cap.isOpened():
                        cap.release();cap=None;self.capture=None
                        self.post("video_status","Kamera görüntüsü bekleniyor; RTSP kontrol edin")
                        self.stopped.wait(3);continue
                    self.post("video_status","Geniş açı / düşük gecikmeli bağlantı açık")
                ok,raw=cap.read()
                if not ok:
                    cap.release();cap=None;self.capture=None
                    self.post("video_status","RTSP yeniden bağlanıyor")
                    self.stopped.wait(1);continue
                if raw is None:continue
                frame=raw.copy()
                zoom=float(self.settings["digital_zoom"])
                if zoom>1.01:
                    h,w=frame.shape[:2];nh=int(h/zoom);nw=int(w/zoom)
                    x=(w-nw)//2;y=(h-nh)//2
                    frame=cv2.resize(frame[y:y+nh,x:x+nw],(w,h))
                sharp=int(self.settings.get("sharpen",0))
                if sharp:
                    blurred=cv2.GaussianBlur(frame,(0,0),1)
                    frame=cv2.addWeighted(frame,1+sharp*.35,blurred,-sharp*.35,0)
                now=time.monotonic()

                if self._detector_failed and recoveries<=2 and now>=recover_at and self.settings['detection']:
                    self._detector_failed=False
                    self.post('info',f'YOLO yeniden başlatılıyor ({recoveries}/2)')
                if self.settings["detection"] and not self._detector_failed:
                    if detector is None:
                        self.post('detection_loading',None)
                        try:
                            detector=AsyncDetector(str(self.settings["yolo_model"]),interval=.75)
                            self.yolo_ready=False
                        except Exception as exc:
                            recoveries+=1
                            recover_at=now+min(30,6*recoveries)
                            self._detector_failed=True
                            self.post('detection_retry' if recoveries<=2 else 'detection_failed',
                                      'YOLO başlatma: '+str(exc)[:160])
                            if recoveries>2:self.settings['detection']=False
                    if detector is not None:
                        for kind,payload in detector.poll():
                            if kind=='track_ids':
                                track_ids=payload;continue
                            if kind=='error':
                                recoveries+=1
                                recover_at=now+min(30,6*recoveries)
                                self._detector_failed=True
                                self.yolo_ready=False
                                boxes=[]
                                detector.stop();detector=None
                                self.post('detection_retry' if recoveries<=2 else 'detection_failed',
                                          'YOLO: '+str(payload)[:170])
                                if recoveries>2:self.settings['detection']=False
                                if self.follower:self.follower.disable('YOLO hatası nedeniyle takip durdu.')
                                break
                            if kind=='result':
                                h,w=frame.shape[:2]
                                boxes=[]
                                for normalized,name,conf in payload[:25]:
                                    coords=[int(v*(w if j%2==0 else h)) for j,v in enumerate(normalized)]
                                    boxes.append((coords,str(name),float(conf)))
                                last_result=now
                                if self.follower:
                                    # v1.3.x compatibility: same detection frame, no second capture.
                                    # self.follower.on_detections(boxes,w,h,now=now)
                                    self.follower.on_detections(boxes,w,h,now=now,track_ids=track_ids)
                                if not self.yolo_ready:
                                    self.yolo_ready=True
                                    self.post('detection_ready',None)
                                person=any(name=='person' for _,name,_ in boxes)
                                if person and not self._was_person and now-self._last_person>25:
                                    self._last_person=now
                                    self.post('person_event','Kamera görüntüsünde kişi algılandı')
                                    if self.settings.get('event_clip'):
                                        self._clip_until=now+6.0
                                        CAPTURES.mkdir(parents=True,exist_ok=True)
                                        if self._clip_writer is None:
                                            out=CAPTURES/('Ti_Olay_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.avi')
                                            self._clip_writer=cv2.VideoWriter(str(out),cv2.VideoWriter_fourcc(*'MJPG'),5,(480,270))
                                            if not self._clip_writer.isOpened():
                                                self._clip_writer.release();self._clip_writer=None
                                                self.post('error','Olay klibi açılamadı')
                                            else:
                                                self.post('info','Kişi olay klibi: '+out.name)
                                                try:
                                                    from ti_v2_features import VisualHistory
                                                    VisualHistory(DATA/'visual_history.sqlite3',CAPTURES).add('Klip','Kişi olay videosu',out)
                                                except (OSError,ValueError):pass
                                    from ti_v2_features import VisualHistory
                                    try:VisualHistory(DATA/'visual_history.sqlite3',CAPTURES).add('Kişi','Görüntüde kişi algılandı.')
                                    except (OSError,ValueError):pass
                                    if self.settings.get('auto_snapshot'):
                                        CAPTURES.mkdir(parents=True,exist_ok=True)
                                        shot=CAPTURES/("Ti_Kisi_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".jpg")
                                        success,encoded=cv2.imencode('.jpg',frame)
                                        if success:
                                            shot.write_bytes(encoded.tobytes())
                                            self.post('info','Olay fotoğrafı: '+shot.name)
                                            try:VisualHistory(DATA/'visual_history.sqlite3',CAPTURES).add('Fotoğraf','Kişi olay kaydı',shot)
                                            except (OSError,ValueError):pass
                                self._was_person=person
                        if not self._detector_failed:
                            detector.submit(frame,self.settings['confidence'],self.settings['person_only'],track=bool(self.follower and self.follower.active))
                else:
                    boxes=[];self._was_person=False;self.yolo_ready=False
                    if detector is not None:
                        detector.stop();detector=None
                    if not self.settings['detection']:
                        self._detector_failed=False;recoveries=0
                if now-last_result>1.5:boxes=[]
                for coords,name,confidence in boxes:
                    x1,y1,x2,y2=coords
                    color=(53,185,62) if name=='person' else (255,147,42)
                    cv2.rectangle(frame,(x1,y1),(x2,y2),color,2)
                    cv2.putText(frame,f"{name} {confidence:.0%}",(x1,max(16,y1-6)),
                                cv2.FONT_HERSHEY_SIMPLEX,.47,color,1)
                if self._clip_writer is not None:
                    if now>=self._clip_until:
                        self._clip_writer.release();self._clip_writer=None
                        self.post('info','Olay videosu tamamlandı.')
                    elif now-self._clip_last>=.20:
                        self._clip_writer.write(cv2.resize(frame,(480,270),interpolation=cv2.INTER_AREA))
                        self._clip_last=now
                with self.frame_lock:self.frame=frame.copy()
                if self.recording:
                    if self.writer is None:
                        CAPTURES.mkdir(parents=True,exist_ok=True)
                        target=CAPTURES/("Ti_Video_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".mp4")
                        self.writer=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*"mp4v"),10,
                                                    (frame.shape[1],frame.shape[0]))
                        if not self.writer.isOpened():
                            self.writer.release();self.writer=None;self.recording=False
                            self.post('error','Video kayıt dosyası açılamadı')
                        else:self.post('info',f'Video kaydı: {target.name}')
                    if self.writer and time.monotonic()-self._rec_last>=.10:
                        self.writer.write(frame);self._rec_last=time.monotonic()
                elif self.writer is not None:
                    self.writer.release();self.writer=None
                    self.post('info','Video kaydı tamamlandı')
                counter+=1
                if now-counter_start>=1:
                    self.fps=counter/(now-counter_start)
                    counter_start=now;counter=0
                # 8 UI updates/s: no 15fps smooth scaling burden on Qt main loop.
                if now-last_post>.125:
                    self.post('frame',(frame,len(boxes),self.fps));last_post=now
        finally:
            if self._clip_writer is not None:
                self._clip_writer.release();self._clip_writer=None
            if detector is not None:detector.stop()
            if self.writer:
                self.writer.release();self.writer=None
            if cap:cap.release()
            self.capture=None


class Runtime:
    """Coordinates original Ti core and new UI, reuses owned go2rtc only."""
    def __init__(self,settings,post):
        self.settings=settings;self.post=post
        self.motor=TiMotor(enabled=bool(settings["motor"]),stream="c301_ses_test")
        self.follow_controller=SharedVisualFollower(self.motor,post)
        self.video=VideoWorker(settings,post,follower=self.follow_controller)
        self.assistant=None;self.voice_thread=None;self.go_proc=None
        self.starting=False;self.active=False;self.closed=False
        self.store=EventStore()

    def start(self,command_handler):
        if self.starting or self.active:
            self.post("info","Ti zaten başlatılıyor veya çalışıyor");return
        self.starting=True
        threading.Thread(target=self._startup,args=(command_handler,),daemon=True).start()

    def _startup(self,command_handler):
        try:
            streams=get_streams()
            if streams is None:
                if port_open(1984):
                    self.post("error","1984 portu yanıt vermiyor; başka işlem kullanıyor olabilir. Hiçbir işlem kapatılmadı.")
                    return
                binary=PTZ_EXE if PTZ_EXE.is_file() else VOICE_EXE
                if not binary.is_file():
                    self.post("error","go2rtc kurulu değil. Önceden çalışan EXE konumunu kontrol edin.")
                    return
                if not CONFIG_PATH.is_file():
                    self.post("error","go2rtc.yaml dosyası bulunamadı. Eski çalışan yapılandırmayı kontrol edin.")
                    return
                DATA.mkdir(parents=True,exist_ok=True)
                out=open(DATA/"go2rtc.log","ab")
                try:
                    self.go_proc=subprocess.Popen([str(binary),"-c",str(CONFIG_PATH)],stdin=subprocess.DEVNULL,
                          stdout=out,stderr=subprocess.STDOUT,creationflags=FLAGS)
                finally:out.close()
                for _ in range(30):
                    if self.closed:return
                    streams=get_streams()
                    if streams is not None:break
                    if self.go_proc.poll() is not None:break
                    time.sleep(.5)
                if streams is None:
                    self.post("error","go2rtc API açılmadı. Ti_Veriler/go2rtc.log dosyasına bakın.")
                    return
            self.post("info","go2rtc bağlı; mevcut kamera akışı kullanılıyor")
            self.active=True
            if self.settings["preview"]:
                self.video.start()
            if "c301_ses_test" not in streams:
                self.post("error","c301_ses_test ses akışı bulunamadı; video çalışabilir ama Ti mikrofonu/hoparlörü için bu akış gerekli.")
                self.post("runtime_started", "video_only")
                return
            if port_open(8766):
                self.post("error","8766 ses portu başka Ti işleminde olabilir; onu kapatmadan sesli asistanı açmıyorum.")
                self.post("runtime_started","video_only")
                return
            if not (BASE/"camera_speaker.py").exists():
                self.post("error","camera_speaker.py proje klasöründe yok; eski çalışan dosyayı buraya koyun.")
                self.post("runtime_started","video_only")
                return
            model=self.settings["whisper"]
            self.assistant=TiAssistant(model_name=model,stream="c301_ses_test",
                threshold=float(self.settings["threshold"]),enable_motor=bool(self.settings["motor"]),
                tracker_source=self.settings["video_source"],tracker_model=self.settings["yolo_model"],
                follow_vertical=False,follow_max_steps=4)
            a=self.assistant;a.command_handler=command_handler
            # Voice and GUI tracking share the same detection stream and motor.
            a.motor=self.motor
            a.follower=self.follow_controller
            a.on_transcript=lambda t:self.post("transcript",t)
            a.on_response=lambda t:self.post("reply",t)
            if not self.settings["microphone"]:a.microphone_enabled.clear()
            if not self.settings["voice"]:a.voice_enabled.clear()
            if not self.settings["detection"]:a.visual_detection_enabled.clear()
            self.voice_thread=threading.Thread(target=self._start_voice,daemon=True,name="TiVoice")
            self.voice_thread.start()
            self.post("runtime_started","all")
        except Exception as e:
            self.post("error","Başlatma hatası: "+str(e)[:260])
        finally:self.starting=False

    def _start_voice(self):
        try:self.assistant.start()
        except Exception as e:self.post("error","Asistan hatası: "+str(e)[:260])
        finally:self.post("voice_stopped",None)

    def stop(self):
        self.follow_controller.disable()
        self.video.stop()
        if self.assistant:
            self.assistant.follower.disable();self.assistant.stop_event.set()
            if self.assistant._ffmpeg and self.assistant._ffmpeg.poll() is None:
                self.assistant._ffmpeg.terminate()
        if self.go_proc and self.go_proc.poll() is None:
            self.go_proc.terminate()  # only the process launched by THIS app
        self.go_proc=None;self.active=False
        self.post("runtime_stopped",None)

    def close(self):
        self.closed=True;self.stop()

    def speak(self,text):
        if not self.assistant or not self.assistant.speaker:
            self.post("error","Ti'nin ses sistemi henüz hazır değil.");return
        if not self.settings["voice"]:
            self.post("error","Ti konuşma ayarı kapalı.");return
        assistant=self.assistant
        def send_in_background():
            try:
                assistant._respond(text[:450])
                self.post("info","Özel cümle Ti'ye gönderildi")
            except Exception as exc:
                self.post("error","Konuşma hatası: "+str(exc)[:180])
        threading.Thread(target=send_in_background,daemon=True,name="ti-tts").start()

    def move(self,direction):
        if not self.active or not self.settings["motor"]:
            self.post("error","PTZ için çalışan kamera ve motor izni gerekli.");return
        def task():
            if time.monotonic()-getattr(self,'_last_manual_move',0)<self.settings['manual_move_pause']:
                self.post("info", "Motor güvenliği: ayarlanan bekleme süresi dolmadı")
                return
            self.follow_controller.disable("Manuel yön tuşu takip modunu kapattı.")
            ok,msg=self.motor.move(direction)
            if ok:self._last_manual_move=time.monotonic()
            self.post("info" if ok else "error",msg)
        threading.Thread(target=task,daemon=True).start()

    def follow(self,on):
        if on:
            if not self.active:
                self.post("error","Önce Sistemi Başlat; canlı kamera açıldıktan sonra takibi etkinleştir.")
                return
            if not self.settings["preview"] or not self.settings["detection"]:
                self.post("error","Takip için Canlı Görüntü ve Nesne Algılama açık olmalı.")
                return
            ok,msg=self.follow_controller.enable(seconds=self.settings.get('follow_minutes',10)*60,
                max_steps_per_minute=self.settings.get('follow_steps_per_minute',4))
            self.post("info" if ok else "error",msg)
        else:
            self.follow_controller.disable()

    def toggle(self,key,value):
        self.settings[key]=value
        if key=='preview':
            if value and self.active:
                self.video.start()
                self.post('info','Canlı görüntü yeniden açılıyor')
            elif not value:
                self.post('info','Canlı görüntü kapatıldı')
        if key=='detection' and value and self.active and self.settings.get('preview'):
            self.video.start()
            self.post('info','Nesne algılama istendi; YOLO ilk karede yükleniyor')
        if key=="motor":
            self.motor.enabled=bool(value)
            if not value:self.follow_controller.disable("Motor kapatıldığı için takip durdu.")
        if key in ("preview", "detection") and not value:
            self.follow_controller.disable("Canlı görüntü/algılama kapatıldığı için takip durdu.")
        if self.assistant:
            if key=="microphone":
                (self.assistant.microphone_enabled.set if value else self.assistant.microphone_enabled.clear)()
            if key=="voice":
                (self.assistant.voice_enabled.set if value else self.assistant.voice_enabled.clear)()
            if key=="motor":
                self.assistant.motor.enabled=bool(value)
                if not value:self.assistant.follower.disable()
            if key=="detection":
                (self.assistant.visual_detection_enabled.set if value else self.assistant.visual_detection_enabled.clear)()
                if not value:self.assistant.follower.disable()
        settings_save(self.settings)
