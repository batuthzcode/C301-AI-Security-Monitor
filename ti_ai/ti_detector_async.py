"""Ti YOLO worker: isolate model loading/inference from camera and Qt GUI.

Messages are newline-delimited JSON sent over local pipes to a child Python
process. The child does not listen on a network port or access camera credentials.
Only one prediction may be in flight; there is no stale-frame queue.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from typing import Any

BASE = Path(__file__).resolve().parent


def _encode(obj: dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')


def child_main(*, mock=False):
    """Only invoked in an isolated subprocess; never in Qt's event loop."""
    try:
        # Constrain CPU consumption BEFORE importing torch/OpenCV/Ultralytics.
        os.environ.setdefault('OMP_NUM_THREADS', '2')
        os.environ.setdefault('MKL_NUM_THREADS', '2')
        os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
        os.environ.setdefault('NUMEXPR_NUM_THREADS', '2')
        import cv2
        import numpy as np
        if not mock:
            import torch
            torch.set_num_threads(2)
            try:torch.set_num_interop_threads(1)
            except RuntimeError:pass
            from ultralytics import YOLO
            model = os.environ.get('TI_DETECT_MODEL', 'yolo11n.pt')
            if not model.endswith('.pt') or '/' in model or '\\' in model or '..' in model:
                raise ValueError('Model adı geçersiz; yalnızca .pt dosyası adı destekleniyor.')
            candidate = BASE / model
            detector = YOLO(str(candidate) if candidate.exists() else model)
        print(json.dumps({'type':'ready'}), flush=True)
    except Exception as e:
        print(json.dumps({'type':'error', 'detail':f'{type(e).__name__}: {str(e)[:180]}'},ensure_ascii=False),flush=True)
        return 2

    for raw in sys.stdin.buffer:
        try:
            request = json.loads(raw)
            data = base64.b64decode(request['jpeg'],validate=True)
            frame = cv2.imdecode(np.frombuffer(data,dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:raise ValueError('JPEG görüntüsü çözümlenemedi')
            boxes=[];ids=[]
            if mock:
                time.sleep(float(request.get('mock_delay', 0.0)))
                boxes=[([0.2,0.2,0.8,0.8],'person',0.91)]
            else:
                predicting=detector.track if request.get('track') else detector.predict
                predictions = predicting(frame, imgsz=320, device='cpu',
                      conf=float(request['confidence']), classes=[0] if request['person_only'] else None,
                      max_det=25, verbose=False, **({'persist':True,'tracker':'bytetrack.yaml'} if request.get('track') else {}))
                if predictions and predictions[0].boxes is not None:
                    h,w=frame.shape[:2]
                    for b in predictions[0].boxes[:25]:
                        xyxy=[float(v) for v in b.xyxy[0].tolist()]
                        normalized=[xyxy[0]/w,xyxy[1]/h,xyxy[2]/w,xyxy[3]/h]
                        klass=int(b.cls[0]);name=str(predictions[0].names.get(klass,klass))
                        boxes.append((normalized,name,float(b.conf[0])))
                        ids.append(int(b.id[0]) if b.id is not None else None)
            print(json.dumps({'type':'result','boxes':boxes,'ids':ids}), flush=True)
        except Exception as e:
            print(json.dumps({'type':'error','detail':f'{type(e).__name__}: {str(e)[:180]}'}, ensure_ascii=False),flush=True)
            return 3
    return 0


class AsyncDetector:
    """Nonblocking producer: one in-flight inference, at most 1 pending frame."""
    def __init__(self, model: str='yolo11n.pt', *, interval: float=0.75, mock: bool=False):
        self.interval=max(0.3,float(interval));self.mock=mock
        self.stopped=threading.Event()
        self.ready=False
        self._busy=False
        self._lock=threading.Lock()
        self._last_submitted=0.0
        self._last_result=0.0
        self._events=queue.Queue(maxsize=8)
        self._frames=queue.Queue(maxsize=1)
        self._reader=None;self._sender=None
        env=os.environ.copy()
        env.update({'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2',
                    'NUMEXPR_NUM_THREADS':'2','TI_DETECT_MODEL':str(model)})
        command=[sys.executable, '-u', str(BASE/'ti_detector_async.py'), '--worker']
        if mock:command.append('--mock')
        # Log child stderr to disk, not to a PIPE that can fill and freeze it.
        log_dir=BASE/'Ti_Veriler';log_dir.mkdir(parents=True,exist_ok=True)
        log_file=open(log_dir/'ti_yolo.log','ab')
        try:
            self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=log_file,env=env,bufsize=0,
                creationflags=(getattr(subprocess,'CREATE_NO_WINDOW',0) |
                               getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0)))
        finally:log_file.close()
        self._reader=threading.Thread(target=self._read,daemon=True,name='TiYOLO-Reader')
        self._sender=threading.Thread(target=self._send,daemon=True,name='TiYOLO-Sender')
        self._reader.start();self._sender.start()

    def _event(self, item):
        try:self._events.put_nowait(item)
        except queue.Full:
            try:self._events.get_nowait()
            except queue.Empty:pass
            self._events.put_nowait(item)

    def _read(self):
        try:
            for line in self.process.stdout:
                if self.stopped.is_set():break
                payload=json.loads(line)
                typ=payload.get('type')
                if typ=='ready':
                    with self._lock:self.ready=True
                    self._event(('ready',None))
                elif typ=='result':
                    with self._lock:
                        self._busy=False
                        self._last_result=time.monotonic()
                    self._event(('track_ids',payload.get('ids',[])))
                    self._event(('result',payload.get('boxes',[])))
                elif typ=='error':
                    self._event(('error',str(payload.get('detail','Bilinmeyen hata'))[:200]))
                    return
        except (OSError,ValueError,TypeError) as exc:
            if not self.stopped.is_set():self._event(('error',str(exc)[:150]))
        finally:
            if not self.stopped.is_set():
                self._event(('error','YOLO alt işlemi sonlandı; Ti_Veriler/ti_yolo.log dosyasını kontrol edin.'))

    def _send(self):
        while not self.stopped.is_set():
            try:frame,conf,person_only,delay,track=self._frames.get(timeout=.2)
            except queue.Empty:continue
            try:
                import cv2
                small=cv2.resize(frame,(424,240),interpolation=cv2.INTER_AREA)
                ok,jpeg=cv2.imencode('.jpg',small,[cv2.IMWRITE_JPEG_QUALITY,65])
                if not ok:raise RuntimeError('JPEG hazırlanamadı')
                message={'jpeg':base64.b64encode(jpeg.tobytes()).decode('ascii'),
                         'confidence':conf,'person_only':person_only,'track':track}
                if self.mock:message['mock_delay']=delay
                self.process.stdin.write(_encode(message))
                self.process.stdin.flush()
            except (BrokenPipeError,OSError,ValueError,RuntimeError) as exc:
                if not self.stopped.is_set():self._event(('error','YOLO iletişimi: '+str(exc)[:150]))
                break

    def submit(self, frame, confidence=.45, person_only=False, *, mock_delay=0.0, track=False):
        """Never waits for inference. Returns False if busy/not ready/throttled."""
        now=time.monotonic()
        with self._lock:
            if self.stopped.is_set() or not self.ready or self._busy or (now-self._last_submitted)<self.interval:
                return False
            self._busy=True
            self._last_submitted=now
        try:
            self._frames.put_nowait((frame.copy(),float(confidence),bool(person_only),float(mock_delay),bool(track)))
            return True
        except queue.Full:
            with self._lock:self._busy=False
            return False

    def poll(self):
        messages=[]
        while True:
            try:messages.append(self._events.get_nowait())
            except queue.Empty:break
        if self.process.poll() is not None and not self.stopped.is_set() and not any(k=='error' for k,_ in messages):
            messages.append(('error',f'YOLO işlemi kapandı (kod: {self.process.returncode}).'))
        # If YOLO hung in prediction, terminate/restart via UI instead of blocking capture.
        with self._lock:
            timed_out=self.ready and self._busy and (time.monotonic()-self._last_submitted)>20
        if timed_out and not any(k=='error' for k,_ in messages):
            messages.append(('error','YOLO 20 saniye yanıt vermedi. Algılama kapatıldı.'))
        return messages

    def stop(self):
        if self.stopped.is_set():return
        self.stopped.set()
        if self.process.poll() is None:
            try:self.process.terminate()
            except OSError:pass
        try:self.process.wait(timeout=.8)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:self.process.wait(timeout=.5)
            except subprocess.TimeoutExpired:pass
        try:self.process.stdin.close();self.process.stdout.close()
        except (OSError,ValueError):pass


if __name__=='__main__':
    if '--worker' not in sys.argv:
        print('Ti YOLO yardımcı işlemi. Doğrudan başlatılmaz.')
        sys.exit(1)
    sys.exit(child_main(mock='--mock' in sys.argv))
