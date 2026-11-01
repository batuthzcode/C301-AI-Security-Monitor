# LinkedIn paylaşımı — hazır taslak (1 Kasım 2026)

Xiaomi C301 kamerayı yalnızca nesne algılayan bir güvenlik kamerası olarak değil,
benimle Türkçe konuşan deneysel bir kişisel asistana dönüştürüyorum:
**C301 AI Security Monitor + Ti AI v2.3**.

Ti'nin amacı, kamera güvenliğiyle günlük asistan deneyimini aynı yerel kontrol
merkezinde buluşturmak. Kamera ve sistem durumunu sorabiliyorum. “Ti, saldırı
tehdidi var mı?” dediğimde son Cyber SOC örneklemini özetleyip gördüğü şüphe
işaretlerini ve analizin sınırlarını söylüyor. İsteğe bağlı sohbet modeliyle genel
sorulara yanıt verebiliyor. Sıkıldığımda ise AR Studio'yu açıp parmağımla havaya
çizim yapabiliyorum.

Bu geliştirme demosunda:

• C301/go2rtc yerel RTSP görüntüsü
• YOLO ile kişi ve nesne algılama
• Yerel olay, fotoğraf ve video kaydı
• Faster-Whisper ile Türkçe sesli komutlar
• PySide6 kontrol merkezi ve gerçek zamanlı AR Studio
• Türkçe kişisel asistan komutları ve isteğe bağlı sohbet modeli
• “Saldırı tehdidi var mı?” sorusu için açıklamalı Cyber SOC özeti
• Deneysel kişi takibi, kamera hoparlörü ve yerel ağ güvenliği araçları

üzerinde çalıştım.

Gizlilik tarafı benim için özellikle önemliydi. Depoda gerçek kamera
yapılandırması, hesap tokenları, IP/MAC geçmişi, görüntü veya ses kaydı yok.
Sistem yüz kimliği tanımıyor ve fiziksel mesafe/radar ölçümü yaptığını iddia
etmiyor. Paylaşım görsellerindeki IP, alan adı, adaptör kimliği ve kesin tarih/saat
bilgileri kaldırıldı.

Canlı Cyber SOC testinde izinli Wi-Fi adaptöründe 12 saniyede 800 paket
örneklendi ve tanımlı şüphe eşiği aşılmadı. Bu sonuç “saldırı kesinlikle yok”
anlamına gelmiyor; Ti bir antivirüs veya profesyonel SOC yerine geçmiyor.

Güncel paket kişisel veriden arındırıldı; Windows üzerinde kurulup arayüzü kamera
olmadan da denenebiliyor. Donanımsız regresyon paketinde **181 test geçti** ve
son GitHub Actions çalışması başarılı tamamlandı.

Bu hâliyle hâlâ bir **demo/prototip**. Uzun süreli kamera kararlılığı, PTZ motoru
ve iki yönlü ses özellikleri gerçek donanımda daha fazla test gerektiriyor.

Kaynak kod ve kurulum:
https://github.com/batuthzcode/C301-AI-Security-Monitor

#Python #ComputerVision #CyberSecurity #YOLO #OpenCV #PySide6 #IoT #AI

---

Paylaşım görselleri:

1. `ti_ai/assets/ti-ai-v2.3-demo.png` — ana kontrol merkezi
2. `ti_ai/assets/ti-ai-v2.3-ar-studio.png` — sentetik AR görsel testi
3. `ti_ai/assets/ti-ai-v2.3-ar-live-drawing.png` — gerçek parmak çizimi ve el takibi
4. `ti_ai/assets/ti-ai-v2.3-cyber-soc-live-redacted.png` — anonimleştirilmiş gerçek test

