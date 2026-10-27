# Baştan bugüne geliştirme geçmişi

Bu belge; yerel sürüm ZIP'leri, kaynak dosyalarının zaman damgaları, mevcut
geliştirme günlüğü ve paylaşılan ChatGPT konuşması birlikte incelenerek hazırlandı.
Git deposu daha önce oluşturulmadığı için ilk sürümler arşivlerden yeniden commit
edildi. Kod sırası gerçektir; commit oluşturulma zamanları özgün çalışma
zamanlarını temsil etmez.

## 1. İlk hedef ve kapsam

Amaç, Xiaomi C301'i firmware'i değiştirmeden Windows üzerinde çalışan yerel bir
güvenlik/yardımcı kamera sistemine dönüştürmekti. Kamera görüntüsünü go2rtc ile
yerel RTSP akışına çevirmek, bilgisayarda nesne algılamak ve olayları yerel tutmak
temel tasarım kararı oldu.

İlk günden itibaren sınırlar:

- Yüz tanıma veya kişi kimliği yok.
- “Radar” adı yalnızca görüntü düzlemindeki 2B konum gösterimini ifade ediyor.
- Gerçek Xiaomi bağlantısı, token ve hesap bilgileri Git dışında kalıyor.
- C301 firmware'i değiştirilmiyor.

## 2. v0.1.0 — temel bilgisayarlı görü prototipi

İlk arşivde şu yapı kuruldu:

1. Tkinter tabanlı Windows masaüstü arayüzü.
2. RTSP, USB kamera veya video dosyası girişi.
3. Ultralytics YOLO11n ile nesne algılama.
4. Algılama kutuları ve görüntü düzleminde 2B konum görünümü.
5. Sınıf kaybolup yeniden göründüğünde olay üreten `EventGate`.
6. Olay JPEG'leri ve JSONL kayıtlarını yalnız yerelde tutan `EventRecorder`.
7. Kamera olmadan denenebilen “SIMULATION” işaretli sentetik demo.
8. Gerçek go2rtc yapılandırmasını dışarıda bırakan güvenli örnek YAML.

Tam kaynak görüntüsü `v0.1.0` etiketindedir.

## 3. C301 bağlantı ve codec teşhisleri

Kamera go2rtc'nin Xiaomi aygıt yükleyicisinde görüldü ve kullanıcı canlı görüntüyü
aldı. Sonraki sorunlar Python kodundan önce taşıma/codec katmanında ortaya çıktı:

- `cs2: pop buffer is full` uyarıları.
- HEVC eksik referans kare ve QP uyarıları.
- go2rtc tarayıcı görüntüsü doğruyken OpenCV'de yeşil görüntü.
- H.264 alt akışının YAML'da yanlış ayrılması ve `unsupported scheme` hatası.
- Doğru alıntılama ve ayrı anahtarlardan sonra `c301` ile `c301_h264` görüntüsü.
- Yerel RTSP istemci kapanmalarının Xiaomi CS2 hatasından ayrı tutulması.

Bu dönem ağırlıklı olarak tanı ve geri dönüş planları üretti; özel Xiaomi URL'si
hiçbir yayımlanabilir dosyaya alınmadı.

## 4. v0.1.1 — en-son-kare düşük gecikme mimarisi

İlk worker aynı döngüde hem `VideoCapture.read()` hem YOLO çalıştırıyordu. Ağır
çıkarım sırasında RTSP kareleri birikiyor, GUI eski kareleri sırayla çiziyordu.
v0.1.1'de:

1. Kamera sürekli ayrı thread'de okunmaya başladı.
2. Üzerine yazılan `LatestFrameBuffer` kullanıldı.
3. YOLO en son sabit kareyi bağımsız analiz etti.
4. Tkinter her turda yalnız en güncel görüntüyü çizdi.
5. `--imgsz` ve `--inference-interval` ayarları eklendi.

Bu yaklaşım uygulama içi kuyruğu azaltır; kamera, go2rtc veya FFmpeg tamponlarını
tek başına ortadan kaldırmaz. Kaynak görüntü `v0.1.1` etiketindedir.

## 5. v0.1.2 — gecikmeyi katmanlara ayırma

Yaklaşık üç saniyelik gecikmenin yalnız YOLO'dan gelmediği görüldü. v0.1.2:

- `--preview-only` ile YOLO, olay kaydı ve uyarıları devre dışı bıraktı.
- FFplay/go2rtc/OpenCV karşılaştırma planını belgeledi.
- Ayrı `c301_h264_hw` deneyi tasarladı.
- Önizleme ve yakalama için regresyon testleri ekledi.

Kullanıcı gözleminde preview-only modu gecikmeyi tamamen çözmedi; dolayısıyla
“gecikme düzeldi” iddiası yapılmadı. Kaynak `v0.1.2` etiketindedir.

## 6. v0.2.0-preview — ilk Türkçe ses katmanı

Kamera izleme hattına dokunmadan ayrı bir ses yardımcısı eklendi:

