# Siri-for-Windows
# Türkçe Sesli Asistan

Bu proje, Türkçe konuşmayı algılayabilen ve çeşitli görevleri yerine getirebilen bir sesli asistan uygulamasıdır. Kullanıcıların sesli komutlarla uygulamaları açmasına, internet aramaları yapmasına, hava durumu bilgisi almasına, hatırlatıcılar ayarlamasına, matematiksel işlemler yapmasına, e-posta göndermesine, takvim etkinlikleri eklemesine ve Spotify veya yerel müzik çalmasına olanak tanır. Ayrıca, Grok API ile entegre edilerek tanınmayan komutlar için yapay zeka destekli yanıtlar sağlar.

## Özellikler

- **Sesli Komut Tanıma**: Türkçe sesli komutları algılar ve işler.
- **Uygulama ve Dosya Açma**: Kullanıcı tanımlı uygulamaları veya klasörleri sesli komutlarla açar.
- **İnternet Arama**: Google'da arama yapar.
- **Hava Durumu**: OpenWeatherMap API üzerinden hava durumu bilgisi sağlar.
- **Hatırlatıcılar**: Belirli saatlerde hatırlatıcılar ayarlar ve bildirir.
- **Matematiksel İşlemler**: Temel işlemler (toplama, çıkarma, çarpma, bölme) ve ileri matematik (türev, integral, denklem çözme).
- **E-posta Gönderme**: Gmail üzerinden e-posta gönderir.
- **Takvim Entegrasyonu**: Google Calendar'a etkinlik ekler.
- **Müzik Çalma**: Spotify veya yerel müzik dosyalarını çalar.
- **Grok API Entegrasyonu**: Tanınmayan komutlar için xAI'nin Grok modelinden yanıt alır.
- **Sistem Komutları**: Bilgisayarı kapatma, yeniden başlatma veya uyku moduna geçirme.
- **Komut Kaydı**: Komut geçmişi veritabanında saklanır ve CSV'ye aktarılabilir.
- **Sistem Tepsisi**: Arka planda çalışır ve sistem tepsisi üzerinden kontrol edilir.
- **Ses Seviyesi Kontrolü**: Sesli yanıtların ses seviyesini ayarlar.

## Kurulum

### Gereksinimler

- Python 3.8+
- Gerekli Python kütüphaneleri:
  ```bash
  pip install customtkinter tkinter speechrecognition plyer pillow rapidfuzz pystray stanza requests schedule wikipedia-api sympy pyttsx3 openai python-dotenv google-auth google-auth-oauthlib google-api-python-client joblib
  ```
  Opsiyonel (sesli yanıt için):
  ```bash
  pip install gTTS pydub playsound
  ```

- **API Anahtarları**:
  - OpenWeatherMap API anahtarı (`WEATHER_API_KEY`)
  - xAI Grok API anahtarı (`XAI_API_KEY`)
  - Gmail uygulama şifresi (`GMAIL_ADDRESS` ve `GMAIL_APP_PASSWORD`)
  - Spotify API kimlik bilgileri (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`)

- **Google Calendar API**:
  - Google Developer Console'dan `credentials.json` dosyasını indirin ve proje dizinine yerleştirin.
  - İlk çalıştırmada tarayıcı üzerinden yetkilendirme yapmanız gerekecek.

- **Stanza Türkçe Modeli**:
  ```bash
  python -m stanza download tr
  ```

### Kurulum Adımları

1. Depoyu klonlayın:
   ```bash
   git clone https://github.com/kullanici_adiniz/turkce-sesli-asistan.git
   cd turkce-sesli-asistan
   ```

2. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

3. `.env` dosyasını oluşturun ve gerekli API anahtarlarını ekleyin:
   ```env
   XAI_API_KEY=your_xai_api_key
   GMAIL_ADDRESS=your_email@gmail.com
   GMAIL_APP_PASSWORD=your_app_password
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
   ```

4. `WEATHER_API_KEY`, `ICON_ON_PATH`, `ICON_OFF_PATH` ve `MUSIC_FOLDER` değişkenlerini `main.py` içinde yapılandırın.

5. Programı çalıştırın:
   ```bash
   python main.py
   ```

## Kullanım

1. **Mikrofon Seçimi**: Açılış ekranında mevcut mikrofonlardan birini seçin.
2. **Uygulama/Klasör Ekleme**: "Uygulama/Dosya Ekle" veya "Klasör Ekle" butonlarıyla uygulamaları veya klasörleri ekleyin ve tetikleme kelimeleri belirleyin.
3. **Asistanı Başlat**: "Asistanı Başlat" butonuna tıklayın; asistan sistem tepsisine küçülecek ve sesli komutları dinlemeye başlayacaktır.
4. **Komutlar**:
   - **Uygulama Açma**: "Not defterini aç"
   - **Arama**: "Google'da Python ara"
   - **Hava Durumu**: "İstanbul hava durumu"
   - **Hatırlatıcı**: "Yarın 10:00'da toplantıyı hatırlat"
   - **Matematik**: "5 artı 3", "x kare artı 2x çöz"
   - **E-posta**: "Ali'ye e-posta gönder"
   - **Müzik**: "Dua Lipa şarkısı çal"
   - **Takvim**: "Yarın 14:00'te toplantı ekle"
   - **Sistem**: "Bilgisayarı kapat"
   - **Ses Kontrolü**: "Sesi yüzde 50 yap"
   - **Fikir Danışmanlığı**: "Proje için fikir ver"
   - **Favori Komut**: "Favori komutumu çalıştır"

5. **Sistem Tepsisi**: Asistanı başlat/durdur, menüyü aç veya tamamen kapat.

6. **Log Sayfası**: Komut geçmişini görüntüleyin, filtreleyin ve CSV'ye aktarın.

## Notlar

- **Hata Günlüğü**: Hatalar `assistant.log` dosyasına kaydedilir.
- **Veritabanı**: Komut geçmişi ve hatırlatıcılar `assistant.db` SQLite veritabanında saklanır.
- **Spotify**: İlk kullanımda tarayıcıdan yetkilendirme kodu almanız gerekir.
- **Google Calendar**: İlk kullanımda tarayıcıdan yetkilendirme yapmanız gerekir.
- **gTTS**: İnternet bağlantısı gerektirir; yoksa `pyttsx3` kullanılır.
- **Önbellekleme**: NLP işlemleri için `joblib` ile önbellekleme yapılır.

## Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen aşağıdaki adımları izleyin:

1. Depoyu fork edin.
2. Yeni bir özellik dalı oluşturun (`git checkout -b feature/yeni-ozellik`).
3. Değişikliklerinizi yapın ve commit edin (`git commit -m 'Yeni özellik eklendi'`).
4. Dalınızı itin (`git push origin feature/yeni-ozellik`).
5. Bir Pull Request açın.

## Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır.

## İletişim

Sorularınız veya önerileriniz için: [beratardiic@gmail.com](mailto:beratardiic@gmail.com)
