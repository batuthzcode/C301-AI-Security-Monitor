# LinkedIn paylaşımı — hazır taslak (1 Kasım 2026)

Xiaomi C301 kamerayı, görüntüyü yerel olarak işleyen küçük bir yapay zekâ
güvenlik monitörüne dönüştürüyorum: **C301 AI Security Monitor + Ti AI v2.3**.

Bu geliştirme demosunda:

• C301/go2rtc yerel RTSP görüntüsü
• YOLO ile kişi ve nesne algılama
• Yerel olay, fotoğraf ve video kaydı
• Faster-Whisper ile Türkçe sesli komutlar
• PySide6 kontrol merkezi ve AR Studio
• Deneysel kişi takibi, kamera hoparlörü ve ağ güvenliği araçları

üzerinde çalıştım.

Gizlilik tarafı benim için özellikle önemliydi. Depoda gerçek kamera
yapılandırması, hesap tokenları, IP/MAC geçmişi, görüntü veya ses kaydı yok.
Sistem yüz kimliği tanımıyor ve fiziksel mesafe/radar ölçümü yaptığını iddia
etmiyor.

Güncel paket kişisel veriden arındırıldı; Windows üzerinde kurulup arayüzü kamera
olmadan da denenebiliyor. Donanımsız regresyon paketinde **181 test geçti** ve
son GitHub Actions çalışması başarılı tamamlandı.

Bu hâliyle hâlâ bir **demo/prototip**. Uzun süreli kamera kararlılığı, PTZ motoru
ve iki yönlü ses özellikleri gerçek donanımda daha fazla test gerektiriyor.

Kaynak kod ve kurulum:
https://github.com/batuthzcode/C301-AI-Security-Monitor

#Python #ComputerVision #CyberSecurity #YOLO #OpenCV #PySide6 #IoT #AI

---

Görsel: `ti_ai/assets/ti-ai-v2.3-demo.png` — kamera bağlı değilken alınmış,
kişisel veri içermeyen gerçek Ti AI v2.3 arayüz görüntüsü.
