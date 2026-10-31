"""Ti Lab: opt-in AI chat/research and local, read-only improvement planning.

No autonomous tool calls, shell execution, code modification or camera upload.
Requires the user's separately configured API key for internet research.
"""
from __future__ import annotations
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import urllib.error
import urllib.request

SYSTEM_PROMPT = ("Sen Ti adlı Türkçe kişisel yapay zekâ asistanısın. "
                 "Kendini gerçek insan olarak tanıtma. Gizli bilgiler talep etme. "
                 "Doğrulanmamış sonucu doğrulanmış gibi sunma. "
                 "Kullanıcının bilgisayarında kod veya komut çalıştıramazsın. "
                 "Kamera görüntüsü ve özel dosyalar sana gönderilmez.")


class KnowledgeBook:
    """Explicitly user-written notes; never auto-ingests camera/audio data."""
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=3)) as con:
            con.execute('CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, created TEXT, title TEXT, body TEXT)')
            con.commit()

    def add(self, title, body):
        title=str(title).strip()[:120]
        body=str(body).strip()[:4000]
        if not title or not body:
            raise ValueError('Başlık ve not içeriği boş olamaz.')
        with closing(sqlite3.connect(self.path, timeout=3)) as con:
            cursor=con.execute('INSERT INTO notes (created,title,body) VALUES (?,?,?)',
                               (datetime.now().isoformat(timespec='seconds'),title,body))
            con.commit()
            return cursor.lastrowid

    def search(self, term='', limit=40):
        term=str(term).strip()[:100]
        with closing(sqlite3.connect(self.path, timeout=3)) as con:
            if term:
                escaped=term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
                return con.execute("SELECT id,created,title,body FROM notes WHERE title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?",
                        (f'%{escaped}%',f'%{escaped}%', min(200,int(limit)))).fetchall()
            return con.execute('SELECT id,created,title,body FROM notes ORDER BY id DESC LIMIT ?',
                               (min(200,int(limit)),)).fetchall()


def _api_output(blob):
    chunks=[]
    for msg in blob.get('output',[]):
        if msg.get('type')=='message':
            for section in msg.get('content',[]):
                if section.get('type')=='output_text' and isinstance(section.get('text'),str):
                    chunks.append(section['text'])
                    for item in section.get('annotations',[]):
                        url=item.get('url','')
                        if item.get('type')=='url_citation' and url.startswith('https://'):
                            chunks.append('\nKaynak: '+url)
    return '\n'.join(chunks).strip() or '(Model yanıt metni döndürmedi.)'


