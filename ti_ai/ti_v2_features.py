"""Ti 2.0 opt-in integrations: auditable actions, no autonomous code execution.

Secrets are read from environment variables only, never persisted by settings.
External calls use bounded timeouts and are initiated by users or an enabled alert.
"""
from __future__ import annotations
from datetime import datetime
from contextlib import closing
import base64
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

from ti_lab import _post_json, _api_output, ask_ti

EXTENSIONS = {
    'spotify': ('Spotify', 'ti_spotify'),
    'windows': ('Windows Kısayolları', 'ti_commands'),
    'home_assistant': ('Home Assistant', 'ti_v2_features'),
    'telegram': ('Telegram Uyarıları', 'ti_v2_features'),
    'vision': ('Görsel Soru-Cevap', 'ti_v2_features'),
    'mobile': ('Güvenli Web Paneli', 'ti_v2_web'),
}
AGENTS = {
    'genel': 'Güvenilir, kısa, Türkçe bir yardımcı gibi cevap ver.',
    'arastirmaci': 'Kaynakları belirt, belirsizliği açıkla, doğrulanmayan bilgiyi ayırt et.',
    'gelistirici': 'Kod önerileri için test, geriye uyumluluk ve risk analizi sun. Değişikliği kendin uygulama.',
    'kamera': 'Yalnızca açıkça paylaşılan özet veya görüntü hakkında konuş; canlı kameraya eriştiğini iddia etme.',
}


def safe_url(url, *, allow_local=False):
    parts=urllib.parse.urlparse(url)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError('Bağlantıda kullanıcı adı, parola veya sorgu bulunamaz.')
    if parts.scheme=='https' and parts.hostname and parts.port in (None,443,8123):
        return url.rstrip('/')
    if allow_local and parts.scheme=='http' and parts.hostname in ('127.0.0.1','localhost') and parts.port in (None,8123):
        return url.rstrip('/')
    raise ValueError('HTTPS gereklidir (yerel 127.0.0.1 istisna).')


def home_assistant_toggle(entity_id, *, base_url=None, token=None):
    """Exactly light/switch toggles; no arbitrary HA services from model output."""
    if not re.fullmatch(r'(light|switch)\.[a-z0-9_]{1,80}', str(entity_id)):
        raise ValueError('Yalnızca light.* veya switch.* cihazlarına izin verilir.')
    key=(token or os.environ.get('TI_HOME_ASSISTANT_TOKEN','')).strip()
    if not key:raise RuntimeError('TI_HOME_ASSISTANT_TOKEN eksik.')
    root=safe_url(base_url or os.environ.get('TI_HOME_ASSISTANT_URL','http://127.0.0.1:8123'),allow_local=True)
    domain=entity_id.split('.')[0]
    result=_post_json(root+f'/api/services/{domain}/toggle',{'entity_id':entity_id},
                      headers={'Authorization':'Bearer '+key},timeout=12)
    return 'Home Assistant komutu gönderildi.' if isinstance(result,(list,dict)) else 'Beklenmeyen yanıt'


def telegram_alert(message, *, token=None, chat_id=None):
    key=(token or os.environ.get('TI_TELEGRAM_BOT_TOKEN','')).strip()
    user=(chat_id or os.environ.get('TI_TELEGRAM_CHAT_ID','')).strip()
    if not re.fullmatch(r'\d{7,12}:[A-Za-z0-9_-]{25,}',key) or not re.fullmatch(r'-?\d{4,18}',user):
        raise RuntimeError('Telegram bot tokeni / sohbet kimliği yapılandırılmadı.')
    data=_post_json('https://api.telegram.org/bot'+key+'/sendMessage',
                    {'chat_id':user,'text':str(message)[:250]},timeout=12)
    if data.get('ok') is not True:raise RuntimeError('Telegram bildirimi başarısız.')
    return True


def vision_question(jpeg: bytes, question: str, *, api_key=None):
    """User-triggered image upload only: no streaming or automatic cloud sharing."""
    key=(api_key or os.environ.get('OPENAI_API_KEY','')).strip()
    if not key:raise RuntimeError('OPENAI_API_KEY gerekli. Görüntü izinsiz gönderilmez.')
    if not isinstance(jpeg,bytes) or not jpeg.startswith(b'\xff\xd8') or len(jpeg)>900_000:
        raise ValueError('Küçük bir JPEG görüntüsü gerekli.')
    if not question.strip() or len(question)>1500:raise ValueError('1–1500 karakterlik soru gerekli.')
    model=os.environ.get('TI_OPENAI_MODEL','gpt-5.5')
    if not re.fullmatch(r'[a-zA-Z0-9._-]{2,55}',model):raise ValueError('Model adı geçersiz.')
    req={'model':model,'instructions':'Görüntü hakkında yalnızca gözlenebilir bilgileri Türkçe anlat. Yanılabileceğini belirt. Kişileri tanımlama.','input':[
        {'role':'user','content':[{'type':'input_text','text':question},
        {'type':'input_image','image_url':'data:image/jpeg;base64,'+base64.b64encode(jpeg).decode('ascii'),'detail':'low'}]}],
        'store':False,'max_output_tokens':550}
    result=_post_json('https://api.openai.com/v1/responses',req,
                      headers={'Authorization':'Bearer '+key},timeout=50)
    return _api_output(result)


