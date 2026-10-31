"""Windows/Spotify/browser commands. No arbitrary shell commands are executed.
Dangerous OS actions only issue a UI confirmation event.
"""
from __future__ import annotations
import ctypes
from datetime import datetime
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import threading
import urllib.parse
import urllib.request
import webbrowser

from ti_v1_core import normalize

# Windows media virtual keys; no third-party dependencies required.
MEDIA_CODES = {"play": 0xB3, "stop": 0xB2, "next": 0xB0, "previous": 0xB1,
               "mute": 0xAD, "up": 0xAF, "down": 0xAE}


def media_key(key: str) -> bool:
    if os.name != "nt" or key not in MEDIA_CODES:
        return False
    keycode = MEDIA_CODES[key]
    ctypes.windll.user32.keybd_event(keycode, 0, 0, 0)
    ctypes.windll.user32.keybd_event(keycode, 0, 2, 0)
    return True


def open_target(name: str) -> str:
    """Whitelisted app and browser open operations."""
    apps = {
        "notepad": ["notepad.exe"], "calculator": ["calc.exe"],
        "explorer": ["explorer.exe"], "taskmgr": ["taskmgr.exe"],
        "paint": ["mspaint.exe"], "terminal": ["powershell.exe"],
        "cmd": ["cmd.exe"],
    }
    websites = {
        "youtube": "https://www.youtube.com/", "google": "https://www.google.com/",
        "gmail": "https://mail.google.com/", "github": "https://github.com/",
        "chatgpt": "https://chatgpt.com/", "maps": "https://www.google.com/maps",
    }
    try:
        if name in websites:
            webbrowser.open(websites[name]); return f"{name.title()} tarayıcıda açıldı."
        if name == "spotify":
            try:
                if os.name == "nt":
                    os.startfile("spotify:")
                else:
                    webbrowser.open("https://open.spotify.com/")
            except OSError:
                webbrowser.open("https://open.spotify.com/")
            return "Spotify açılıyor."
        if name == "chrome":
            paths=[Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))/"Google/Chrome/Application/chrome.exe",
                   Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))/"Google/Chrome/Application/chrome.exe",
                   Path(os.environ.get("LOCALAPPDATA", ""))/"Google/Chrome/Application/chrome.exe"]
            executable=next((str(p) for p in paths if p.is_file()),shutil.which('chrome'))
            if executable:
                subprocess.Popen([executable],stdin=subprocess.DEVNULL)
                return "Google Chrome açılıyor."
            webbrowser.open("https://www.google.com/")
            return "Chrome bulunamadı. Varsayılan tarayıcıda Google açıldı."
        if name == "edge":
            try:
                subprocess.Popen(["msedge.exe"],stdin=subprocess.DEVNULL)
                return "Microsoft Edge açılıyor."
            except OSError:
                webbrowser.open("https://www.bing.com/")
                return "Edge bulunamadı. Varsayılan tarayıcı açıldı."
        if name == "browser":
            webbrowser.open("https://www.google.com/"); return "Tarayıcı açılıyor."
        if name in apps:
            subprocess.Popen(apps[name], stdin=subprocess.DEVNULL)
            return f"{name.title()} açılıyor."
        if name == "desktop_screenshot":
            from PIL import ImageGrab
            path=Path(__file__).resolve().parent/"Ti_Kayitlar"
            path.mkdir(exist_ok=True)
            target=path/("Ti_Masaustu_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".png")
            ImageGrab.grab().save(target)
            return "Ekran görüntüsü kaydedildi: "+target.name
        if name == "settings" and os.name == "nt":
            os.startfile("ms-settings:"); return "Windows ayarları açılıyor."
        if name == "downloads_folder":
            target=Path.home()/"Downloads"
            if not target.is_dir():return "İndirilenler klasörü bulunamadı."
            if os.name=="nt":os.startfile(str(target))
            return "İndirilenler klasörü açıldı."
        if name == "camera_folder":
            path = Path(__file__).resolve().parent / "Ti_Kayitlar"
            path.mkdir(exist_ok=True)
            if os.name == "nt":
                os.startfile(path)
            return "Ti kayıt klasörü açıldı."
        return "Bu uygulamayı açmak için henüz güvenli bir kısayol tanımlanmadı."
    except (OSError, ValueError, ImportError) as exc:
        return f"Uygulama açılamadı: {str(exc)[:100]}"


def specs() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.15)
        mem = psutil.virtual_memory()
        return f"İşlemci kullanımı yüzde {cpu:.0f}, RAM kullanımı yüzde {mem.percent:.0f}."
    except ImportError:
        return f"Bilgisayar {platform.system()} kullanıyor. Detaylar için psutil yüklenmeli."


