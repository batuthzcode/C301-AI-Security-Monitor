"""Ti AR Studio original procedural face filters, air painting and true 3D globe shader.

Uses OpenCV + NumPy; never opens camera or starts network requests.
"""
from __future__ import annotations
import math
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from ti_ar_core import face_geometry


def _blend_rgba(frame,rgba,center):
    h,w=frame.shape[:2];sh,sw=rgba.shape[:2]
    x=int(center[0]-sw/2);y=int(center[1]-sh/2)
    x0=max(0,x);y0=max(0,y);x1=min(w,x+sw);y1=min(h,y+sh)
    if x1<=x0 or y1<=y0:return frame
    patch=rgba[y0-y:y1-y,x0-x:x1-x]
    alpha=patch[:,:,3:4].astype(np.float32)/255
    roi=frame[y0:y1,x0:x1]
    roi[:]=(patch[:,:,:3]*alpha+roi*(1-alpha)).astype('uint8')
    return frame


@lru_cache(maxsize=20)
def _mask_sprite(style,size):
    size=max(40,min(640,int(size)));im=np.zeros((size,size,4),dtype=np.uint8)
    s=size/240
    def pt(x,y):return int(x*s),int(y*s)
    def ellipse(center,r,clr,th=-1,start=0,end=360):
        cv2.ellipse(im,pt(*center),pt(*r),0,start,end,clr,max(1,int(th*s)) if th>=0 else -1,cv2.LINE_AA)
    if style=='Muzip yüz (özgün)':
        # Original cartoon grin, not a copy of the third-party Trollface image.
        ellipse((120,118),(92,108),(240,244,251,250),-1)
        ellipse((120,118),(92,108),(40,40,40,255),4)
        ellipse((83,93),(22,11),(20,20,20,255),2)
        ellipse((156,90),(22,10),(20,20,20,255),2)
        ellipse((90,92),(6,7),(10,10,10,255))
        ellipse((152,90),(6,7),(10,10,10,255))
        ellipse((123,157),(65,36),(25,25,25,255),4,0,180)
        for x in range(80,171,18):cv2.line(im,pt(x,158),pt(x+4,180),(25,25,25,255),max(1,int(2*s)),cv2.LINE_AA)
    elif style=='Gözlük':
        # More natural lenses with lens gradient, polished frame, bridge and reflections.
        for cx in (67,173):
            for dy in range(-30,31):
                frac=abs(dy)/31
                color=(int(50+26*frac),int(42+32*frac),int(32+24*frac),205)
                cv2.line(im,pt(cx-46*math.sqrt(max(0,1-frac*frac)),110+dy),
                         pt(cx+46*math.sqrt(max(0,1-frac*frac)),110+dy),color,max(1,int(s)),cv2.LINE_AA)
            ellipse((cx,110),(49,33),(20,22,24,255),max(2,int(8*s)))
            cv2.line(im,pt(cx-28,91),pt(cx-12,85),(195,198,202,180),max(1,int(3*s)),cv2.LINE_AA)
        cv2.line(im,pt(116,107),pt(124,107),(30,30,35,255),max(2,int(8*s)),cv2.LINE_AA)
        cv2.line(im,pt(15,108),pt(0,100),(25,25,25,250),max(2,int(7*s)),cv2.LINE_AA)
        cv2.line(im,pt(225,108),pt(239,100),(25,25,25,250),max(2,int(7*s)),cv2.LINE_AA)
    elif style=='Bıyık':
        poly1=np.array([pt(*v) for v in [(116,153),(99,139),(75,146),(53,167),(83,175),(119,159)]],np.int32)
        poly2=np.array([pt(*v) for v in [(122,153),(144,138),(166,146),(189,167),(153,175),(121,159)]],np.int32)
        cv2.fillPoly(im,[poly1,poly2],(25,25,30,255),cv2.LINE_AA)
    elif style=='Şapka':
        cv2.ellipse(im,pt(121,55),pt(99,19),0,0,360,(20,50,190,255),-1,cv2.LINE_AA)
        cv2.rectangle(im,pt(55,0),pt(185,61),(35,80,220,255),-1)
        cv2.ellipse(im,pt(121,60),pt(113,19),0,0,360,(14,36,140,255),-1,cv2.LINE_AA)
    elif style=='Emoji':
        ellipse((120,120),(94,94),(0,213,255,240),-1)
        for x in (88,154):ellipse((x,104),(10,16),(20,20,20,255))
        ellipse((120,138),(50,35),(25,25,25,255),5,0,180)
    elif style=='Korku':
        ellipse((120,119),(93,102),(207,207,233,200),-1)
        for x in (82,156):ellipse((x,103),(25,38),(17,17,34,255))
        ellipse((120,169),(20,29),(15,14,33,255))
    return im



