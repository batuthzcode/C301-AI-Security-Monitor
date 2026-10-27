# Mimari ve veri akışı

## Görüntü yolu

1. C301 kendi Xiaomi akışını üretir.
2. go2rtc özel yerel yapılandırmayla akışı `127.0.0.1` RTSP'ye köprüler.
3. `CameraWorker`, OpenCV veya FFmpeg pipe ile kareleri sürekli çeker.
4. `LatestFrameBuffer` yalnız en yeni kareyi saklar.
5. YOLO belirli aralıklarla karenin bir kopyasını analiz eder.
6. `unpack_yolo()` sonucu taşınabilir `Detection` nesnelerine dönüştürür.
7. `EventGate` sınıfın kaybolup yeniden görünmesini değerlendirir.
8. `PersonPresenceGate` kişi girişini iki pozitif analizle doğrular.
9. GUI kutuları ve 2B görüntü konumlarını çizer.
10. `EventRecorder` yalnız olay anında JPEG ve JSONL üretir.

## Sesli asistan yolu

1. FFmpeg, C301 ses RTSP akışını mono 16 kHz PCM'e çevirir.
2. `UtteranceGate` enerji eşiği ve sessizlikle cümle sınırını bulur.
3. faster-whisper Türkçe metni bilgisayarda üretir.
4. `interpret_utterance()` uyandırma, komut veya devam sorusunu seçer.
5. Kural tabanlı komut motoru yanıtı üretir.
6. `C301Speaker`, gTTS MP3'ünü geçici loopback HTTP adresinde sunar.
7. go2rtc/FFmpeg ses geri kanalı cevabı kameraya göndermeyi dener.
8. Hoparlör çalarken asistan kendi sesini tekrar algılamamak için cümle kapısını
   geçici olarak sıfırlar.

## Görsel takip ve PTZ güvenlik sınırları

`TiPersonFollower` yalnız bir kişi kutusu olduğunda merkez sapmasını hesaplar.
Yatay sapma önce, sonra dikey sapma değerlendirilir. Sapma eşik altındaysa hareket
yoktur. Birden fazla kişi, eksik akış veya model hatasında hareket üretilmez.

`TiMotor` sürekli dönüş değil tek adım gönderir, yön beyaz listesi ve hareketler
arasında bekleme uygular. Deneysel go2rtc yamasındaki Xiaomi motor paketleri
doğrulanmadığı için `--enable-motor` olmadan kapalıdır.

## Güven sınırları

```text
Git deposu
  ├─ Python kaynakları
  ├─ örnek loopback YAML
  └─ sentetik/ayıklanmış belgeler

Özel yerel alan (Git dışında)
  ├─ gerçek go2rtc.yaml ve Xiaomi URL/token'ı
  ├─ kamera olay görüntüleri
  ├─ mikrofon test WAV'ları
  ├─ model ağırlıkları
  └─ yerel go2rtc/FFmpeg çalıştırılabilir dosyaları
```

## Bilinen teknik borç

- Kamera, GUI ve Ti henüz tek süreç ve ayar dosyasında birleşmiş değil.
- gTTS çevrim içi; tamamen yerel TTS seçeneği eklenmeli.
- Kamera sesi özel go2rtc davranışına bağlı.
- OpenCV ve FFmpeg yakalama yolları ortak soyutlamada toplanmalı.
- PTZ yaması upstream API değildir ve donanım doğrulaması eksiktir.
- Gerçek donanım entegrasyon testleri CI'da çalıştırılamaz.
