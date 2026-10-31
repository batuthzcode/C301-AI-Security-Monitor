# Ti AI — Arındırılmış Proje Özeti ve Devam Notları

**Tarih:** 31 Ekim 2026
**Son geliştirilen paket:** Ti AI Cyber SOC v2.3 — ZTE H3600 cihaz envanteri
**Durum:** Windows üzerinde geliştirilen çok modüllü masaüstü asistanı; bazı bileşenler gerçek cihazda kullanıldı, pek çok yeni özellik ise çevrimdışı test veya entegrasyon aşamasında.

> [!IMPORTANT]
> Bu belge, kullanıcı tarafından sağlanan geliştirme notlarının kişisel ve
> hassas ayrıntılardan arındırılmış özetidir. Burada anılan v1.0–v2.3 paketlerinin
> kaynakları bu Git deposunda bulunmadığından özellikler ve test sayıları bu
> commit kapsamında bağımsız olarak doğrulanmamıştır. Belge kaynak kod yerine
> geçmez ve mevcut deponun çalışan özellik listesi olarak yorumlanmamalıdır.

## 1. Projenin amacı

Ti AI'yi Xiaomi C301 kameralı bir Türkçe sesli asistandan şu yetenekleri kapsayan, GitHub/LinkedIn'de sergilenebilecek bir projeye dönüştürüyoruz:

- Python / PySide6 ile masaüstü kontrol merkezi; açık/koyu tema.
- Kamera canlı görüntü, YOLO ile nesne ve kişi algılama, kontrollü PTZ takibi.
- Türkçe komutlar, seçili Windows otomasyonu, sohbet ve internette araştırma (gerekli API/yerel model ile).
- AR Studio: yüz maskeleri, el takibi, havaya çizim, elde Dünya ve diğer efektler.
- Cyber SOC: kişisel bilgisayarın bağlantıları, Wireshark/TShark analizi, ZTE modemden cihaz envanteri, güvenlik olayları ve savunma önerileri.

**Proje ilkeleri:** Performans korunmalı, bütün butonlar gerçek işlevli olmalı ve
her yeni ZIP'te güncel `DEVAM_NOTLARI.md` bulunmalı.

## 2. Yaptıklarımız — sürüm geçmişi

| Sürüm | Başlıca çalışmalar |
|---|---|
| v1.0–v1.1 | Xiaomi C301 video/ses bağlantısı ve ilk Ti Kontrol Merkezi; gecikme ve fazla yakın görüntü için akış/zoom düzeltmeleri. |
| v1.2–v1.3 | Buton anahtarlarının tıklama düzeltmeleri; YOLO hata bildirimi; algılamayı ayrı işlemde çalıştırarak arayüz donmalarını azaltma. |
| v1.3.1 | Eksik `ti_services.py` sorununa karşı birleşik dosya paketi, yedeklemeli kurulum, görünür açılış hataları. Kurulum başlatıcı adlarındaki karışıklık sonrasında `00_BASLAT.bat` düzeni. |
| v1.3.2 | “Takibi Başlat”ın sesli asistandan ayrılması; mevcut video/YOLO sonuçlarıyla çalışması. |
| v1.3.3 | Tek motor hareketinden sonra durma sorununa karşı kontrollü takip süresi ve hareket aralıkları; Ti Laboratuvarı, sohbet/araştırma, notlar, olay arama, performans raporu. |
| v2.0 | Tıklayarak hedef seçme, ID takibi, motor kalibrasyon verisi, görsel soru-cevap, sohbet hafızası, ajan rolleri, Windows kısayolları, Telegram/Home Assistant, mobil panel, geliştirici önerileri, EXE derleme ve geri alma altyapısı. Bazıları yalnızca taslak/entegrasyon düzeyinde. |
| v2.1 | AR Studio: yüz maskeleri, MediaPipe el/yüz takibi, havada çizim, Dünya ve diğer sanal objeler, fotoğraf/video kontrolleri. FPS/çözünürlük sınırlaması. |
| v2.1.1–v2.1.2 | AR model teşhisi ve onarımı. Unicode karakter içeren kullanıcı klasörlerinde MediaPipe modelini açamama sorunu için model baytlarını `model_asset_buffer` ile bellekte yükleme. |
| v2.2 | NASA Blue Marble dokulu Dünya ve daha iyi yüz hizalaması; Ağ Güvenliği paneli: yerel IP, açık bağlantılar, ARP, TShark adaptörleri, izinli kısa analiz, DNS/TLS alan adı gözlemleri ve şüpheli örüntü raporu. |
| **v2.3** | **ZTE H3600 Topoloji JSON'unu manuel içe aktarma**, cihaz adı/IP/MAC/bağlantı türü ayıklama, SQLite envanteri, yeni cihaz karşılaştırması ve ilgili Türkçe komutlar. |

