# Ti C301 motor denemesi — tek PowerShell penceresi

Bu paket **Ti v0.5 dosyanızı veya mevcut çalışan `go2rtc_audio_fixed.exe` dosyanızı değiştirmez**. Deneysel ayrı `go2rtc_ti_ptz_experimental.exe` derler ve Ti'yi `--enable-motor` ile başlatır. Motor adımları **C301 üzerinde fiziksel olarak henüz doğrulanmamıştır**. Her komut bir adımdır; ilk denemede sadece bir kez "Ti, sola dön" deyin. Xiaomi Home otomatik motor takibini önceden kapatın.

1. ZIP içindeki `Ti_Motor_TekPencere.ps1` ve `install_c301_ptz_v2.py` dosyalarını `ti_assistant_v0_5.py` ile aynı C301 proje klasörüne çıkarın.
2. Açık Ti işlemini Ctrl+C ile durdurun. Var olan tek PowerShell pencerenizden proje klasörüne gidin.
3. İlk sefer bir güvenlik duvarı kuralı gerekebilir. İlk çalıştırmada yetki hatası alırsanız **PowerShell'i bir kez yönetici olarak açın**, proje klasörüne gidin, aynı komutu çalıştırın. Daha sonra normal açabilirsiniz.
4. **Tek komut:** `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Ti_Motor_TekPencere.ps1`
5. Dinlemeye geçtiğinde "Merhaba Ti", ardından "Ti, sola dön" deyin.

Sistem, güvenlik amacıyla go2rtc HTTP portunun (1984) yalnızca localhost'tan dinlenmesini ister. Bu şart sağlanmazsa denemeyi kapatır. `go2rtc.yaml` dosyasını düzenlemeden önce bir kopyasını alın ve gizli Xiaomi erişim bilgilerini paylaşmayın. `api:` altında `listen: "127.0.0.1:1984"` ayarı kullanılabilir; diğer `api` parametrelerini silmeyin. Konfigürasyonu değiştirmek kamera ve ses akışını etkileyebilir.

**Kurulum ne yapar?** Mevcut ses düzeltmesi uygulanmış go2rtc kaynak koduna bir deneysel tek-adım Xiaomi motor endpoint'i ekler; ilgili Go paketlerini sadece derleyerek denetler, ayrıca PTZ EXE üretir. Motor HTTP çağrıları uzak ağ adreslerinden reddedilir. Go kaynağı için daha önceki klasörün varlığı ve `go` derleyicisinin PATH üzerinde bulunması gerekir. Kaynak kodu mevcut değilse durur; otomatik indirme yapmaz.

**Geri dönüş:** Ti Ctrl+C ile durdurulunca deneysel go2rtc işlemi kapanır. Eskisi hâlâ `%LOCALAPPDATA%\C301-go2rtc-audio-fix\go2rtc_audio_fixed.exe` yolundadır. Önceki çalışan sesli asistan kurulumunu aynı yöntemle açabilirsiniz. Çalışan sürümünüz, Xiaomi yapılandırması ve kameranın firmware'i değiştirilmez.
