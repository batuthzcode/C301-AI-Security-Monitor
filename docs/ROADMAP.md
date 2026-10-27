# C301 AI Security Monitor — development roadmap

## Şimdi — v0.5 deneysel konsolidasyon

- [x] v0.1.0–v0.2.0 arşivlerini etiketli Git geçmişine dönüştür.
- [x] Güncel kişi mevcudiyeti, kamera sesi ve Ti v0.5 kodunu birleştir.
- [x] Özel kamera verilerini ve model/binary dosyalarını dışarıda bırak.
- [x] Tarih, mimari, güvenlik ve kurulum belgelerini toparla.
- [x] Donanımsız birim testleri ve sözdizimi kontrolü ekle.
- [ ] Windows'ta temiz bir sanal ortamdan kurulumu tekrar doğrula.
- [ ] Kamera, ses ve motor için tek bir güvenli yapılandırma şeması tasarla.

## Sonraki — kararlı görüntü ve olay hattı

- [ ] OpenCV ve FFmpeg yakalamayı ortak arayüz altında birleştir.
- [ ] Kare yaşı, yakalama FPS'i, çıkarım FPS'i ve gecikmeyi GUI'de göster.
- [ ] Gerçek C301'de 30–60 dakikalık kararlılık testi yap.
- [ ] CS2, decoder ve yeniden bağlanma hatalarını ölç.
- [ ] Sınıf, güven eşiği, bölge ve cooldown ayarlarını kalıcılaştır.
- [ ] Yanlış pozitif/negatif örneklerle YOLO eşiklerini kalibre et.

## Ti — yerel ve güvenilir ses

- [ ] Ti'yi ana GUI'den güvenli şekilde başlat/durdur.
- [ ] gTTS yerine isteğe bağlı tamamen yerel Türkçe TTS ekle.
- [ ] Komut sözlüğünü test tablosuyla genişlet.
- [ ] Mikrofon eşiğini ortam gürültüsüne göre kontrollü kalibre et.
- [ ] Ses geri kanalı kesilirse PC hoparlörüne fallback ekle.
- [ ] Canlı kişi var/yok ve son olay zamanını Ti'ye bağla.
- [ ] Genel sohbet eklenecekse yerel/uzak veri akışını açıkça belgeleyerek ekle.

## Görsel takip ve PTZ — yalnız kontrollü deney

- [ ] C301 motor protokolünü güvenilir kaynak ve donanım ölçümüyle doğrula.
- [ ] Yazılımsal pan/tilt sınırları ve merkez/park konumu ekle.
- [ ] Acil durdurma, hareket bütçesi ve watchdog uygula.
- [ ] PTZ komutlarını mock sunucuyla otomatik test et.
- [ ] Fiziksel testte önce tek küçük hareket, sonra yönleri tek tek doğrula.
- [ ] Başarısız veya ters harekette otomatik kapatma uygula.
- [ ] Birden çok kişi ve hedef kaybı davranışlarını tanımla.

Ses yönüne dönme ayrı bir donanım problemidir. Tek mikrofon akışı yön bilgisi
sağlamıyorsa yazılımla güvenilir ses lokalizasyonu iddia edilmeyecek.

## Ürünleştirme

- [ ] Paketlenmiş Windows başlatıcı ve sağlık kontrolü.
- [ ] Şifreli uzak bildirim; varsayılan kapalı ve açık izinli.
- [ ] 24/7 kayıt için ayrı NVR entegrasyonu; uygulama olay odaklı kalır.
- [ ] Veri saklama süresi ve otomatik temizleme politikası.
- [ ] Herkese açık yayın öncesi lisans ve üçüncü taraf incelemesi.

## Kapsam dışı

- Yüz tanıma veya kişi kimliği çıkarımı.
- Gizli kayıt veya izinsiz uzaktan erişim.
- Kamera firmware'ini değiştirmek.
- Kalibre edilmemiş 2B konumu fiziksel mesafe/radar diye sunmak.

## Arşivdeki ilk yol haritası

All statuses are evidence-based. Do not describe a feature as verified on the
physical Xiaomi C301 until it has been tested on the user's device.

| Phase | Feature | State |
|---|---|---|
| 0 | Research C301/go2rtc stream integration | Documented, integration untested |
| 1 | Local Windows GUI with RTSP/webcam/video inputs | Implemented, physical camera untested |
| 1 | Synthetic demo, bounding boxes, 2D visualization | Windows demo UI confirmed by user screenshot; actual camera pending |
| 1 | Local JSONL events and saved snapshots | Implemented; end-to-end validation pending |
| 1 | PC speaker spoken alerts | Implemented with fallback; Windows test pending |
| 2 | Actual Xiaomi Home login and C301 live-stream verification | Pending user-side test |
| 2 | Optimize CPU/GPU video latency on target Windows laptop | Pending benchmark |
| 3 | Persistent multi-object IDs / real entry-exit detection | Planned |
| 3 | Arbitrary objects, zones, notification policies | Planned |
| 4 | Camera speaker audio via go2rtc backchannel | Experimental; not guaranteed |
| 4 | Remote notifications, encrypted access | Planned |
| 5 | Standalone always-on host; PC-off use case | Not in current scope |

No face recognition or identity claims in v0.1.
