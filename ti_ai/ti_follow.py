"""Responsive person-follow controller using EXISTING detections and bounded PTZ.

No camera / YOLO thread is created here. PTZ remains opt-in and can be disabled.
Physical movement limits cannot be inferred from RTSP images; do not bypass firmware limits.
"""
from __future__ import annotations
from collections import deque
import threading
import time
from ti_v1_core import TiPersonFollower


class SharedVisualFollower:
    """Follow one unambiguous person; rate-limit each PTZ step and handle video lag.

    Unlike v1.3.2, a non-improving frame after *one* move does not disable
    following. Repeated non-improvement produces a visible cooldown instead.
    """

    def __init__(self, motor, post, *, max_steps=4):
        self.motor = motor
        self.post = post
        self.max_steps = max(1, min(int(max_steps), 12))  # per rolling minute
        self._lock = threading.RLock()
        self._active = False
        self._session = 0
        self._until = 0.0
        self._recent_moves = deque()
        self._last_direction = None
        self._stable = 0
        self._moving = False
        self._check = None
        self._stagnant = 0
        self._pause_until = 0.0
        self._last_command_at = 0.0
        self._status = None
        self._target_point = None
        self._target_id = None
        self._target_seen = 0.0
        self.calibration = []  # Observed relative x-shift, not physical degrees.

    @property
    def active(self):
        with self._lock:
            return self._active

    def _emit(self, message):
        if message != self._status:
            self._status = message
            self.post('follow_status', message)

    def select_target(self, nx:float, ny:float):
        if not (0 <= nx <= 1 and 0 <= ny <= 1):raise ValueError('Hedef koordinatı 0–1 aralığında olmalı.')
        with self._lock:
            self._target_point=(nx,ny)
            self._target_id=None
            self._target_seen=time.monotonic()
            self._stable=0
            self._last_direction=None
            self._emit('Kilit hedefi seçildi; kişi algılaması bekleniyor.')

    def clear_target(self):
        with self._lock:
            self._target_point=None;self._target_id=None
            self._emit('Hedef kilidi temizlendi.')

    def calibration_report(self):
        with self._lock:
            if not self.calibration:return 'Kalibrasyon: Henüz ölçüm yok. Gerçek PTZ hareketinden sonra gözlemle.'
            values=self.calibration[-10:]
            return f'Kalibrasyon: {len(values)} örnek, ortalama yatay değişim {sum(values)/len(values):.3f} kadraj.'

    def enable(self, *, seconds=None, max_steps_per_minute=None):
        with self._lock:
            self._session += 1
            self._active = True
            duration = min(1800.0, max(5.0, float(600 if seconds is None else seconds)))
            self.max_steps = max(1, min(int(max_steps_per_minute or self.max_steps), 12))
            self._until = time.monotonic() + duration
            self._recent_moves.clear()
            self._stagnant = 0
            self._pause_until = 0.0
            self._stable = 0
            self._last_direction = None
            self._moving = False
            self._check = None
            self._last_command_at = 0.0
            self._emit(f'Takip açık: {duration/60:g} dk; dakikada en fazla {self.max_steps} motor adımı.')
        return True, 'Tek YOLO akışıyla sürekli kişi takibi açıldı. Motor yalnızca yerel PTZ API destekleniyorsa hareket eder.'

    def disable(self, reason='Kişi takibi durduruldu.'):
        with self._lock:
            self._session += 1
            was_active = self._active
            self._active = False
            self._moving = False
            self._check = None
            self._stable = 0
            self._last_direction = None
            if was_active:
                self._emit(reason)
        return was_active

    def close(self):
        self.disable()

    def on_detections(self, boxes, frame_width, frame_height, *, now=None, track_ids=None):
        """Consume fresh detections; no motor move occurs on caller's thread."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if not self._active:
                return
            if now >= self._until:
                self.disable('Ayarlanan takip süresi bitti; Takibi Başlat ile yeniden açabilirsin.')
                return
            people = [(b, (track_ids[i] if track_ids and i<len(track_ids) else None))
                      for i,b in enumerate(boxes) if b[1] == 'person']
            if self._target_point is not None and people and frame_width>0 and frame_height>0:
                if self._target_id is None:
                    px,py=self._target_point
                    candidates=sorted(people,key=lambda item:(((item[0][0][0]+item[0][0][2])/2/frame_width-px)**2+
                        ((item[0][0][1]+item[0][0][3])/2/frame_height-py)**2))
                    chosen, identity=candidates[0]
                    bounds=chosen[0]
                    if (bounds[0]/frame_width-.08 <= px <= bounds[2]/frame_width+.08 and
                        bounds[1]/frame_height-.08 <= py <= bounds[3]/frame_height+.08):
                        if identity is None and len(people)>1:
                            people=[]  # No reliable ID: cannot safely choose among people.
                        else:
                            self._target_id=identity
                            people=[(chosen,identity)]
                        self._target_seen=now
                    else:people=[]
                elif track_ids:
                    people=[(b,i) for b,i in people if i==self._target_id]
                    if people:self._target_seen=now
                else:
                    # Tracker lost IDs: suspend motor to avoid following wrong person.
                    people=[]
            if len(people) != 1 or frame_width <= 0 or frame_height <= 0:
                self._stable = 0
                self._last_direction = None
                self._check = None
                self._emit('Kilitli kişi bekleniyor; motor güvenlik için duruyor.' if self._target_point is not None else ('Bir kişi bekleniyor.' if not people else 'Birden fazla kişi var; motor hareket etmiyor.'))
                return
            coords = people[0][0][0]
            x = (coords[0] + coords[2]) / (2.0 * frame_width) - 0.5
            y = (coords[1] + coords[3]) / (2.0 * frame_height) - 0.5
            direction = TiPersonFollower.direction_for_offset(x, y, vertical=False)
            if self._moving:
                return
            if self._check is not None:
                axis, before, completed = self._check
                if now - completed < 4.5:
                    self._emit('Motor hareket etti; yeni kamera görüntüsü bekleniyor.')
                    return
                after = x if axis == 'x' else y
                improved = abs(after) < abs(before) - 0.04
                if improved:
                    self._stagnant = 0
                    if axis == 'x': self.calibration.append(round(abs(after-before),4))
                    if len(self.calibration)>20:self.calibration.pop(0)
                elif direction is not None:
                    self._stagnant += 1
                self._check = None
                self._stable = 0
                self._last_direction = None
                if self._stagnant >= 3:
                    self._pause_until = now + 30.0
                    self._stagnant = 0
                    self._emit('Hedef merkeze yaklaşmıyor: motor 30 sn dinlendiriliyor; takip açık.')
                    return
            if direction is None:
                self._stagnant = 0
                self._stable = 0
                self._last_direction = None
                self._emit('Kişi kadraj merkezinde. İzleme sürüyor.')
                return
            if not self.motor.enabled:
                self._emit('Kişi algılandı; Motor Kontrolü kapalı olduğu için kamera dönmüyor.')
                return
            if now < self._pause_until:
                self._emit('Motor dinleniyor; kişi görsel olarak izleniyor.')
                return
            if now - self._last_command_at < 3.2:
                return
            while self._recent_moves and now - self._recent_moves[0] >= 60.0:
                self._recent_moves.popleft()
            if len(self._recent_moves) >= self.max_steps:
                self._emit('Dakikalık motor sınırına ulaşıldı; takip açık, motor beklemede.')
                return
            if direction == self._last_direction:
                self._stable += 1
            else:
                self._stable = 1
                self._last_direction = direction
            if self._stable < 2:
                self._emit('Kişi algılandı; konum ikinci karede doğrulanıyor.')
                return
            self._moving = True
            session = self._session
            self._emit('Kişi merkez dışında; PTZ komutu gönderiliyor...')
            threading.Thread(target=self._move, args=(session, direction, x),
                             name='Ti-Follow-Motor', daemon=True).start()

    def _move(self, session, direction, before):
        with self._lock:
            if not self._active or session != self._session:
                return
        try:
            ok, message = self.motor.move(direction)
        except Exception as exc:
            ok, message = False, str(exc)[:150]
        with self._lock:
            if session != self._session or not self._active:
                return
            self._moving = False
            if not ok:
                if 'bekleme süresi' in message or 'bekleme' in message:
                    self._stable = 0
                    self._last_direction = None
                    self._emit('PTZ bekleme süresi; izleme devam ediyor.')
                else:
                    self.disable('PTZ kullanılamadı: ' + str(message)[:150])
                return
            moment = time.monotonic()
            self._last_command_at = moment
            self._recent_moves.append(moment)
            self._stable = 0
            self._last_direction = None
            self._check = ('x', before, moment)
            self._emit(f'Motor hareketi gönderildi ({len(self._recent_moves)}/{self.max_steps} dakikalık hak); doğrulanıyor.')
