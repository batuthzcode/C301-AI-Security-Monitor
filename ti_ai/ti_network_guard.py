"""Ti Ağ Güvenliği: consent-based, bounded local network diagnostics.

Does not scan remote machines, sniff payloads, or upload traffic.
TShark use is explicitly initiated by a local user, non-promiscuous,
12 seconds / 800 field rows, minimal metadata only. No periodic background capture.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
from typing import Optional
import urllib.request

FIELDS = ('frame.time_epoch','ip.src','ip.dst','ipv6.src','ipv6.dst',
          'tcp.srcport','tcp.dstport','udp.srcport','udp.dstport','dns.qry.name',
          'tls.handshake.extensions_server_name','http.host','tcp.flags.syn','tcp.flags.ack')
PRIVATE_PORTS = {22,23,25,53,80,110,135,139,143,443,445,465,587,993,995,1433,3306,3389,5432,5900,6379,8080,8443}

class GuardError(RuntimeError):
    pass


def tshark_path():
    found=shutil.which('tshark')
    if found:return found
    for base in (os.environ.get('ProgramFiles',''),os.environ.get('ProgramFiles(x86)','')):
        if base and (Path(base)/'Wireshark'/'tshark.exe').is_file():
            return str(Path(base)/'Wireshark'/'tshark.exe')
    return None


def _cmd(argv,timeout=8):
    kw={'capture_output':True,'text':True,'encoding':'utf-8','errors':'replace',
        'timeout':timeout, 'stdin':subprocess.DEVNULL}
    if os.name=='nt':kw['creationflags']=getattr(subprocess,'CREATE_NO_WINDOW',0)
    try:return subprocess.run(argv,**kw)
    except (OSError,subprocess.TimeoutExpired) as exc:raise GuardError(str(exc)) from exc


def interfaces(binary=None):
    binary=binary or tshark_path()
    if not binary:raise GuardError('Wireshark TShark bulunamadı. Wireshark kurulumu ile TShark ve Npcap gereklidir.')
    p=_cmd([binary,'-D'])
    if p.returncode:raise GuardError(('Arayüz listesi okunamadı: '+p.stderr)[-450:])
    return [dict(id=m.group(1), name=m.group(2).strip()) for line in p.stdout.splitlines()
            if (m:=re.match(r'^\s*(\d+)\.\s+(.+)',line))]


def ip_inventory():
    result={'hostname':socket.gethostname(),'interfaces':[],'local_ips':[],
            'public_ip':'İsteğe bağlı; internete sorgu gönderilmedi','note':'Yalnızca bu bilgisayar'}
    try:
        import psutil
        for name,addrs in psutil.net_if_addrs().items():
            ips=[]
            for a in addrs:
                if a.family in (socket.AF_INET,socket.AF_INET6):
                    value=str(a.address).split('%')[0]
                    if value not in ('127.0.0.1','::1'):
                        ips.append(value)
            if ips:
                result['interfaces'].append({'name':name,'ips':ips})
                result['local_ips'].extend(ips)
    except ImportError:
        try:
            result['local_ips']=[i for i in socket.gethostbyname_ex(socket.gethostname())[2] if not i.startswith('127.')]
        except OSError:pass
    result['local_ips']=list(dict.fromkeys(result['local_ips']))
    return result


def public_ip_lookup():
    """Only when user clicks a button. Informs a third-party of public address."""
    request=urllib.request.Request('https://api.ipify.org',headers={'User-Agent':'Ti-AI/2.2'})
    try:
        with urllib.request.urlopen(request,timeout=6) as r:
            payload=r.read(64).decode('ascii','strict').strip()
        return str(ipaddress.ip_address(payload))
    except (OSError,ValueError,UnicodeError) as ex:raise GuardError('Dış IP sorgusu başarısız: '+str(ex)[:160]) from ex


def local_connections(limit=80):
    """Only OS-owned socket metadata, not other users' browser histories."""
    try:import psutil
    except ImportError:raise GuardError('Bağlantı listesi için psutil eksik. .venv üzerinden pip install psutil')
    rows=[]
    try:connections=psutil.net_connections(kind='inet')
    except (OSError,PermissionError) as exc:raise GuardError('Bağlantılar okunamadı: '+str(exc)) from exc
    for conn in connections:
        if not conn.raddr:continue
        lip=f'{conn.laddr.ip}:{conn.laddr.port}' if conn.laddr else ''
        rip=f'{conn.raddr.ip}:{conn.raddr.port}'
        name='Bilinmiyor'
        if conn.pid:
            try:name=psutil.Process(conn.pid).name()
            except (psutil.AccessDenied,psutil.NoSuchProcess):pass
        rows.append({'uygulama':name,'pid':conn.pid,'yerel':lip,'uzak':rip,'durum':conn.status})
    rows.sort(key=lambda x:(x['uygulama'].lower(),x['uzak']))
    return rows[:max(1,min(int(limit),200))]


def arp_neighbors():
    """Recent ARP cache sightings; NOT a complete list of Wi-Fi clients."""
    if os.name!='nt':return []
    proc=_cmd(['arp','-a'])
    matches=[]
    for line in proc.stdout.splitlines():
        m=re.match(r'\s*(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9a-fA-F-]{17})\s+',line)
        if m:
            try:
                ip=ipaddress.ip_address(m.group(1))
                if ip.is_private and not ip.is_multicast:matches.append({'ip':str(ip),'mac':m.group(2)})
            except ValueError:pass
    return matches[:150]