def _post_json(url, body, headers=None, timeout=45):
    data=json.dumps(body,ensure_ascii=False).encode('utf-8')
    request=urllib.request.Request(url,data=data,headers={
        'Content-Type':'application/json', **(headers or {})},method='POST')
    try:
        with urllib.request.urlopen(request, timeout=timeout) as r:
            if r.status != 200:
                raise RuntimeError(f'HTTP {r.status}')
            response=r.read(1_200_001)
            if len(response)>1_200_000:raise RuntimeError('Yanıt boyutu sınırı aşıldı.')
            return json.loads(response)
    except urllib.error.HTTPError as exc:
        if exc.code==401: raise RuntimeError('API anahtarı geçersiz veya yetkisiz (401).') from exc
        if exc.code==429: raise RuntimeError('API kullanım limiti veya kredisi aşıldı (429).') from exc
        raise RuntimeError('AI hizmeti HTTP '+str(exc.code)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError('AI servisine erişilemiyor veya zaman aşımına uğradı.') from exc


def ask_ti(question, *, research=False, improvement_context=None, local_model=None, api_key=None):
    """No programmatic commands, only plain-text answers; network usage is user-triggered."""
    question=str(question).strip()
    if not question or len(question)>3000:
        raise ValueError('1-3000 karakterlik bir soru yaz.')
    if improvement_context:
        prompt=SYSTEM_PROMPT+'\nYalnızca onaya sunulan geliştirme önerileri üret; kodu değiştirme.'
        question=('Aşağıdaki anonim yerel tanı özeti için test edilebilir, öncelikli gelişim planı '
                  'hazırla. Öneriler: risk, beklenen fayda ve test önerisi içersin.\n'
                  +str(improvement_context)[:1700]+'\nİstek: '+question)
    else:
        prompt=SYSTEM_PROMPT
    key=(api_key or os.environ.get('OPENAI_API_KEY','')).strip()
    if research and not key:
        raise RuntimeError('İnternet araştırması için OPENAI_API_KEY ortam değişkeni gerekli. ChatGPT aboneliği API anahtarı yerine geçmez.')
    if key:
        model=os.environ.get('TI_OPENAI_MODEL','gpt-5.5').strip()
        if not re.fullmatch(r'[a-zA-Z0-9._-]{2,55}',model):
            raise RuntimeError('TI_OPENAI_MODEL adı geçersiz.')
        payload={'model':model,'instructions':prompt,'input':question,
                 'max_output_tokens':1200,'store':False}
        if research:payload['tools']=[{'type':'web_search'}];payload['tool_choice']='required'
        data=_post_json('https://api.openai.com/v1/responses',payload,
                        headers={'Authorization':'Bearer '+key},timeout=75 if research else 45)
        return _api_output(data)
    if local_model:
        model=local_model.strip()
        if not re.fullmatch(r'[a-zA-Z0-9._:\-]{2,60}',model):
            raise RuntimeError('Ollama model adı geçersiz.')
        data=_post_json('http://127.0.0.1:11434/api/chat',
                {'model':model,'stream':False,'messages':[{'role':'system','content':prompt},
                 {'role':'user','content':question}]},timeout=45)
        return str(data.get('message',{}).get('content') or '(Ollama boş cevap verdi.)')
    raise RuntimeError('Sohbet için OPENAI_API_KEY ayarla ya da Ayarlar’dan Ollama sohbetini aç. İnternet araştırması OpenAI API gerektirir.')


def make_diagnostic(runtime, settings):
    """Nonsecret health info. Camera streams and tokens never included."""
    diag={'time':datetime.now().isoformat(timespec='seconds'),
          'ti_version':'2.0.0','python':sys.version.split()[0],
          'running':bool(runtime.active),'voice_ready':bool(runtime.assistant and runtime.assistant.speaker),
          'camera_preview_enabled':bool(settings.get('preview')),
          'object_detection_enabled':bool(settings.get('detection')),
          'yolo_ready':bool(runtime.video.yolo_ready),
          'tracking_active':bool(runtime.follow_controller.active),
          'motor_permission':bool(settings.get('motor')),
          'camera_frames':int(runtime.video.frame_count),
          'camera_fps':round(float(runtime.video.fps),2)}
    try:
        import psutil
        diag.update(cpu_percent=psutil.cpu_percent(interval=None),
                    memory_percent=round(psutil.virtual_memory().percent,1),
                    process_ram_mb=round(psutil.Process().memory_info().rss/1024**2,1))
    except ImportError:
        diag['metrics']='psutil kurulu değil'
    return diag


def diagnostic_text(diag):
    return '\n'.join(f'{key}: {value}' for key,value in diag.items())


def export_diagnostic(path,diag):
    target=Path(path)
    if target.suffix.lower()!='.md':raise ValueError('Rapor .md dosyası olmalı.')
    lines=['# Ti AI Tanı Raporu','', 'Bu rapor kamera kimliği, token ve görüntü içermez.','']
    lines.extend(f'- **{k}**: {str(v)}' for k,v in diag.items())
    target.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def export_chat(path, chat):
    target=Path(path)
    if target.suffix.lower()!='.md':raise ValueError('Sohbet kaydı .md dosyası olmalı.')
    rows=['# Ti AI Sohbet Geçmişi','', 'Yalnızca bu oturumdaki kullanıcı isteğiyle oluşturulan konuşmalar.','']
    for who,msg in chat[-100:]:
        rows.extend(['## '+('Kullanıcı' if who=='user' else 'Ti'),'',str(msg).replace('\x00','')[:6000],''])
    target.write_text('\n'.join(rows),encoding='utf-8')
