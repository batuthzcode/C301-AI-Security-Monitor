"""Ti Cyber SOC v2.3: LOCAL-ONLY import of ZTE topology response.

No router login, guessed endpoints, packet capture, credential storage, or outbound requests.
Only whitelisted device metadata are extracted; raw JSON is never persisted.
"""
from __future__ import annotations
import hashlib
from contextlib import closing
import ipaddress
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

MAX_INPUT = 1_500_000
MAX_DEVICES = 300
MAX_DEPTH = 11

NAME_KEYS = ('HostName', 'DeviceName', 'DevName', 'ClientName', 'hostName', 'hostname', 'deviceName', 'Name', 'name')
IP_KEYS = ('IpAddr', 'ipAddr', 'IPAddress', 'ipAddress', 'IPv4Address', 'IPv4Addr', 'HostIP', 'IP', 'ip')
MAC_KEYS = ('MacAddr', 'macAddr', 'MACAddr', 'MacAddress', 'MACAddress', 'MAC', 'Mac', 'mac', 'macAddress', 'macaddr')
TYPE_KEYS = ('ConnectionType', 'ConnectType', 'InterfaceType', 'LinkType', 'Interface', 'ConnType', 'AccessType', 'Connection', 'DeviceType')
STATUS_KEYS = ('Online', 'IsOnline', 'online', 'Active', 'ConnectStatus', 'Status')

class InventoryError(ValueError):
    pass


def _string(obj, keys, maxlen=120):
    for k in keys:
        x = obj.get(k)
        if isinstance(x, (int, float, bool)):
            x = str(x)
        if isinstance(x, str) and x.strip():
            return x.strip().replace('\x00', '')[:maxlen]
    # Some firmware variants capitalize names unpredictably.
    lower = {str(k).lower(): v for k, v in obj.items()}
    for key in keys:
        x = lower.get(key.lower())
        if isinstance(x, (int, float, bool)):
            x = str(x)
        if isinstance(x, str) and x.strip():
            return x.strip().replace('\x00', '')[:maxlen]
    return ''


def _mac(value):
    raw = re.sub(r'[^0-9a-fA-F]', '', str(value))
    if len(raw) != 12 or raw in ('000000000000', 'ffffffffffff'):
        return ''
    return ':'.join(raw[i:i+2] for i in range(0, 12, 2)).upper()


def _ip(value):
    try:
        obj = ipaddress.ip_address(str(value).split('%')[0].strip())
        if obj.is_unspecified or obj.is_multicast or obj.is_loopback:
            return ''
        return str(obj)
    except ValueError:
        return ''


def _iter_dicts(obj, depth=0):
    if depth > MAX_DEPTH:
        return
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _iter_dicts(value, depth+1)
    elif isinstance(obj, list):
        for value in obj[:MAX_DEVICES*4]:
            yield from _iter_dicts(value, depth+1)
    elif isinstance(obj, str) and len(obj) <= MAX_INPUT and obj.lstrip().startswith(('{', '[')):
        try:
            nested = json.loads(obj)
        except (ValueError, RecursionError):
            return
        yield from _iter_dicts(nested, depth+1)


