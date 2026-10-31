"""Explicitly enabled mobile control panel with bearer auth and optional TLS.
By default binds ONLY to loopback; LAN access requires user TLS certificate and key.
It never serves RTSP streams, credentials, captures or unrestricted files.
"""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import secrets
import ssl
import threading
import urllib.parse

PAGE="""<!doctype html><html lang='tr'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Ti AI Mobil Kontrol</title><style>body{font-family:system-ui;background:#111c30;color:#f0f6ff;margin:auto;max-width:650px;padding:20px}button,input{padding:14px;margin:6px;border-radius:9px}button{background:#2675e7;color:white;border:0}pre{white-space:pre-wrap}</style>
<h1>Ti AI • Mobil Kontrol</h1><p>Bu panel yalnızca yetkilendirilmiş kullanıcı içindir. Token bu sayfada kalır.</p><input id='key' type='password' placeholder='TI_WEB_TOKEN'><button onclick='refresh()'>Durumu Yenile</button>
<div><button onclick="act('follow_start')">Takibi Başlat</button><button onclick="act('follow_stop')">Takibi Durdur</button><button onclick="act('privacy_on')">Gizlilik Aç</button><button onclick="act('snapshot')">Fotoğraf Çek</button></div><pre id='output'>Hazır</pre>
<script>const show=x=>document.getElementById('output').textContent=typeof x==='string'?x:JSON.stringify(x,null,2);
async function query(p,m='GET',data){try{let r=await fetch(p,{method:m,headers:{'Authorization':'Bearer '+document.getElementById('key').value,'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});show({status:r.status,result:await r.json()})}catch(e){show('Bağlantı hatası: '+e.message)}}
function refresh(){query('/api/status')} function act(name){query('/api/control','POST',{action:name})}</script></html>"""
ACTIONS={'follow_start','follow_stop','privacy_on','snapshot'}


class MobileServer:
    def __init__(self,status,command,*,token=None,host='127.0.0.1',port=8765,certfile=None,keyfile=None):
        self.status=status
        self.command=command
        self.token=(token or os.environ.get('TI_WEB_TOKEN','')).strip()
        if len(self.token)<24:raise RuntimeError('TI_WEB_TOKEN en az 24 karakter olmalı. Gizli tut.')
        if host not in ('127.0.0.1','localhost') and (not certfile or not keyfile):
            raise RuntimeError('Telefon/LAN erişimi için TLS sertifikası ve anahtar zorunlu.')
        self._host=host
        parent=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def authorized(self):
                provided=self.headers.get('Authorization','')
                return hmac.compare_digest(provided,'Bearer '+parent.token)
            def reply(self,code,result):
                data=json.dumps(result,ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
            def do_GET(self):
                if self.path=='/':
                    page=PAGE.encode('utf-8');self.send_response(200)
                    self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Content-Security-Policy',"default-src 'self' 'unsafe-inline'; connect-src 'self'")
                    self.send_header('Content-Length',str(len(page)));self.end_headers();self.wfile.write(page);return
                if not self.authorized():return self.reply(401,{'error':'Yetki gerekli'})
                if self.path=='/api/status':return self.reply(200,parent.status())
                return self.reply(404,{'error':'Bulunamadı'})
            def do_POST(self):
                if not self.authorized():return self.reply(401,{'error':'Yetki gerekli'})
                if self.path!='/api/control':return self.reply(404,{'error':'Bulunamadı'})
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if length>800 or length<=0:return self.reply(400,{'error':'İstek boyutu geçersiz'})
                    body=json.loads(self.rfile.read(length))
                    name=body.get('action','')
                    if name not in ACTIONS:return self.reply(400,{'error':'İzin verilmeyen işlem'})
                    parent.command(name)
                    return self.reply(202,{'queued':name})
                except (ValueError,TypeError,AttributeError):
                    return self.reply(400,{'error':'Geçersiz JSON'})
        self.server=ThreadingHTTPServer((host,int(port)),Handler)
        self.server.daemon_threads=True
        if certfile and keyfile:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(certfile,keyfile)
            self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
        self.url=('https' if certfile else 'http')+'://'+host+':'+str(self.server.server_address[1])
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name='Ti-MobilePanel')
    def start(self):self.thread.start();return self.url
    def stop(self):
        if self.thread.is_alive():self.server.shutdown();self.thread.join(timeout=2)
        self.server.server_close()