def _valid_ip(value):
    try:return str(ipaddress.ip_address(value))
    except ValueError:return ''


def _port(s):
    try:return int(s)
    except (ValueError,TypeError):return 0


def parse_tshark_tsv(text, max_rows=800):
    """-E separator=/t -E header=y; field data can be blank/multivalued."""
    packets=[]
    for line in text.splitlines():
        if not line or line.startswith('frame.time_epoch\t'):continue
        cells=line.split('\t')
        if len(cells)<len(FIELDS):continue
        cells=cells[:len(FIELDS)]
        packet=dict(zip(FIELDS,cells))
        src=_valid_ip(packet['ip.src'] or packet['ipv6.src'])
        dst=_valid_ip(packet['ip.dst'] or packet['ipv6.dst'])
        if not src or not dst:continue
        try:when=float(packet['frame.time_epoch'])
        except (ValueError,OverflowError):continue
        if not (0<when<4_000_000_000):continue
        domain=(packet['tls.handshake.extensions_server_name'] or packet['dns.qry.name'] or packet['http.host']).strip().lower()
        # Only a hostname-like identifier; never capture URLs, query paths, payloads.
        domain=domain.split(',')[0]
        if len(domain)>253 or not re.fullmatch(r'[a-z0-9\-._]{1,253}',domain):domain=''
        packets.append({'time':when,'src':src,'dst':dst,
            'sport':_port(packet['tcp.srcport'] or packet['udp.srcport']),
            'dport':_port(packet['tcp.dstport'] or packet['udp.dstport']),
            'domain':domain,
            'syn':packet['tcp.flags.syn'].strip() in ('1','True','0x0001'),
            'ack':packet['tcp.flags.ack'].strip() in ('1','True','0x0010')})
        if len(packets)>=max_rows:break
    return packets


def classify(packets, local_ips=()):
    """Conservative heuristic indicators, never an attack verdict."""
    local=set(local_ips)
    inbound_ports=defaultdict(set); inbound_counts=Counter(); out_domains=defaultdict(set)
    contacts=Counter();domain_counts=Counter()
    for p in packets:
        src,dst=p['src'],p['dst']
        contacts[(src,dst)]+=1
        if p['domain']:domain_counts[p['domain']]+=1
        if dst in local and src not in local and p['syn'] and not p['ack'] and p['dport']:
            inbound_ports[(src,dst)].add(p['dport']);inbound_counts[(src,dst)]+=1
        if src in local and p['domain']:
            out_domains[src].add(p['domain'])
    alerts=[]
    for (src,dst),ports in inbound_ports.items():
        # Hitting 12 distinct ports with SYNs is suspicious, but not conclusive.
        if len(ports)>=12:
            alerts.append({'seviye':'İNCELE','tur':'Olası port taraması',
                'aciklama':f'{src} → {dst}: {len(ports)} farklı TCP hedef portu (SYN); yanlış pozitif olabilir.'})
    for src,domains in out_domains.items():
        if len(domains)>=40:
            alerts.append({'seviye':'İNCELE','tur':'Yoğun alan adı isteği',
                'aciklama':f'{src}: gözlenen {len(domains)} farklı alan adı; normal uygulamalar da oluşturabilir.'})
    return {'packet_count':len(packets),'observed_domains':domain_counts.most_common(40),
            'ip_pairs':[{'src':a,'dst':b,'packets':n} for (a,b),n in contacts.most_common(30)],
            'alerts':alerts,'conclusion':('İncelenmesi gereken belirtiler görüldü; saldırı doğrulanmadı.' if alerts else
                'Bu kısa örneklemde tanımlı şüphe göstergesi yok. Bu, saldırı olmadığı anlamına gelmez.'),
            'limits':'Yalnızca seçili bilgisayar arayüzü ve bu kısa sürede görülen trafik. DNS/SNI alan adları ziyaret edilen kesin sayfalar değildir. HTTPS/DoH/ECH/VPN içerik ve site görünürlüğünü sınırlar.'}


def capture(interface_id, seconds=12, binary=None, local_ips=()):
    """Never called until explicit button, selects only TShark's listed adapter."""
    binary=binary or tshark_path()
    if not binary:raise GuardError('TShark bulunamadı; Wireshark kurulmalı.')
    allowed={a['id'] for a in interfaces(binary)}
    if str(interface_id) not in allowed:raise GuardError('Geçersiz ağ adaptörü seçildi.')
    sec=max(5,min(25,int(seconds)))
    cmd=[binary,'-i',str(interface_id),'-p','-n','-a',f'duration:{sec}','-c','800',
         '-f','ip or ip6','-T','fields','-E','header=y','-E','separator=/t',
         '-E','occurrence=f']
    for field in FIELDS:cmd.extend(['-e',field])
    p=_cmd(cmd,timeout=sec+12)
    if p.returncode and not p.stdout.strip():
        raise GuardError('TShark yakalama başarısız: '+(p.stderr or 'Npcap izni/arayüz seçimini kontrol edin.')[-400:])
    packets=parse_tshark_tsv(p.stdout)
    report=classify(packets,local_ips)
    report['capture']={'interface_id':str(interface_id),'seconds':sec,'sampled_at_utc':datetime.now(timezone.utc).isoformat(),
        'packet_limit':800,'raw_packets_saved':False}
    report['diagnostic_warning']=p.stderr[-240:] if p.returncode else ''
    return report


def export_json(path,report):
    target=Path(path)
    if target.suffix.lower()!='.json':raise ValueError('Yalnızca JSON raporu')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return target