def parse_topology(raw: str | bytes):
    """Whitelisted local device records; does not retain tokens/session fields."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_INPUT: raise InventoryError('JSON boyutu sınırı aşıldı (1,5 MB).')
        try: raw = raw.decode('utf-8-sig')
        except UnicodeError as e: raise InventoryError('UTF-8 JSON bekleniyor.') from e
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > MAX_INPUT:
        raise InventoryError('JSON metni geçersiz veya çok büyük.')
    try: data = json.loads(raw)
    except (json.JSONDecodeError, RecursionError) as e:
        raise InventoryError('Geçerli bir JSON yanıtı içe aktar.') from e
    result = {}
    for item in _iter_dicts(data):
        # Mesh-controller status is not a connected-client record.
        inst = _string(item, ('instID', 'InstID', 'InstanceID'), 80).upper()
        if inst.startswith('MESH.CONTROLLER') and not _string(item, NAME_KEYS):
            continue
        name = _string(item, NAME_KEYS)
        address = _ip(_string(item, IP_KEYS, 100))
        mac = _mac(_string(item, MAC_KEYS, 50))
        if not mac and not (name and address):
            continue
        kind = _string(item, TYPE_KEYS, 60)
        state = _string(item, STATUS_KEYS, 20)
        if not name: name = 'Adı belirtilmemiş cihaz'
        # Prefer MAC identity; IP-only devices may change addresses and get a new identity.
        identity = mac or (name.lower()+'|'+address)
        key = hashlib.sha256(identity.encode('utf-8')).hexdigest()
        record = {'id':key, 'name':name, 'ip':address, 'mac':mac, 'kind':kind,
                  'state':state, 'identity_quality':'MAC' if mac else 'ad+IP'}
        if key not in result or len(record['name']) > len(result[key]['name']):
            result[key] = record
        if len(result) >= MAX_DEVICES: break
    return sorted(result.values(), key=lambda r: (r['name'].casefold(),r['ip']))


def _db(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=3)
    con.execute('''CREATE TABLE IF NOT EXISTS devices(
        id TEXT PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL, mac TEXT NOT NULL,
        kind TEXT NOT NULL, state TEXT NOT NULL, identity_quality TEXT NOT NULL,
        first_seen_utc TEXT NOT NULL, last_seen_utc TEXT NOT NULL, seen_count INTEGER NOT NULL,
        trusted INTEGER NOT NULL DEFAULT 0)''')
    con.execute('''CREATE TABLE IF NOT EXISTS snapshots(
        id INTEGER PRIMARY KEY AUTOINCREMENT, imported_utc TEXT NOT NULL,
        device_count INTEGER NOT NULL, new_count INTEGER NOT NULL)''')
    return con


def import_snapshot(raw, path, now=None):
    """Create baseline on first import, then flag newly discovered identities.

    No raw JSON, cookies, headers or authentication material are saved.
    No network call or device blocking takes place.
    """
    records = parse_topology(raw)
    if not records: raise InventoryError('Bu JSON içinde tanınabilir cihaz kaydı yok. Doğru Topoloji yanıtını seç.')
    stamp = now or datetime.now(timezone.utc).isoformat(timespec='microseconds')
    with closing(_db(path)) as con, con:
        baseline = con.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0] == 0
        known = {row[0] for row in con.execute('SELECT id FROM devices')}
        new = [rec for rec in records if rec['id'] not in known and not baseline]
        for rec in records:
            con.execute('''INSERT INTO devices
              (id,name,ip,mac,kind,state,identity_quality,first_seen_utc,last_seen_utc,seen_count)
              VALUES(?,?,?,?,?,?,?,?,?,1)
              ON CONFLICT(id) DO UPDATE SET name=excluded.name,ip=excluded.ip,
              mac=excluded.mac,kind=excluded.kind,state=excluded.state,
              last_seen_utc=excluded.last_seen_utc,seen_count=seen_count+1''',
              (rec['id'],rec['name'],rec['ip'],rec['mac'],rec['kind'],rec['state'],
               rec['identity_quality'],stamp,stamp))
        con.execute('INSERT INTO snapshots(imported_utc,device_count,new_count) VALUES(?,?,?)',
                    (stamp,len(records),len(new)))
    return {'count':len(records),'new_count':len(new),'new':new,'baseline':baseline,
            'source':'ZTE JSON elle içe aktarım','imported_utc':stamp, 'records':records}


def latest(path):
    """Read last imported snapshot; never imply live device status."""
    if not Path(path).is_file():
        return {'imported_utc':None, 'records':[], 'note':'Henüz JSON içe aktarılmadı.'}
    with closing(_db(path)) as con:
        snap = con.execute('SELECT imported_utc,device_count,new_count FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
        if not snap:
            return {'imported_utc':None, 'records':[], 'note':'Henüz JSON içe aktarılmadı.'}
        stamp,count,new_count = snap
        # A device seen during the last snapshot; not necessarily still connected now.
        rows = con.execute('''SELECT id,name,ip,mac,kind,state,identity_quality,trusted
                              FROM devices WHERE last_seen_utc=? ORDER BY name COLLATE NOCASE LIMIT ?''',
                           (stamp,MAX_DEVICES)).fetchall()
    return {'imported_utc':stamp, 'count':count, 'new_count':new_count,
            'records':[dict(zip(('id','name','ip','mac','kind','state','identity_quality','trusted'),r)) for r in rows],
            'note':'Son elle içe aktarılan Topoloji görüntüsü; CANLI modem sorgusu değildir.'}


def masked_mac(mac):
    return '••:••:••:'+mac[-8:] if mac else 'MAC bilinmiyor'


def describe(report):
    stamp = report.get('imported_utc')
    if not stamp: return 'Henüz Topoloji JSON verisi içe aktarılmadı.'
    records = report.get('records',[])
    lines = ['ZTE H3600 CİHAZ ENVANTERİ',
             'Kaynak: son manuel JSON içe aktarımı (canlı bağlantı değil).',
             f'İçe aktarma: {stamp}',f'Bu görüntüde görülen cihaz: {len(records)}',
             f"Yeni kimlik: {report.get('new_count',0)}", '']
    for i, rec in enumerate(records[:MAX_DEVICES],1):
        lines.append(f"{i:02}. {rec['name']} | {rec['ip'] or '?'} | {masked_mac(rec['mac'])} | {rec['kind'] or 'Bağlantı türü belirsiz'}")
    lines += ['', 'Yeni cihaz tek başına saldırı kanıtı değildir. MAC rastgeleleştirme yeni kimlik üretebilir.',
              'Cihaz görünmemesi bağlantısının kesildiğini kanıtlamaz.']
    return '\n'.join(lines)
