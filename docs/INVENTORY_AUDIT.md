# Kaynak bütünlüğü ve yayın envanteri

Bu denetim 28 Ekim 2026'da, yerel proje klasörü ile dört sürüm ZIP'i Git
geçmişi ve GitHub'a gönderilecek dosyalar karşılaştırılarak yapıldı.

## Doğrulanan sürüm arşivleri

Her ZIP girdisinin Git blob özeti ilgili etiketteki dosyayla karşılaştırıldı.
Dosya adı, dosya sayısı ve içerik bakımından fark bulunmadı:

| Arşiv | Dosya | Git etiketi | Eksik | Değişmiş | Fazladan |
|---|---:|---|---:|---:|---:|
| v0.1.0 | 23 | `v0.1.0` | 0 | 0 | 0 |
| v0.1.1 low-latency | 30 | `v0.1.1` | 0 | 0 | 0 |
| v0.1.2 latency diagnostics | 32 | `v0.1.2` | 0 | 0 | 0 |
| v0.2.0 voice preview | 38 | `v0.2.0-preview` | 0 | 0 | 0 |

## Sonradan bulunan güvenli yerel kaynaklar

İlk yayın denetiminde ana çalışma klasöründe kalan metin tabanlı ara kaynaklar
da bulundu ve anlamları değiştirilmeden arşivlendi:

- `experimental/installers/install_c301_ptz_v2.py`
- `experimental/ptz/` altındaki tek-pencere PowerShell motor deneyi ve açıklaması
- `docs/milestones/` altındaki NumPy salt-okunur kare ve yeniden boyutlandırılabilir
  önizleme notları
- `legacy/local-snapshots/` altındaki GUI, worker, takip ve kamera-ses ara yedekleri

Bu dosyalar güncel çalıştırma giriş noktası değildir. Özellikle PTZ kaynakları
deneyseldir, gerçek C301 üzerinde doğrulanmamıştır ve varsayılan olarak kapalıdır.

## Bilinçli olarak yayımlanmayanlar

Aşağıdakiler kaynak geçmişinin parçası sayılmaz ve güvenlik, gizlilik veya depo
boyutu nedeniyle GitHub'a gönderilmez:

- `.venv/`, `__pycache__/` ve derleme/çalışma artıkları
- `private_data/` olay görüntüleri ve JSONL kayıtları
- gerçek `go2rtc.yaml`, Xiaomi URL/token/hesap ve cihaz bilgileri
- `_voice_test/` ve `ti_mikrofon_test.wav` kişisel test sesleri
- `yolo11n.pt` model ağırlığı; Ultralytics tarafından gerektiğinde indirilir
- üretilmiş MP3/WAV/video dosyaları ve çalıştırılabilir binary'ler

`.gitignore` bu sınıfları engeller. Yayın öncesi taramada gerçek kimlik bilgisi,
özel Xiaomi bağlantısı veya kamera kaydı bulunmadı.

## v0.4 açıklaması

Yerel diskte bağımsız bir v0.4 kaynak dosyası bulunmadığından uydurma bir sürüm
oluşturulmadı. Paylaşılan konuşmada tarif edilen oturum davranışı v0.5 kodunda
korunur ve `docs/HISTORY_TR.md` içinde açıkça belgelenir.