## 3. Arındırılmış modem ve ağ bağlamı

- **Modem:** ZTE ZXHN H3600 V9.
- İnternet sağlayıcısı ve cihaz firmware ayrıntıları gizlilik amacıyla çıkarıldı.
- Yönetim paneline erişim mevcut.
- Topoloji ekranında bağlı cihaz adları görülüyor.
- Chrome geliştirici araçlarında `?_type=menuData&_tag=topo_...` biçiminde JSON yanıtları bulundu.
- Kullanıcı, yanıtta cihaz bilgileri ile ilgili alanların göründüğünü doğruladı.
- **Henüz bilinmeyen:** Bu JSON'a Ti'nin güvenli, desteklenen ve kalıcı bir salt-okunur yöntemle otomatik erişip erişemeyeceği. Port Mirroring menüsü de doğrulanmadı.

## 4. Ti Cyber SOC v2.3'te ne gerçekten eklendi?

**Kod olarak eklenen:**

1. `ti_cyber_inventory.py`: Topoloji JSON'undan cihaz alanlarını okuma.
2. `Ti_Veriler/ti_cyber_inventory.sqlite3`: cihazları yerel SQLite veritabanında saklama.
3. İlk içe aktarmayı başlangıç listesi sayıp sonraki aktarımlarda yeni cihaz kimliklerini karşılaştırma.
4. Ağ Güvenliği içinde **“ZTE H3600 • Cihaz Envanteri”** paneli: panodan JSON içe aktar, JSON dosyası aç, son envanteri göster.
5. “Ti, modemime kimler bağlı?” / “Ti, ağıma yeni cihaz var mı?” komutları. **Yanıt son içe aktarılmış veriye dayanır, canlı modem sorgusu değildir.**
6. Mevcut projeye yedeklemeli, tekrar uygulanabilir küçük kurulum yaması.

**Henüz eklenmemiş veya doğrulanmamış:**

- Otomatik ZTE oturumu ve canlı cihaz listesi yenileme.
- Bilinmeyen cihazı modem üzerinden engelleme; uzaktan modem ayarlarını değiştirme.
- Her cihazın eksiksiz ziyaret geçmişi; HTTPS/VPN/DoH nedeniyle zaten her durumda elde edilemez.
- Gerçek zamanlı tüm ev trafiğinin tam IDS kapsamı; uygun gateway/mirror kurulumu gerekir.
- Gerçek H3600 + hedef Windows sistemi üzerinde tüm v2.3 butonlarının ve sesli komutların uçtan uca başarı testi.

## 5. Yaşadığımız ve ele aldığımız hatalar

- `ti_services.py` eksik kurulum dosyası; birleşik paket ve sağlık kontrolü hazırlandı.
- `.py` dosyasının açılıp kapanması; görünür `.bat`/`.cmd` başlatma ve hata kaydı getirildi.
- YOLO açınca donma; algılama ayrı işleme alınıp kare kuyruğu kısıtlandı.
- Takip motorunun yalnızca bir kez dönmesi; katı ilk-motor-sonrası durdurma mantığı değiştirildi. Fiziksel PTZ cihaz doğrulaması yine gerekli.
- AR modellerinin bulunamaması / başlatılamaması; tanı ve onarım aracı eklendi.
- Unicode karakter içeren Windows kullanıcı yolunda `FileNotFoundError`; modelin bellekten yüklenmesi için v2.1.2 yaması yapıldı.
- AR maskeleri ve eldeki objeler yeterince gerçekçi bulunmadı; Dünya dokusu ve bazı hizalamalar geliştirildi. Tam fiziksel/photoreal 3D ve el-nesne örtüşmesi henüz tamamlanmadı.

## 6. Testlerin anlamı

- Kullanıcı tarafından sağlanan v2.3 geliştirme kayıtlarına göre **175 çevrimdışı otomatik test** (önceki 158 + 17 cihaz envanteri testi) geçti.
- Örnek klasörde kurulum, yedekleme, tekrar kurulum, Python sözdizimi ve AR yamasını koruma denetlendi.
- **Bu sayı gerçek Windows/C301/ZTE/Wireshark entegrasyonlarının tamamının çalıştığının kanıtı değildir ve bu depoda yeniden çalıştırılmamıştır.** Hedef Windows sisteminde ayrıca doğrulama gerekir.