class ConversationMemory:
    """User-controlled notes and short conversation turns, local-only by default."""
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, time TEXT, role TEXT, text TEXT)')
    def add(self,role,content):
        if role not in ('user','assistant'):raise ValueError('Geçersiz rol')
        content=str(content).strip()[:2000]
        if not content:raise ValueError('Boş içerik')
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('INSERT INTO messages (time,role,text) VALUES (?,?,?)',
                (datetime.now().isoformat(timespec='seconds'),role,content))
    def recent(self,limit=8):
        with closing(sqlite3.connect(self.path)) as con, con:
            rows=con.execute('SELECT role,text FROM messages ORDER BY id DESC LIMIT ?', (max(1,min(20,int(limit))),)).fetchall()
        return list(reversed(rows))
    def clear(self):
        with closing(sqlite3.connect(self.path)) as con, con:con.execute('DELETE FROM messages')


class VisualHistory:
    """Event metadata with optional snapshot paths kept under an approved capture folder."""
    def __init__(self,path,root):
        self.path=Path(path);self.root=Path(root).resolve()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('CREATE TABLE IF NOT EXISTS sights (id INTEGER PRIMARY KEY, time TEXT, kind TEXT, note TEXT, image TEXT)')
    def add(self,kind,note,image=''):
        relative=''
        if image:
            p=Path(image).resolve()
            if p.parent!=self.root or p.suffix.lower() not in ('.jpg','.png','.avi','.mp4'):
                raise ValueError('Görüntü yalnızca Ti_Kayitlar klasöründen olabilir.')
            relative=p.name
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('INSERT INTO sights (time,kind,note,image) VALUES (?,?,?,?)',
                        (datetime.now().isoformat(timespec='seconds'),str(kind)[:50],str(note)[:300],relative))
    def search(self,phrase='',limit=40):
        phrase=str(phrase)[:80]
        pattern='%'+phrase.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        with closing(sqlite3.connect(self.path)) as con, con:
            return con.execute("SELECT time,kind,note,image FROM sights WHERE kind LIKE ? ESCAPE '\\' OR note LIKE ? ESCAPE '\\' ORDER BY id DESC LIMIT ?",
                               (pattern,pattern,min(200,int(limit)))).fetchall()


def agent_chat(question,agent,*,api_key=None,local_model=None,memory=None,research=False):
    if agent not in AGENTS:raise ValueError('Tanımsız ajan')
    context='\n'.join(f'{role}: {text}' for role,text in (memory.recent(6) if memory else []))
    combined=f'Rol: {AGENTS[agent]}\n' + (f'Önceki konuşma (kullanıcı izinli):\n{context[:1300]}\n' if context else '') +f'Kullanıcı: {question}'
    answer=ask_ti(combined,api_key=api_key,local_model=local_model,research=research)
    if memory:
        memory.add('user',question);memory.add('assistant',answer[:2000])
    return answer


def developer_proposal(question,diagnostic,*,api_key=None,local_model=None,path):
    proposal=ask_ti(question,api_key=api_key,local_model=local_model,
                    improvement_context=str(diagnostic)[:1500])
    p=Path(path)
    if p.suffix!='.md':raise ValueError('Öneri .md formatında olmalı.')
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('# Ti Developer — inceleme bekleyen öneri\n\n'
        'Bu dosya kendi kendine kod değiştirmez, PR oluşturmaz. Önce geliştirici kontrolü gerekir.\n\n'
        +proposal[:12000]+'\n',encoding='utf-8')
    return p


def offline_tests(project_dir):
    """Fixed scripts only, no model supplied arbitrary shell commands."""
    root=Path(project_dir)
    command=[sys.executable,'-m','unittest','discover','-s',str(root),'-p','Ti_v2_Testleri.py']
    result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=50)
    return result.returncode,(result.stdout+'\n'+result.stderr)[-3000:]


def extension_list():
    return [(name,label,import_path) for name,(label,import_path) in EXTENSIONS.items()]