- faster-whisper ile yerel Türkçe konuşma tanıma.
- Metin üzerinden saat ve hava gibi kural tabanlı yanıtlar.
- Open-Meteo ile hava sorgusu.
- PC mikrofonu ve PC hoparlörü kullanan istek üzerine önizleme.

Bu aşamada kamera mikrofonu ve hoparlörü ana asistan hattının parçası değildi.
Kaynak görüntü `v0.2.0-preview` etiketindedir.

## 7. Gecikme araçlarının geliştirilmesi

Sonraki yerel dosyalarda FFmpeg'i doğrudan subprocess pipe olarak kullanıp raw
BGR kare alma yolu eklendi. Ardışık düzeltmeler:

- düşük tamponlu FFmpeg parametreleri;
- `numpy.frombuffer()` sonucunun yazılabilir olması için `.copy()`;
- yeniden boyutlandırılabilir OpenCV penceresi;
- `F` ile tam ekran, `Q`/`Esc` ile çıkış.

Bu araçlar üretim NVR'ı değil, gecikmenin hangi katmanda oluştuğunu ölçmek içindir.

## 8. Kamera hoparlörü ve Ti v0.1-v0.3

Yerel çalışma dizinindeki Ti sürümleri gelişimi gösteriyor:

- v0.1: C301 ses akışından PCM alıp “Merhaba Ti” ile uyanan yardımcı.
- v0.2: komut eşleştirmeleri ve durum yanıtlarının genişletilmesi.
- v0.3: kayıt/Whisper teşhisi ve mikrofon eşiği ayarlarının geliştirilmesi.

`camera_speaker.py`, gTTS ile Türkçe MP3 üretip loopback geçici HTTP sunucusu ve
go2rtc ses geri kanalı üzerinden kameraya göndermeyi dener. Üretilen ses dosyası
çalma sonrasında silinir. gTTS çevrim içidir; metin dış TTS hizmetine gider.

Bu ilk dosyalar `legacy/ti/` altında korunur.

## 9. Ti v0.4 — sürekli oturum davranışı

Paylaşılan konuşmadaki v0.4 aşamasında uyandırma modeli değiştirildi:

1. İlk açılış için `Merhaba Ti` zorunlu.
2. Bundan sonra her komutta yeniden “Merhaba” denmesi gerekmiyor.
3. `Ti, <komut>` biçimi her zaman kabul ediliyor.
4. Yalnız `Ti` denirse yaklaşık 27 saniyelik tek devam sorusu açılıyor.
5. `İyi geceler`, `uykuya geç` veya `sus` oturumu kapatıyor.

v0.4 dosyası yerel diskte bulunamadı; davranış v0.5 kaynak kodunda devam ediyor.
Bu nedenle v0.4 için uydurma kaynak veya Git etiketi üretilmedi.

## 10. Akıllı kişi mevcudiyeti

Kare başına tekrar eden uyarılar yerine `PersonPresenceGate` eklendi:

- Giriş iki pozitif analizle doğrulanır.
- Çıkış sürekli negatif analiz süresinden sonra kabul edilir.
- Aynı kişi odada kalırken tekrar tekrar sesli uyarı üretilmez.
- Bu biyometrik kimlik veya kalıcı kişi takibi değildir.

İsteğe bağlı `C301_TRACK=1`, YOLO'nun ByteTrack modunu açar ve geçici track ID
ekler.

## 11. Ti v0.5 — hareket komutları ve görsel takip deneyi

v0.5 sola/sağa/yukarı/aşağı tek adım, beni takip et, takibi durdur, bana dön ve
motoru durdur niyetlerini tanır.

C301 ses akışı yön/açı bilgisi vermediği için “ses neredeyse oraya dön” özelliği
uygulanmadı. Yerine, görüntüde tam bir kişi varsa kutu merkezine göre küçük hareket
öneren görsel takip yazıldı. Birden çok kişi varsa hareket edilmez; kamera dışında
hedef aramak için gezinme yapılmaz.

Motor komutu:

- varsayılan kapalıdır;
- yalnız `--enable-motor` ile açılır;
- yaklaşık 2,8 saniyelik hız sınırı uygular;
- tek adım gönderir;
- stok go2rtc'de olmayan deneysel yerel uç noktaya bağlıdır;
- gerçek C301 motor kodları fiziksel olarak doğrulanmış kabul edilmez.

## 12. Bugünkü sonuç

Proje beş katmanlı bir prototipe dönüştü:

1. Yerel kamera köprüsü (go2rtc).
2. Düşük tamponlu görüntü yakalama.
3. YOLO algılama, olay ve kişi mevcudiyeti.
4. Kamera mikrofonu, Whisper ve Ti komut motoru.
5. Kamera hoparlörü ve kapalı varsayılan görsel/PTZ deneyleri.

Bir sonraki hedef, parçaları tek yapılandırma ve güvenli başlangıç komutu altında
birleştirmek; donanımda ölçülebilir testler tamamlanmadan deneysel özellikleri
“çalışıyor” diye işaretlememektir.
