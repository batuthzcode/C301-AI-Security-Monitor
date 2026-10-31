"""Ti AR Studio pure geometry and gesture recognition. No device/network access.

Normalized landmark input is compatible with MediaPipe Tasks' x/y/z values.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import hypot
from pathlib import Path
import math

MASKS = ('Kapalı','Muzip yüz (özgün)','Gözlük','Bıyık','Şapka','Emoji','Korku','Özel PNG')
OBJECTS = ('Kapalı','3D Dünya','Ay','Mini Güneş','Ateş topu','Enerji küresi','Futbol','Kristal','Güneş sistemi','Hologram küp','Mini galaksi')
COLORS = ((255,230,50),(90,220,255),(255,90,110),(80,255,130),(200,100,255),(255,255,255)) # RGB

@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float=0.0

def coords(landmarks):
    return tuple(Point(float(p.x),float(p.y),float(getattr(p,'z',0))) for p in landmarks)

def dist(a,b):
    return hypot(a.x-b.x,a.y-b.y)

def hand_gesture(lm):
    """Detect draw/select/erase/palm/pause from 21 landmarks.

    Ordering follows MediaPipe Hands. Thumb and index pinch must be close
    relative to palm size, so hands at different camera distances work.
    """
    if len(lm)!=21: return 'none'
    palm=max(0.018, dist(lm[0],lm[9]))
    # A finger is extended when its tip lies significantly farther from the
    # wrist than the PIP joint. This works at many rotations, not all poses.
    up=[dist(lm[t],lm[0]) > dist(lm[p],lm[0])*1.14 for t,p in [(8,6),(12,10),(16,14),(20,18)]]
    if dist(lm[4],lm[8])<palm*0.32: return 'erase'
    if sum(up)>=4:return 'palm'
    if up[0] and up[1] and not up[2] and not up[3]:return 'select'
    if up[0] and not any(up[1:]):return 'draw'
    if not any(up):return 'pause'
    return 'idle'

def palm_anchor(lm):
    if len(lm)!=21:return Point(.5,.5)
    p=[lm[i] for i in (0,5,9,13,17)]
    return Point(sum(a.x for a in p)/5,sum(a.y for a in p)/5)

def index_tip(lm):
    return lm[8] if len(lm)==21 else Point(0.5,0.5)

def face_geometry(lm,width,height):
    """Return aligned face center, width, height, roll angle in radians."""
    if len(lm)<264: return None
    left,right=lm[33],lm[263]
    angle=math.atan2((right.y-left.y)*height,(right.x-left.x)*width)
    xs=[p.x for p in lm];ys=[p.y for p in lm]
    cx=(min(xs)+max(xs))*.5*width
    cy=(min(ys)+max(ys))*.5*height
    fw=max(15,(max(xs)-min(xs))*width)
    fh=max(20,(max(ys)-min(ys))*height)
    return cx,cy,fw,fh,angle

class Drawing:
    """Bounded stroke storage: no unbounded RAM use on long sessions."""
    def __init__(self,max_points=2400,max_strokes=90):
        self.max_points=max_points
        self.max_strokes=max_strokes
        self.strokes=[]
        self.active=False
        self.color=COLORS[0]
        self.width=5
        self.last=None

    def begin(self,color=None,width=None):
        if self.active:return
        self.active=True
        self.color=color or self.color
        self.width=width or self.width
        self.strokes.append({'color':tuple(self.color),'width':int(self.width),'points':[]})
        self.strokes=self.strokes[-self.max_strokes:]
        self.last=None

    def end(self):
        self.active=False
        self.last=None

    def point(self,x,y):
        if not self.active:return False
        x=max(0,min(1,float(x)));y=max(0,min(1,float(y)))
        if self.last:
            x=self.last[0]*.35+x*.65;y=self.last[1]*.35+y*.65
            if hypot(x-self.last[0],y-self.last[1])<.003:return False
        self.last=(x,y)
        self.strokes[-1]['points'].append((x,y))
        self._trim()
        return True

    def _trim(self):
        # Remove oldest complete strokes first; then bound the current stroke.
        count=sum(len(s['points']) for s in self.strokes)
        while count>self.max_points and len(self.strokes)>1:
            count-=len(self.strokes.pop(0)['points'])
        if count>self.max_points:
            self.strokes[0]['points']=self.strokes[0]['points'][-self.max_points:]

    def erase(self,x,y,radius=.055):
        """Remove any stroke touched by the eraser."""
        remaining=[];removed=0
        for stroke in self.strokes:
            if any(hypot(px-x,py-y)<radius for px,py in stroke['points']):removed+=1
            else:remaining.append(stroke)
        self.strokes=remaining
        if removed:self.end()
        return removed

    def clear(self):
        self.strokes.clear();self.end()

    def __len__(self):return sum(len(s['points']) for s in self.strokes)


def valid_png(path):
    p=Path(path).expanduser().resolve()
    if not p.is_file() or p.suffix.lower()!='.png' or p.stat().st_size>4_000_000:
        raise ValueError('Özel maske için 4 MB altı gerçek bir PNG seçin.')
    return p
