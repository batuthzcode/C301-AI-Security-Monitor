"""Ti AR Studio: latest-only background inference / rendering (never on Qt UI thread)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from threading import Condition, Lock, Thread
from time import monotonic, sleep
import time
import math
import importlib.util
import cv2
import numpy as np
from ti_ar_core import MASKS, OBJECTS, COLORS, Drawing, coords, hand_gesture, palm_anchor, index_tip, valid_png, dist
from ti_ar_render import apply_face_mask, draw_strokes, drawing_png, draw_object, draw_sticker

MODEL_URLS={
 'hand_landmarker.task':'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
 'face_landmarker.task':'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
}

def download_models(directory,callback=None):
    """Explicit opt-in, trusted official URLs only, <25 MB/file, atomic write."""
    from urllib.request import urlopen, Request
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    written=[]
    for name,url in MODEL_URLS.items():
        dst=directory/name
        if dst.exists() and dst.stat().st_size>50_000:
            if callback:callback(f'{name}: mevcut')
            continue
        if callback:callback(f'{name}: resmi kaynaktan indiriliyor...')
        temp=dst.with_suffix('.download')
        try:
            with urlopen(Request(url,headers={'User-Agent':'TiAI-AR-Studio/2.1'}),timeout=25) as response,open(temp,'wb') as out:
                size=0
                while True:
                    block=response.read(131072)
                    if not block:break
                    size+=len(block)
                    if size>25_000_000:raise ValueError('Model çok büyük, indirme iptal edildi')
                    out.write(block)
            if size<50_000:raise RuntimeError('Model boş veya eksik indi')
            temp.replace(dst);written.append(name)
        finally:
            temp.unlink(missing_ok=True)
    return written

def ar_preflight(model_dir, *, require_hand=True, require_face=False):
    """Instant, nonblocking checks; no expensive MediaPipe model import on GUI thread.

    Returns actionable faults, not a misleading 'AR active' for missing models.
    """
    issues=[]
    if require_hand or require_face:
        if importlib.util.find_spec('mediapipe') is None:
            issues.append('MediaPipe kurulu değil. Ti_AR_Kutuphaneleri.bat dosyasını çalıştır.')
        folder=Path(model_dir)
        for name,needed in (('hand_landmarker.task',require_hand),('face_landmarker.task',require_face)):
            if needed and (not (folder/name).is_file() or (folder/name).stat().st_size<50000):
                issues.append(f'{name} eksik/bozuk. AR Studio > Modelleri İndir düğmesini kullan.')
    return issues


class MediapipeModel:
    """Late-load MediaPipe only when AR enabled. Single worker owns native state."""
    def __init__(self,model_dir):
        self.dir=Path(model_dir);self.hand=None;self.face=None;self.mp=None
        self.timestamp=0
        self.last_warning=''

    def _init(self,kind):
        path=self.dir/f'{kind}_landmarker.task'
        if not path.is_file():raise RuntimeError(f'AR modeli eksik: {path.name}. Önce Modelleri İndir düğmesini kullan.')
        if self.mp is None:
            try:import mediapipe as mp
            except ImportError as ex:raise RuntimeError('MediaPipe eksik. Ti_AR_Kutuphaneleri.bat çalıştır.') from ex
            self.mp=mp
        mp=self.mp
        opts=mp.tasks.vision
        base=mp.tasks.BaseOptions(model_asset_buffer=path.read_bytes())
        if kind=='hand':
            self.hand=opts.HandLandmarker.create_from_options(opts.HandLandmarkerOptions(
                base_options=base,running_mode=opts.RunningMode.VIDEO,num_hands=2,
                min_hand_detection_confidence=.52,min_tracking_confidence=.5))
        else:
            self.face=opts.FaceLandmarker.create_from_options(opts.FaceLandmarkerOptions(
                base_options=base,running_mode=opts.RunningMode.VIDEO,num_faces=2,
                min_face_detection_confidence=.5,min_tracking_confidence=.5))

    def detect(self,frame,hand=True,face=True):
        warnings=[]
        if hand and self.hand is None:
            try:self._init('hand')
            except (RuntimeError,ImportError,ValueError,OSError) as ex:warnings.append(str(ex)[:90])
        if face and self.face is None:
            try:self._init('face')
            except (RuntimeError,ImportError,ValueError,OSError) as ex:warnings.append(str(ex)[:90])
        self.last_warning=' | '.join(warnings)
        mp=self.mp
        if mp is None:return [],[]
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        img=mp.Image(image_format=mp.ImageFormat.SRGB,data=np.ascontiguousarray(rgb))
        self.timestamp=max(self.timestamp+1,int(monotonic()*1000))
        hands=self.hand.detect_for_video(img,self.timestamp).hand_landmarks if hand and self.hand else []
        faces=self.face.detect_for_video(img,self.timestamp).face_landmarks if face and self.face else []
        return [coords(x) for x in hands], [coords(x) for x in faces]

    def close(self):
        for detector in (self.hand,self.face):
            if detector is not None:detector.close()
        self.face=self.hand=None

class ARStudio:
    """One overwrite-only input slot, bounded frame size, fixed FPS, no camera ownership.

    UI invokes configure/submit; callback is thread-safe Window.post. Only worker
    invokes MediaPipe. If the model is missing, it reports a useful error without
    affecting the regular C301 preview, YOLO or motor controller.
    """
    def __init__(self,model_dir,callback,output_dir):
        self.model_dir=Path(model_dir);self.output_dir=Path(output_dir)
        self.callback=callback
        self.condition=Condition()
        self.frame=None
        self.running=False
        self.worker=None
        self.mask='Kapalı';self.obj='Kapalı';self.drawing_on=False
        self.custom_png=None
        self.color=COLORS[0];self.brush=5;self.fps_limit=6;self.max_side=640
        self.draw=Drawing()
        self.stickers=[]
        self.typed_text=''
        self.photo_on_thumbs=False
        self.music_on_thumbs=False
        self.laser_on=False;self.throw_on=False
        self._thumb_since=0;self._last_photo=0;self._last_media=0
        self._gesture='none';self._last_select=0;self._last_ui_status=0
        self._frame_out=None;self._last_rendered=None;self._out_lock=Lock()
        self.recording=False;self._writer=None;self._record_path=None
        self._last_model_error=''
        self.orb_scale=1.0;self._two_hands_initial=None
        self._model=None
        self._palm_last=None;self._palm_last_time=0.0;self._flying=[]
        self._next_submit=0.0
        self._input_frames=0;self._output_frames=0

    def start(self):
        with self.condition:
            if self.running:return
            if self.worker is not None and self.worker.is_alive():
                raise RuntimeError('AR arka planı henüz kapanıyor. Kısa süre sonra tekrar aç.')
            self.running=True
            self.frame=None
            self._next_submit=0.0
            self._input_frames=0;self._output_frames=0
            with self._out_lock:
                self._frame_out=None;self._last_rendered=None
            self.worker=Thread(target=self._run,name='Ti-AR-LatestOnly',daemon=True)
            self.worker.start()

    def stop(self):
        with self.condition:
            self.running=False;self.frame=None;self.condition.notify_all()
        self.draw.end()
        with self._out_lock:
            self._frame_out=None;self._last_rendered=None
        # no wait/join on the UI thread; worker owns native cleanup

    def submit(self,frame):
        if not self.running:return
        # Decimate before expensive copy/resize when source camera is faster than AR.
        now=monotonic()
        if now<self._next_submit:return
        self._next_submit=now+1/max(4,self.fps_limit)
        h,w=frame.shape[:2]
        if min(h,w)<48:return
        # copy latest resized frame, not a queue; max ~1.4MB BGR buffer
        factor=min(1,self.max_side/max(w,h))
        if factor<1:frame=cv2.resize(frame,(max(1,int(w*factor)),max(1,int(h*factor))),interpolation=cv2.INTER_AREA)
        else:frame=frame.copy()
        with self.condition:
            if not self.running:return
            self.frame=frame
            self._input_frames+=1
            self.condition.notify()

    def configure(self,**kwargs):
        allowed={'mask','obj','drawing_on','color','brush','fps_limit','custom_png','typed_text','photo_on_thumbs','music_on_thumbs','laser_on','throw_on'}
        with self.condition:
            for name,value in kwargs.items():
                if name not in allowed:raise ValueError(name)
                if name=='mask' and value not in MASKS:raise ValueError(value)
                if name=='obj' and value not in OBJECTS:raise ValueError(value)
                if name=='custom_png' and value: value=valid_png(value)
                if name=='fps_limit':value=max(4,min(15,int(value)))
                if name=='brush':value=max(1,min(25,int(value)))
                if name=='color' and tuple(value) not in COLORS:raise ValueError('Geçersiz renk')
                setattr(self,name,value)
            self.condition.notify_all()

    def clear(self):
        with self.condition:self.draw.clear();self.stickers.clear()

    def add_sticker(self,kind='Kalp',point=(.5,.5)):
        if kind not in ('Kalp','Yıldız','Ok'):raise ValueError(kind)
        with self.condition:
            self.stickers.append((kind,(max(0,min(1,point[0])),max(0,min(1,point[1])))))
            self.stickers=self.stickers[-30:]

    def pop_frame(self):
        with self._out_lock:
            item=self._frame_out;self._frame_out=None
        return item

    def snapshot(self):
        with self._out_lock:
            if self._last_rendered is None:return None
            return self._last_rendered.copy()

    def save_drawing(self):
        with self.condition:
            pic=drawing_png(self.draw)
        self.output_dir.mkdir(parents=True,exist_ok=True)
        path=self.output_dir/f'Ti_Hava_Cizimi_{time.strftime("%Y%m%d_%H%M%S")}.png'
        if not cv2.imwrite(str(path),pic):raise OSError('PNG kaydedilemedi')
        return path

    def save_photo(self):
        with self._out_lock:
            if self._last_rendered is None:raise RuntimeError('AR görüntüsü henüz hazır değil.')
            pic=self._last_rendered.copy()
        self.output_dir.mkdir(parents=True,exist_ok=True)
        path=self.output_dir/f'Ti_AR_Fotograf_{time.strftime("%Y%m%d_%H%M%S")}.png'
        if not cv2.imwrite(str(path),pic):raise OSError('PNG kaydedilemedi')
        return path

    def set_recording(self,enabled):
        with self.condition:
            self.recording=bool(enabled)
            self.condition.notify_all()

    def _record_frame(self,img,fps):
        if not self.recording:
            if self._writer is not None:self._writer.release();self._writer=None
            return
        if self._writer is None:
            self.output_dir.mkdir(parents=True,exist_ok=True)
            self._record_path=self.output_dir/f'Ti_AR_Video_{time.strftime("%Y%m%d_%H%M%S")}.mp4'
            h,w=img.shape[:2]
            self._writer=cv2.VideoWriter(str(self._record_path),cv2.VideoWriter_fourcc(*'mp4v'),float(fps),(w,h))
            if not self._writer.isOpened():
                self._writer=None;self.recording=False
                self.callback('ar_status','AR video kodlayıcı açılamadı; FFmpeg/MP4 desteğini kontrol edin.')
                return
            self.callback('ar_status','AR video kaydı: '+str(self._record_path))
        self._writer.write(img)

    def _run(self):
        model=MediapipeModel(self.model_dir);self._model=model
        next_frame=monotonic()
        try:
            while True:
                with self.condition:
                    while self.running and self.frame is None:self.condition.wait(timeout=.3)
                    if not self.running:break
                    raw=self.frame;self.frame=None
                    mask=self.mask;obj=self.obj;draw_on=self.drawing_on
                    fps=self.fps_limit;custom=self.custom_png
                remaining=next_frame-monotonic()
                if remaining>0:sleep(min(.15,remaining))
                next_frame=monotonic()+1/max(4,fps)
                started=monotonic()
                try:
                    # Demand only relevant models and don't import MediaPipe with AR off.
                    need_hands=(draw_on or obj!='Kapalı' or self.photo_on_thumbs or self.music_on_thumbs or self.laser_on)
                    need_faces=mask!='Kapalı'
                    if need_hands or need_faces:hands,faces=model.detect(raw,need_hands,need_faces)
                    else:hands,faces=[],[]
                    with self.condition:
                        out=self._render(raw,hands,faces,mask,obj,draw_on,custom,started)
                    self._last_model_error=''
                    status=f'AR aktif • {len(hands)} el, {len(faces)} yüz • {self._gesture} • kare {self._output_frames+1} • {1/max(.001,monotonic()-started):.0f} işlem/sn'
                    if model.last_warning:status='AR model uyarısı: '+model.last_warning
                except Exception as ex:
                    # Never take down Ti's main video/UI when AR model misconfigured.
                    out=raw
                    status='AR: '+str(ex)[:150]
                if not self.running:break
                self._record_frame(out,fps)
                with self._out_lock:
                    self._frame_out=(out,status)
                    self._last_rendered=out.copy()
                self._output_frames+=1
                if monotonic()-self._last_ui_status>.85 or status.startswith('AR:') and status!=self._last_model_error:
                    self.callback('ar_status',status)
                    self._last_ui_status=monotonic();self._last_model_error=status
        finally:
            if self._writer is not None:self._writer.release();self._writer=None
            model.close();self._model=None

    def _render(self,frame,hands,faces,mask,obj,draw_on,custom,tick):
        h,w=frame.shape[:2]
        if faces:apply_face_mask(frame,faces,mask,custom)
        hand=hands[0] if hands else None
        gesture=hand_gesture(hand) if hand else 'none'
        self._gesture=gesture
        if draw_on:
            if gesture=='draw':
                self.draw.begin(self.color,self.brush)
                p=index_tip(hand);self.draw.point(p.x,p.y)
            elif gesture=='erase':
                self.draw.end();p=index_tip(hand);self.draw.erase(p.x,p.y)
            else:self.draw.end()
            if gesture=='select' and tick-self._last_select>1.5:
                ix=COLORS.index(tuple(self.color));self.color=COLORS[(ix+1)%len(COLORS)]
                self._last_select=tick
            draw_strokes(frame,self.draw)
        if hand:
            palm=palm_anchor(hand)
            palm_size=dist(hand[0],hand[9])*h
            if len(hands)>1:
                a=palm_anchor(hands[0]);b=palm_anchor(hands[1]);separation=dist(a,b)
                if self._two_hands_initial is None:self._two_hands_initial=max(.05,separation)
                self.orb_scale=max(.65,min(2.,separation/max(.05,self._two_hands_initial)))
            else:self._two_hands_initial=None
            if self.laser_on and gesture in ('draw','select'):
                p=index_tip(hand)
                tip=(int(p.x*w),int(p.y*h))
                cv2.line(frame,tip,(min(w-1,tip[0]+140),max(0,tip[1]-145)),(40,50,255),3,cv2.LINE_AA)
                cv2.circle(frame,tip,9,(190,210,255),-1,cv2.LINE_AA)
            if self.throw_on and obj!='Kapalı':
                if gesture=='pause' and self._palm_last is not None and tick-self._palm_last_time<.6:
                    px,py=self._palm_last
                    self._flying.append([px,py,.0,tick,obj])
                    self._palm_last=None
                elif gesture=='palm':
                    self._palm_last=(palm.x,palm.y-.085)
                    self._palm_last_time=tick
            if obj!='Kapalı' and (gesture in ('palm','select','idle') or len(hands)>1):
                radius=min(110,max(25,palm_size*1.6*self.orb_scale))
                pos=(palm.x*w, (palm.y-.085)*h)
                draw_object(frame,pos,radius,obj,tick*.75)
            if gesture=='draw' and draw_on:
                p=index_tip(hand);cv2.circle(frame,(int(p.x*w),int(p.y*h)),8,(40,255,255),2,cv2.LINE_AA)
            # Gesture screenshot/music: explicit opt-in and 2s steady fist-free thumb.
            if self.photo_on_thumbs or self.music_on_thumbs:
                thumb_up=dist(hand[4],hand[0])>dist(hand[3],hand[0])*1.30 and gesture in ('pause','idle')
                if thumb_up:
                    if self._thumb_since==0:self._thumb_since=tick
                    if tick-self._thumb_since>=2:
                        if self.photo_on_thumbs and tick-self._last_photo>8:
                            self._last_photo=tick;self.callback('ar_photo',None)
                        if self.music_on_thumbs and tick-self._last_media>8:
                            self._last_media=tick;self.callback('ar_music',None)
                else:self._thumb_since=0
        else:self.draw.end();self._two_hands_initial=None;self._thumb_since=0
        self._flying=[f for f in self._flying if tick-f[3]<1.2]
        for fx,fy,_,start,kind in self._flying:
            age=tick-start
            draw_object(frame,(fx*w+age*130,(fy-age*.17)*h),max(12,55*(1-age/1.3)),kind,tick)
        for kind,pos in self.stickers:draw_sticker(frame,pos,kind)
        if self.typed_text:
            cv2.putText(frame,self.typed_text[:48],(18,max(28,h-26)),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,245,215),2,cv2.LINE_AA)
        return frame
