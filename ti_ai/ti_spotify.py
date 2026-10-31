"""Spotify authorization-code PKCE, loopback 127.0.0.1 only.
No Spotify credentials/tokens are written to disk. Token kept in session memory.
User must create Spotify Developer app and register exact redirect URI.
"""
from __future__ import annotations
import base64
import hashlib
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import secrets
import threading
import time
from urllib.parse import urlencode,urlsplit,parse_qs,quote
import urllib.error
import urllib.request
import webbrowser

REDIRECT='http://127.0.0.1:8795/callback'
SCOPES='user-read-playback-state user-modify-playback-state user-read-currently-playing'


class SpotifyConnection:
    def __init__(self):
        self.client_id=''
        self.access=''
        self.refresh_token=''
        self.expires_at=0
        self._lock=threading.RLock()
        self._auth_active=False

    @property
    def connected(self):
        return bool(self.access or self.refresh_token)

    def disconnect(self):
        with self._lock:
            self.access='';self.refresh_token='';self.expires_at=0

    def connect(self,client_id,on_status):
        if not (len(client_id)>=18 and client_id.replace('-','').isalnum()):
            on_status(False,'Spotify Client ID geçersiz. Ayarlar bölümüne Spotify Developer Client ID gir.');return
        with self._lock:
            if self._auth_active:
                on_status(False,'Spotify bağlantısı zaten bekleniyor.');return
            self._auth_active=True
        self.client_id=client_id
        threading.Thread(target=self._authorize,args=(on_status,),daemon=True,name='TiSpotifyOAuth').start()

    def _authorize(self,on_status):
        verifier=secrets.token_urlsafe(60)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).decode('ascii').rstrip('=')
        state=secrets.token_urlsafe(24)
        result={}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path=urlsplit(self.path)
                if path.path!='/callback':
                    self.send_error(404);return
                q=parse_qs(path.query)
                if q.get('state',[''])[0]!=state:
                    self.send_error(403,'OAuth state mismatch');result['error']='OAuth onayı güvenlik kontrolünden geçmedi';return
                result['code']=q.get('code',[''])[0]
                result['error']=q.get('error',[''])[0]
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers()
                self.wfile.write('<html><meta charset="utf-8"><body style="font-family:Segoe UI"><h2>Ti / Spotify</h2><p>Bu pencereyi kapatıp Ti uygulamasına dönebilirsin.</p></body></html>'.encode())
            def log_message(self,*args):pass
        try:
            server=HTTPServer(('127.0.0.1',8795),Handler)
            server.timeout=120
            query=urlencode({'response_type':'code','client_id':self.client_id,'redirect_uri':REDIRECT,
                    'code_challenge_method':'S256','code_challenge':challenge,'state':state,'scope':SCOPES})
            webbrowser.open('https://accounts.spotify.com/authorize?'+query)
            server.handle_request()
            server.server_close()
            if not result.get('code'):
                raise RuntimeError('Spotify yetkilendirmesi tamamlanmadı: '+result.get('error','zaman aşımı'))
            tokens=self._post_token({'grant_type':'authorization_code','code':result['code'],
                         'redirect_uri':REDIRECT,'client_id':self.client_id,'code_verifier':verifier})
            self._apply_tokens(tokens)
            on_status(True,'Spotify hesabı bağlandı. Artık şarkı komutlarını deneyebilirsin.')
        except (OSError,ValueError,RuntimeError) as e:
            on_status(False,'Spotify bağlantısı başarısız: '+str(e)[:180])
        finally:
            with self._lock:self._auth_active=False

    @staticmethod
    def _post_token(data):
        body=urlencode(data).encode()
        request=urllib.request.Request('https://accounts.spotify.com/api/token',data=body,
                          headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=15) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError('Spotify token HTTP '+str(e.code)) from None

    def _apply_tokens(self,data):
        with self._lock:
            self.access=data['access_token'];self.expires_at=time.time()+int(data.get('expires_in',3600))-40
            if data.get('refresh_token'):self.refresh_token=data['refresh_token']

    def _token(self):
        with self._lock:
            if not self.connected:raise RuntimeError('Spotify hesabı bağlı değil.')
            if time.time()<self.expires_at:return self.access
            if not self.refresh_token:raise RuntimeError('Spotify oturum süresi doldu. Yeniden bağlan.')
            data=self._post_token({'grant_type':'refresh_token','refresh_token':self.refresh_token,'client_id':self.client_id})
            self._apply_tokens(data)
            return self.access

    def _api(self,method,path,data=None):
        body=json.dumps(data).encode('utf-8') if data is not None else None
        req=urllib.request.Request('https://api.spotify.com/v1/'+path.lstrip('/'),
                 headers={'Authorization':'Bearer '+self._token(),'Content-Type':'application/json'},
                 data=body,method=method)
        try:
            with urllib.request.urlopen(req,timeout=16) as resp:
                raw=resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code==403:raise RuntimeError('Spotify izin vermedi. Premium hesap ve izinleri kontrol et.') from None
            if e.code==404:raise RuntimeError('Aktif Spotify oynatma cihazı bulunamadı.') from None
            if e.code==401:raise RuntimeError('Spotify oturumu geçersiz. Yeniden bağlan.') from None
            if e.code==429:raise RuntimeError('Spotify istek sınırı; daha sonra dene.') from None
            raise RuntimeError('Spotify API HTTP '+str(e.code)) from None

    def play_song(self,query):
        if not self.connected:return False,'Spotify bağlantısı yapılmadı.'
        try:
            res=self._api('GET','search?'+urlencode({'q':query,'type':'track','limit':5}))
            items=res.get('tracks',{}).get('items',[])
            if not items:raise RuntimeError('Spotify şarkıyı bulamadı.')
            track=items[0]
            devices=self._api('GET','me/player/devices').get('devices',[])
            if not devices:raise RuntimeError('Spotify uygulamasını aç ve bir çalma cihazını etkinleştir.')
            device=next((d for d in devices if d.get('is_active')),devices[0])
            id_=device.get('id')
            if not id_:raise RuntimeError('Spotify çalma cihazı kimliği alınamadı.')
            self._api('PUT','me/player/play?'+urlencode({'device_id':id_}),{'uris':[track['uri']]})
            return True, f"{track['name']} — {track['artists'][0]['name']} Spotify'da oynatılıyor."
        except (RuntimeError,OSError,KeyError,IndexError,ValueError) as e:
            return False,str(e)[:220]