@lru_cache(maxsize=6)
def _load_custom_png(path,mtime):
    # Unicode Windows/OneDrive path safe; cached so disk isn't hit per frame.
    raw=np.fromfile(path,dtype=np.uint8)
    if raw.size>4_000_000:raise ValueError('PNG 4 MB sınırını aşmış')
    return cv2.imdecode(raw,cv2.IMREAD_UNCHANGED)


@lru_cache(maxsize=1)
def _earth_texture():
    path=Path(__file__).resolve().parent/'Ti_Dunya_Dokusu.jpg'
    if not path.is_file():return None
    tex=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_COLOR)
    return tex if tex is not None and tex.shape[1]>256 else None

def apply_face_mask(frame,faces,style,custom_png=None,max_faces=2):
    if style=='Kapalı':return frame
    for landmarks in faces[:max_faces]:
        geo=face_geometry(landmarks,frame.shape[1],frame.shape[0])
        if geo is None:continue
        x,y,fw,fh,roll=geo
        if custom_png and style=='Özel PNG':
            try:rgba=_load_custom_png(str(custom_png),Path(custom_png).stat().st_mtime_ns)
            except (OSError,ValueError,cv2.error):continue
            if rgba is None or rgba.ndim!=3 or rgba.shape[2]!=4:continue
        else:rgba=_mask_sprite(style,480)
        # Different anchor geometry for real face accessories; previously all
        # filters were stretched over the entire face like a flat sticker.
        if style=='Gözlük' and len(landmarks)>263:
            a,b=landmarks[33],landmarks[263]
            center=((a.x+b.x)*frame.shape[1]/2,(a.y+b.y)*frame.shape[0]/2)
            eye_distance=math.hypot((a.x-b.x)*frame.shape[1],(a.y-b.y)*frame.shape[0])
            dst_w=min(600,max(36,int(eye_distance*1.85)));dst_h=max(20,int(dst_w*.42))
        elif style=='Bıyık' and len(landmarks)>13:
            nose,lip=landmarks[1],landmarks[13]
            center=(lip.x*frame.shape[1],(nose.y*.30+lip.y*.70)*frame.shape[0])
            dst_w=min(380,max(32,int(fw*.80)));dst_h=max(24,int(dst_w*.46))
        elif style=='Şapka' and len(landmarks)>10:
            fore=landmarks[10];center=(fore.x*frame.shape[1],fore.y*frame.shape[0]-fh*.20)
            dst_w=min(580,max(45,int(fw*1.20)));dst_h=max(40,int(dst_w*.65))
        else:
            center=(x,y);dst_w=min(600,max(40,int(fw*1.25)));dst_h=min(650,max(50,int(fh*1.38)))
        rgba=cv2.resize(rgba,(dst_w,dst_h),interpolation=cv2.INTER_AREA if rgba.shape[1]>dst_w else cv2.INTER_LINEAR)
        m=cv2.getRotationMatrix2D((dst_w/2,dst_h/2),math.degrees(-roll),1)
        rgba=cv2.warpAffine(rgba,m,(dst_w,dst_h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        _blend_rgba(frame,rgba,center)
    return frame


def draw_strokes(frame,drawing):
    h,w=frame.shape[:2]
    for stroke in drawing.strokes:
        pts=stroke['points']
        if not pts:continue
        c=stroke['color'];clr=(c[2],c[1],c[0])
        q=np.array([(int(x*w),int(y*h)) for x,y in pts],dtype=np.int32)
        thickness=int(stroke['width'])
        if len(q)==1:cv2.circle(frame,tuple(q[0]),max(1,thickness//2),clr,-1,cv2.LINE_AA)
        else:cv2.polylines(frame,[q],False,clr,thickness,cv2.LINE_AA)
    return frame


def drawing_png(drawing,width=1280,height=720):
    out=np.zeros((height,width,4),dtype=np.uint8)
    for s in drawing.strokes:
        q=np.array([(int(x*width),int(y*height)) for x,y in s['points']],dtype=np.int32)
        if not len(q):continue
        r,g,b=s['color'];c=(b,g,r,255)
        if len(q)>1:cv2.polylines(out,[q],False,c,s['width'],cv2.LINE_AA)
        else:cv2.circle(out,tuple(q[0]),max(1,s['width']//2),c,-1,cv2.LINE_AA)
    return out


def _sphere_rgba(kind,radius,angle):
    """Pixelwise 3D hemisphere projection using sphere normals and rotation.
    A texture-like globe is generated mathematically; no image asset needed.
    """
    r=max(15,min(118,int(radius)))
    axis=np.arange(-r,r+1,dtype=np.float32)
    xx,yy=np.meshgrid(axis/r,axis/r)
    inside=xx*xx+yy*yy<=1
    zz=np.sqrt(np.maximum(0,1-xx*xx-yy*yy))
    # Rotate visible 3D sphere around its Y axis.
    ca,sa=math.cos(angle),math.sin(angle)
    x3=xx*ca+zz*sa;z3=-xx*sa+zz*ca
    lat=np.arcsin(np.clip(-yy,-1,1));lon=np.arctan2(x3,z3)
    light=np.clip(xx*(-.40)+(-yy)*(-.32)+zz*.86,.12,1)
    if kind=='3D Dünya':
        tex=_earth_texture()
        if tex is not None:
            th,tw=tex.shape[:2]
            mapx=np.mod((lon/(2*math.pi)+.5)*tw,tw).astype(np.float32)
            mapy=np.clip((.5-lat/math.pi)*th,0,th-1).astype(np.float32)
            rgb=cv2.remap(tex,mapx,mapy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP).astype(np.float32)
            # The source contains authentic NASA Blue Marble land/cloud imagery.
            # Keep the lighting physically plausible without increasing AR model FPS.
            lit=np.clip(.13+.93*np.clip(.8*zz-.35*xx-.18*yy,0,1),.13,1.0)
            rgb*=lit[...,None]
            highlight=np.maximum(0,.3*xx-.25*yy+.91*zz)**36
            ocean=(rgb[:,:,0] > rgb[:,:,2]*1.28).astype(np.float32)
            rgb+=((highlight*43*ocean)[...,None])
            haze=np.clip((1-zz)**4,0,1)
            rgb+=haze[...,None]*np.array([38,20,5])
        else:
            # Graceful fallback if the user removed the optional texture.
            rgb=np.zeros((*xx.shape,3),dtype=np.float32);rgb[:]=[180,95,30]
            rgb*=((.32+.68*light)[...,None])
    elif kind=='Ay':
        rgb=np.zeros((*xx.shape,3),np.float32);rgb[:]=[185,183,177]
        craters=np.sin(lon*19+lat*12)*np.cos(lon*27-lat*8)>.85
        rgb[craters]=[132,131,129]
    elif kind=='Futbol':
        rgb=np.full((*xx.shape,3),238,np.float32)
        pattern=(np.sin(lon*5)*np.cos(lat*6)>0.53)|(np.cos(lon*7)*np.sin(lat*5)<-.60)
        rgb[pattern]=[35,36,37]
    elif kind=='Kristal':
        rgb=np.zeros((*xx.shape,3),np.float32);rgb[:]=[237,120,160]
        facets=np.abs(np.sin(lon*9)+np.cos(lat*11))
        rgb[:,:,1]+=facets*70
    elif kind=='Mini Güneş':
        rgb=np.zeros((*xx.shape,3),np.float32)
        wave=40*np.abs(np.sin(lon*12+lat*6+angle))
        rgb[:,:,0]=20
        rgb[:,:,1]=165+wave*.7
        rgb[:,:,2]=240+wave*.25
    elif kind=='Ateş topu':
        rgb=np.zeros((*xx.shape,3),np.float32)
        rgb[:,:,0]=10+40*np.abs(np.sin(lat*8+angle))
        rgb[:,:,1]=100+100*np.abs(np.sin(lon*8-lat*5+angle))
        rgb[:,:,2]=220+35*np.sin(lon*11+angle)
    elif kind=='Enerji küresi':
        rgb=np.zeros((*xx.shape,3),np.float32);rgb[:]=[245,135,40]
        rgb[:,:,1]+=90*np.abs(np.sin(lon*12+angle))
    else:
        rgb=np.zeros((*xx.shape,3),np.float32);rgb[:]=[255,160,74]
    if kind!='3D Dünya':rgb*=((.32+.68*light)[...,None])
    rim=np.clip(1-zz,0,1)**4
    rgb=np.clip(rgb+(rim[...,None]*np.array([16,22,32])),0,255)
    # Antialiased round edge rather than jagged mask.
    a=(np.clip((1-xx*xx-yy*yy)*r*1.4,0,1)*255).astype(np.uint8)
    out=np.dstack((rgb.astype(np.uint8),a))
    return out


def draw_object(frame,center,radius,kind,rotation=0.0):
    if kind=='Kapalı':return frame
    x,y=int(center[0]),int(center[1]);r=max(15,min(118,int(radius)))
    sprite=_sphere_rgba('Enerji küresi' if kind in ('Güneş sistemi','Mini galaksi','Hologram küp') else kind,r,rotation)
    if kind=='Hologram küp':
        # Project eight true 3D cube vertices in front of the hand.
        a=rotation;ca,sa=math.cos(a),math.sin(a)
        verts=[]
        for X,Y,Z in [(-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),(1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1)]:
            xx=X*ca+Z*sa;zz=-X*sa+Z*ca
            scale=r*.63/(2.7-zz*.25)
            verts.append((int(x+xx*scale*2.6),int(y+Y*scale*2.6)))
        for i in range(8):
            for j in range(i+1,8):
                if (i^j) in (1,2,4):cv2.line(frame,verts[i],verts[j],(245,205,65),2,cv2.LINE_AA)
        return frame
    if kind=='Güneş sistemi':
        for a,b in [(r*1.65,r*.44),(r*1.18,r*.33)]:
            cv2.ellipse(frame,(x,y),(int(a),int(b)),int(rotation*10),0,360,(180,170,98),1,cv2.LINE_AA)
        _blend_rgba(frame,sprite,(x,y))
        for shift,clr in [(1.2,(250,200,90)),(2.1,(155,155,220))]:
            cx=int(x+math.cos(rotation+shift)*r*1.32);cy=int(y+math.sin(rotation+shift)*r*.35)
            cv2.circle(frame,(cx,cy),max(3,r//9),clr,-1,cv2.LINE_AA)
        return frame
    if kind=='Mini galaksi':
        for j in range(4):
            cv2.ellipse(frame,(x,y),(int(r*(1.1+j*.21)),int(r*(.3+j*.04))),int(rotation*18+j*24),0,330,(210,125+j*23,240),1,cv2.LINE_AA)
    _blend_rgba(frame,sprite,(x,y))
    if kind in ('Enerji küresi','Mini Güneş'):
        cv2.circle(frame,(x,y),r+4,(235,165,35),1,cv2.LINE_AA)
    return frame


def draw_sticker(frame,at,kind='Kalp'):
    h,w=frame.shape[:2];x=int(at[0]*w);y=int(at[1]*h)
    if kind=='Yıldız':
        pts=[]
        for i in range(10):
            a=i*math.pi/5-math.pi/2;r=22 if i%2==0 else 9
            pts.append((int(x+math.cos(a)*r),int(y+math.sin(a)*r)))
        cv2.fillPoly(frame,[np.array(pts,np.int32)],(20,230,250),cv2.LINE_AA)
    elif kind=='Ok':cv2.arrowedLine(frame,(x-25,y+18),(x+30,y-22),(110,220,255),4,cv2.LINE_AA,tipLength=.4)
    else:
        cv2.circle(frame,(x-9,y-7),12,(90,90,255),-1,cv2.LINE_AA)
        cv2.circle(frame,(x+9,y-7),12,(90,90,255),-1,cv2.LINE_AA)
        cv2.fillPoly(frame,[np.array([(x-21,y),(x,y+28),(x+21,y)],np.int32)],(90,90,255),cv2.LINE_AA)
    return frame