def battery() -> str:
    try:
        import psutil
        val = psutil.sensors_battery()
        return f"Pil yüzde {val.percent:.0f}." if val else "Bu bilgisayarda pil bilgisi bulunamadı."
    except (ImportError, OSError):
        return "Pil bilgisine ulaşılamadı."


class CommandRouter:
    def __init__(self, settings, post, spotify=None):
        self.settings = settings    # mutable dict, not an authentication token
        self.post = post            # queue UI events, never mutate Qt UI directly
        self._last_llm = []
        self.spotify = spotify

    def _act(self, name: str, value=None) -> str:
        self.post("action", (name, value))
        return {
            "theme_dark": "Koyu tema açılıyor.", "theme_light": "Açık tema açılıyor.",
            "preview_on": "Kamera görüntüsü açılıyor.", "preview_off": "Kamera görüntüsü kapanıyor.",
            "detect_on": "Nesne algılama açılıyor.", "detect_off": "Nesne algılama kapanıyor.",
            "person_only": "Sadece kişi algılama açılıyor.",
            "detect_all": "Tüm nesne sınıfları açılıyor.", "snapshot": "Kamera fotoğrafı çekiliyor.",
            "record_on": "Kamera kaydı başlatılıyor.", "record_off": "Kamera kaydı durduruluyor.",
            "profile_home": "Ev profili açılıyor.", "profile_night": "Gece profili açılıyor.",
            "profile_quiet": "Sessiz profil açılıyor.",
        }.get(name, "Komut işleme alındı.")

    def run(self, command: str) -> str | None:
        c = normalize(command)
        c = re.sub(r"^spotify ac ve\s+", "spotify ", c)
        if not c:
            return None
        if any(q in c for q in ('modemime kimler bagli','agima kimler bagli','agima kim baglandi',
                                   'yeni cihaz var mi','tanimmadigim cihaz','agimdaki cihazlari goster',
                                   'modeme bagli cihazlari goster')):
            import ti_cyber_inventory as cyberinv
            from ti_services import DATA
            state=cyberinv.latest(DATA/'ti_cyber_inventory.sqlite3')
            if not state.get('imported_utc'):
                return 'Önce Ağ Güvenliği sayfasında ZTE Topoloji JSON içe aktarımı yapmalısın. Modeme canlı bağlı değilim.'
            self.post('action',('cyber_open',None))
            people=', '.join(r['name'] for r in state['records'][:5])
            return (f"Son içe aktarılan {state['imported_utc']} tarihli listede "
                    f"{len(state['records'])} cihaz var: {people}. "
                    'Bunlar canlı modem sorgusu değil, son kayıt bilgileri.')
        # Custom personal replies, exact match to avoid accidental trigger.
        for phrase, answer in self.settings.get("learned", {}).items():
            if normalize(phrase) == c:
                return str(answer)[:400]
        if any(q in c for q in ("bilgisayari kapat", "pc kapat", "bilgisayari yeniden baslat", "pc yeniden baslat", "oturumu kilitle", "ekrani kilitle")):
            action = "shutdown" if "kapat" in c else "restart" if "baslat" in c else "lock"
            self.post("confirm", action)
            return "Bu işlem için kontrol merkezindeki onay penceresini kullan."
        if any(q in c for q in ("koyu tema", "gece temas", "karanlik tema", "siyah tema")):
            return self._act("theme_dark")
        if any(q in c for q in ("acik tema", "beyaz tema", "gunduz tema")):
            return self._act("theme_light")
        for q, action in (
            ("nesne algilamayi ac", "detect_on"), ("nesne algilamayi kapat", "detect_off"),
            ("sadece kisileri", "person_only"), ("sadece kisi", "person_only"),
            ("tum nesneleri", "detect_all"), ("kamerayi ac", "preview_on"),
            ("goruntuyu ac", "preview_on"), ("goruntuyu kapat", "preview_off"),
            ("fotograf cek", "snapshot"), ("kameradan fotograf", "snapshot"),
            ("kaydi baslat", "record_on"), ("video kaydi baslat", "record_on"),
            ("kaydi durdur", "record_off"), ("video kaydi durdur", "record_off"),
            ("ev modunu ac", "profile_home"), ("gece modunu ac", "profile_night"),
            ("sessiz moda gec", "profile_quiet"),
        ):
            if q in c:
                return self._act(action)
        if any(q in c for q in ("cpu", "ram", "islemci", "bellek kullanimi", "bilgisayar durumu")):
            return specs()
        if "pil" in c or "sarj" in c:
            return battery()
        if any(q in c for q in ("disk alani", "disk dolu", "diskte kac", "depolama durumu")):
            try:
                import psutil
                disk=psutil.disk_usage(str(Path.home().anchor))
                return f"Sistem diskinde yaklaşık {disk.free / 1024**3:.0f} gigabayt boş alan var."
            except (ImportError, OSError):return "Disk bilgisine erişemedim."
        if "bilgisayarin adi" in c or "pc adi" in c:
            return "Bilgisayar adı: "+platform.node()
        if "ip adresim" in c or "yerel ip" in c:
            try:return "Yerel IP adresi: "+socket.gethostbyname(socket.gethostname())
            except OSError:return "Yerel IP adresini okuyamadım."
        if "ekran goruntusu al" in c or "masaustunun fotografini cek" in c:
            return open_target("desktop_screenshot")
        if c in ("gunaydin","iyi aksamlar", "iyi gunler", "merhaba", "selam"):
            return "Merhaba! Bugün sana nasıl yardımcı olabilirim?"
        if "burada misin" in c or "beni duyuyor musun" in c:
            return "Buradayım, seni dinliyorum."
        if "bir saka yap" in c or "saka anlat" in c:
            return "Bilgisayar neden üşümüş? Çünkü Windows açık kalmış."
        if "neler yapabiliyorsun" in c:
            return "Kamerayı yönetebilir, nesne algılayabilir, sana cevap verebilir, uygulama açabilir ve Spotify'ı kontrol etmeyi deneyebilirim."
        if "internet" in c and any(x in c for x in ("var mi", "bagli", "calisiyor")):
            try:
                with urllib.request.urlopen("https://www.google.com/generate_204", timeout=4) as response:
                    return "İnternet bağlantısı var." if response.status == 204 else "Bağlantı yanıt verdi."
            except OSError:
                return "İnternet bağlantısını doğrulayamadım."
        # Spotify search: opens result; direct playback needs Spotify OAuth & Premium.
        patterns = (r"(?:spotify(?:dan|da)?\s+)?(.+?)\s+(?:sarkisini|muzigini|parcasini)\s+ac$",
                    r"(?:spotify(?:dan|da)?\s+)?(.+?)\s+(?:sarkisini|muzigini|parcasini)\s+cal$",
                    r"spotify(?:dan|da)?\s+(.+?)\s+(?:ac|cal)$")
        if not c.startswith("spotify ac"):
            for p in patterns:
                m = re.search(p, c)
                if m and len(m.group(1)) > 1:
                    song = m.group(1).strip()
                    if self.spotify and self.spotify.connected:
                        success, result = self.spotify.play_song(song)
                        return result
                    webbrowser.open("https://open.spotify.com/search/" + urllib.parse.quote(song))
                    return f"Spotify'da {song} aramasını açtım. Oynatmak için şarkıyı seçmelisin."
        if "spotify" in c and any(x in c for x in ("ac", "baslat")):
            return open_target("spotify")
        if any(q in c for q in ("muzigi durdur", "muzigi baslat", "muzigi devam", "muzige devam", "duraklat", "oynat")):
            return "Medya oynat/duraklat komutu gönderildi." if media_key("play") else "Bu medya komutu Windows gerektiriyor."
        if "sonraki sarki" in c or "sonraki parca" in c:
            return "Sonraki şarkı komutu gönderildi." if media_key("next") else "Windows gerekli."
        if "onceki sarki" in c or "onceki parca" in c:
            return "Önceki şarkı komutu gönderildi." if media_key("previous") else "Windows gerekli."
        if "sesi ac" in c or "sesi yukselt" in c or "sesi arttir" in c:
            if media_key("up") and media_key("up") and media_key("up"):
                return "Bilgisayar sesini yükselttim."
            return "Windows ses denetimine erişemedim."
        if "sesi kis" in c or "sesi azalt" in c:
            if media_key("down") and media_key("down") and media_key("down"):
                return "Bilgisayar sesini kıstım."
            return "Windows ses denetimine erişemedim."
        if "sessize al" in c or "sesi kapat" in c:
            return "Bilgisayar sesini değiştirdim." if media_key("mute") else "Windows gerekli."
        apps = (
            (("spotify",), "spotify"),
            (("youtube",), "youtube"), (("github",), "github"),
            (("gmail",), "gmail"), (("chatgpt",), "chatgpt"),
            (("haritalari", "harita"), "maps"),
            (("chrome",), "chrome"),
            (("edge",), "edge"),
            (("tarayici", "interneti"), "browser"),
            (("not defteri", "notepad"), "notepad"),
            (("hesap makinesi",), "calculator"),
            (("dosya gezgini", "klasoru ac"), "explorer"),
            (("gorev yoneticisi",), "taskmgr"),
            (("paint",), "paint"),
            (("powershell", "terminal"), "terminal"),
            (("windows ayarlari",), "settings"),
            (("kayit klasoru", "kayitlar klasoru"), "camera_folder"),
        )
        if any(x in c for x in (" ac", " baslat", " goster")):
            for names, target in apps:
                if any(x in c for x in names):
                    return open_target(target)
        for prefix, url in (("google da ara ", "https://www.google.com/search?q="),
                            ("internette ara ", "https://www.google.com/search?q="),
                            ("youtube da ara ", "https://www.youtube.com/results?search_query=")):
            if c.startswith(prefix):
                webbrowser.open(url + urllib.parse.quote(c[len(prefix):])); return "Arama sonuçlarını açtım."
        if any(x in c for x in ("hava durumu", "hava nasil")):
            city = self.settings.get("city", "")
            if not city:
                return "Hava durumu için Ayarlar bölümünden bir şehir seç."
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(city+" hava durumu"))
            return f"{city} için hava durumunu tarayıcıda açtım."
        if self.settings.get("llm_enabled", False):
            return self.ask_local_llm(command)
        return None  # Let existing time/date/identity/camera commands handle it.

    def ask_local_llm(self, command: str) -> str:
        """Offline capable local Ollama; explicit opt in and local address only."""
        import json
        model = self.settings.get("llm_model", "llama3.2:3b")
        messages = [{"role": "system", "content": "Sen Ti adlı Türkçe kişisel asistan yazılımısın. İnsan olduğunu iddia etme. Akıcı ve sıcak şekilde konuş. Gereksiz uzun konuşma. Kullanıcı için işlem yaptığını asla uydurma. Konuşma tarzın: "+str(self.settings.get("voice_personality", "Samimi"))+". Bilmediğini söyle."}]
        messages += self._last_llm[-8:]
        messages.append({"role": "user", "content": command})
        req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
            data=json.dumps({"model": model, "messages": messages, "stream": False,
                             "options": {"num_predict": 170}}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=55) as resp:
                answer = str(json.load(resp)["message"]["content"]).strip()[:750]
            self._last_llm += [{"role":"user","content":command}, {"role":"assistant","content":answer}]
            return answer or "Bunu nasıl yanıtlayacağımı bilemedim."
        except (OSError, KeyError, ValueError) as ex:
            return "Yerel sohbet modeline bağlanamadım. Ollama ve seçilen modelin çalıştığını kontrol et."