## 7. Son kurulum paketi

**Paket:** `Ti_AI_Cyber_SOC_v2_3_ZTE_H3600_Cihaz_Envanteri.zip`.

Kurulum planı:

1. Ti'yi kapat.
2. ZIP içindeki 6 dosyayı mevcut C301 ana klasörüne (`.venv` bulunan yere) kopyala.
3. **`00_CYBER_BASLAT.bat`** dosyasını çalıştır.
4. `Ti_Baslat.cmd` ile aç → **Ağ Güvenliği → ZTE H3600 Cihaz Envanteri**.
5. Yalnız yetkili olunan yerel modem yönetim panelindeki Topoloji yanıtını
   Chrome'dan **Copy response** ile kopyala → Ti'de
   **Panodan Topoloji JSON İçe Aktar**.
6. İlk içe aktarmadan sonra son envanteri incele; ileride tekrar alınan JSON'la farkı kontrol et.

**Uyarı:** İçe aktarılan veriler anlık değil, alındıkları zamana ait bir görüntüdür. Özellikle MAC adresi rastgeleleştirmesi yeni cihaz alarmı yaratabilir.

## 8. Sıradaki öncelikler

1. **Gerçek PC testleri:** v2.3 paneli açılıyor mu, JSON kaç cihaz buluyor, SQLite kayıtları ve sesli komutlar doğru mu?
2. **Veri eşleme:** Gerçek H3600 Topoloji yanıtında cihaz listesi ve alanlar hangi iç içe yapıda? Bu doğrulama yetkili yerel sistemde yapılmalı; ham yanıt herkese açık paylaşılmamalı.
3. **Güvenli otomatik okuma:** Mümkünse ZTE'nin desteklediği salt-okunur yönetim yolu; oturum parolasını/tokenları koruyan yerel güvenli saklama. Modemin güvenlik mekanizmaları aşılmamalı.
4. **Cihaz güven listesi:** “Benim telefonum”, “bilinmeyen cihaz”, “beklenen IoT” etiketleri; yeni cihaz bildirimleri.
5. **SOC genişlemesi:** Windows Sysmon, DNS kayıtları, isteğe bağlı Wazuh/Suricata/Zeek entegrasyonları; kanıt/yanlış-pozitif takibi ve günlük rapor.
6. **Onaylı savunma:** Modem gerçekten destekliyorsa geçici engelleme, işlem günlüğü ve geri alma.
7. **Performans ve portföy:** Gerçek FPS/CPU/RAM ölçümü, video demo, testli GitHub README, LinkedIn sunumu.

## 9. Güvenlik ve gizlilik kuralları

- Modem şifresi, oturum çerezi, `Authorization`, token, kamera erişim bilgisi, tam HAR ve hassas JSON asla sohbette veya GitHub'da paylaşılmamalı.
- IP/MAC envanteri mümkün olduğunca **yerelde** tutulmalı; GitHub paketine SQLite veritabanı ve özel günlükler konulmamalı.
- Ağ yakalaması yalnızca izinli ağlarda ve kullanıcı onayıyla yapılmalı; ham paketleri gereksiz yere kaydetmemeli.
- Şüpheli bağlantı uyarısı kesin saldırı teşhisi sayılmamalı.
- Cihaz engelleme gibi ağ kesintisine yol açan eylemler açık kullanıcı onayı, kayıt ve mümkünse geri alma gerektirmeli.

## 10. Gelecekteki her ZIP için zorunlu devam bilgisi

Her yeni sürümün `DEVAM_NOTLARI.md` dosyası şu başlıkları taşısın: **Sürüm/tarih, amaç, eklenen/değişen dosyalar, test sayısı ve test ortamı, gerçek cihaz doğrulaması, bilinen hatalar, kurulum ve geri alma, gizlilik uyarıları, sıradaki adım.**

## 11. Bu Git deposuna ekleme notu

Bu arındırılmış belge yalnızca ileride kaynak paketleri elde edildiğinde yapılacak
inceleme için bağlam sağlar. v1.0–v2.3 kaynakları eklenmeden önce:

1. ZIP ve kaynak envanteri çıkarılmalı.
2. Kimlik bilgileri, özel ağ verisi, SQLite envanteri, HAR/PCAP ve günlükler
   dışarıda bırakılmalı.
3. Testler temiz ve izole bir ortamda yeniden çalıştırılmalı.
4. Yalnız doğrulanan özellikler README'nin güncel özellik listesine taşınmalı.

