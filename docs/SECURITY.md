# Güvenlik ve yayımlama kontrol listesi

## Depoya hiçbir zaman eklenmeyecekler

- Gerçek `go2rtc.yaml` ve yedekleri.
- Tam `xiaomi://` URL'si, Xiaomi kullanıcı bilgisi, token ve cihaz kimliği.
- Özel LAN IP'leri ve ev ağı ayrıntıları.
- `private_data/` olay görüntüleri veya ev içi ekran görüntüleri.
- Mikrofon test WAV/MP3 dosyaları.
- `.env`, API anahtarı, parola veya doğrulama kodu.
- `go2rtc.exe`, FFmpeg binary'leri, model ağırlıkları ve ZIP paketleri.

## GitHub'a göndermeden önce

```powershell
git status --short
git ls-files
git grep -n -i -E 'password|passwd|token|secret|api[_-]?key|xiaomi://'
```

`xiaomi://` için yalnız `PRIVATE_*`, `[REDACTED]` veya `...` gibi açık yer
tutucularına izin verilir. Sonuçları tek tek okuyun.

## Ağ sınırı

- go2rtc API ve RTSP dinleyicilerini `127.0.0.1` üzerinde tutun.
- 1984/8554 portlarını router üzerinden internete açmayın.
- Uzaktan erişim gerekiyorsa ayrı, kimliği doğrulanmış ve şifreli bir çözüm
  tasarlayın; bu prototipi doğrudan yayımlamayın.

## Bulut hizmetleri

Ana görüntü hattı yerel çalışır. Ancak gTTS kullanıldığında söylenecek metin dış
hizmete gönderilir; hava özelliği Open-Meteo'ya şehir sorgusu yapar; model ilk
indirmeleri internete çıkar. Bunlar README'de açıkça belirtilmelidir.

## PTZ

- PTZ varsayılan kapalı kalmalıdır.
- Doğrulanmamış motor paketleri sürekli veya tekrarlı gönderilmemelidir.
- Fiziksel test kamera devrilmeyecek şekilde sabitlenerek yapılmalıdır.
- Mekanik sınır, ters yön veya beklenmeyen hareket görülürse işlem durdurulmalıdır.

## Gizlilik

Kamera ve mikrofon verisi kişisel veri içerebilir. Kayıt yapılan kişileri
bilgilendirin, gerekli izinleri alın ve olay verilerini gereğinden uzun tutmayın.
