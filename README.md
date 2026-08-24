# Gemini Live API + Google ADK

Bu proje, Google AI Studio ücretsiz katmanı üzerinden çalışan bir Gemini Live sesli sohbet istemcisidir. Konuşmalar terminalde yazıya dökülür, Gemini yanıtı hem terminale yazılır hem hoparlörden oynatılır.

## Simüle robot agent'ları

Canlı asistan aynı zamanda donanım gerektirmeyen bir robot kontrol demosudur.
Koordinatör agent, isteği dört uzmanlık alanına ayırır:

- sensörler: sıcaklık, pil, nem, engel mesafesi ve ortam ışığı
- ışık/ses: renk, parlaklık ve buzzer kontrolü
- hareket: yön, hız, durdurma ve fan kontrolü
- sistem: kamera, çalışma modu, acil durdurma ve genel durum

Toplam 20 fonksiyon `app/google_search_agent/robot_tools.py` içinde tanımlıdır.
Koordinatör robot işlemlerini doğrudan yapmaz; dört aktif uzman agent'ı `AgentTool`
olarak çağırır. Yirmi fonksiyon sensör, ışık/ses, hareket ve sistem agent'ları
arasında beşer adet paylaştırılır. Aynı Live turundaki bağımsız agent-tool
çağrıları paralel çalışabilir ve koordinatör işlemi ikinci kez uygulamaz.
Araçlar değerleri doğrudan bellekten okumaz; paralel istek kabul eden yerel bir
HTTP robot API'sine bağlanır. API'nin arkasındaki değerler süreç belleğinde
simüle edilir ve uygulama yeniden başladığında başlangıç durumuna döner. Kullanıcı
komutları, çalışan fonksiyonlar, argümanlar, sonuçlar ve Gemini yanıtları ise
SQLite tabanlı kalıcı işlem geçmişine kaydedilir. Örnek sesli komutlar:

```text
Robotun sıcaklığı kaç derece?
Işığı yeşil yap.
Parlaklığı yüzde 40 yap.
Robotu yüzde 25 hızla ileri götür.
Işığı mavi yap ve fanı aç.
Robotun genel durumunu söyle.
```

Koordinatör, düşük tepki süresi için araçları doğrudan kullanır. Bağımsız birden
fazla işlem aynı model turunda istenir; gerçek asenkron API adaptörleri daha sonra
aynı araç fonksiyonlarının içine eklenebilir. Uzman agent'lar bağımsız `AgentTool`
olarak çalışır; agent transferi kullanılmaz.

## Gereksinimler

- Python 3.10 veya üzeri
- Ücretsiz bir Google AI Studio API anahtarı

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp app/.env.example app/.env
```

`app/.env` içindeki `GOOGLE_API_KEY` değerine [Google AI Studio](https://aistudio.google.com/app/apikey) üzerinden oluşturduğunuz anahtarı yazın. Anahtarı paylaşmayın veya Git'e eklemeyin.

## Çalıştırma

Sanal ortam etkinken proje kökünden:

```bash
python main.py
```

Tarayıcı açılmaz. Terminalde `Gemini Live hazır` mesajı göründüğünde konuşmaya başlayın. Çıkmak için `Ctrl+C` kullanın.

Her sesli yanıttan sonra terminalde, kullanıcının konuşmasının yaklaşık bitişinden
Gemini'nin ilk yanıt sesinin başlamasına kadar geçen geri dönüş süresi gösterilir.
Ölçüme yapılandırılmış 300 ms konuşma sonu sessizlik algılama süresi de eklenir.

Ses aygıtlarını görmek veya varsayılan olmayan aygıtları seçmek için:

```bash
python main.py --list-devices
python main.py --input-device 2 --output-device 5
```

Robot araçlarını yazıyla ve gecikme ölçümüyle denemek için:

```bash
python main.py --text
```

Kalıcı geçmişi text modu içinden `geçmiş` veya `/gecmis` yazarak görebilirsiniz.
Uygulamayı açmadan son 20 kaydı veya istediğiniz sayıyı listelemek için:

```bash
python main.py --history
python main.py --history 5
```

Geçmiş varsayılan olarak Git'e eklenmeyen `app/robot_memory.db` dosyasındadır.

Text modundaki Gemini 3.x modelinde thinking `MINIMAL`, terminal Live native-audio
modelinde ve uzman agent'larda ise desteklenen en düşük değer olan bütçe `0`
olarak ayarlanır.

Text ve Live modları aynı koordinatör, dört uzman agent ve HTTP API akışını
kullanır. Yalnızca zorunlu olarak model/protokol farklıdır: text modu
`generateContent`, ses modu Live bağlantısı kullanır.

Live modunda fonksiyon başlangıç süresi son kullanıcı transkripsiyonunun ulaştığı
andan ölçülür. Bu, konuşma bitişinin yaklaşık karşılığıdır ve yapılandırılmış VAD
konuşma sonu sessizlik eşiğinden etkilenir.

Her araç için Enter'a basılmasından fonksiyonun gerçekten çalışmaya başladığı ana
kadar geçen süre gösterilir. Paralel araçların her biri başladığı anda ayrı
raporlanır. Text modunda Gemini'nin nihai yazılı cevabı gösterilmez.

## İsteğe bağlı web arayüzü

ADK geliştirme arayüzünü kullanmak isterseniz önce ses koruma yamasını uygulayın, ardından `--web` ile başlatın:

```bash
python scripts/patch_adk_web_audio.py
python main.py --web
```

Web sunucusu hazır olduğunda tarayıcı otomatik açılır. Native-audio modelinde mavi okla metin göndermeyin; yeşil telefon düğmesini kullanın.

## Yapılandırma

| Değişken | Açıklama |
| --- | --- |
| `GOOGLE_API_KEY` | Google AI Studio'dan alınan gizli API anahtarı |
| `GOOGLE_GENAI_USE_ENTERPRISE` | Ücretsiz Gemini Developer API için `FALSE` |
| `GEMINI_LIVE_MODEL` | İsteğe bağlı Live model override'ı |
| `GEMINI_TEXT_MODEL` | Metin test modunda kullanılacak model |
| `GEMINI_TEXT_WARMUP` | İlk komuttan önce model bağlantısını ısıtır (`TRUE`) |
| `ROBOT_API_DELAY_MS` | Yerel robot API'sinin simüle ağ/işlem gecikmesi (ms) |
| `ROBOT_API_BASE_URL` | İsteğe bağlı gerçek veya ayrı çalışan robot API adresi |
| `ROBOT_MEMORY_DB` | İsteğe bağlı kalıcı SQLite geçmiş dosyasının yolu |

Sesli tool calling için `gemini-3.1-flash-live-preview` kullanılır. Önceki 2.5
native-audio preview modeli ses transkripsiyonunu üretse de function call aşamasında
zaman aşımı veya `1011` sunucu hatası oluşturduğu için kullanılmaz.

`adk web` yalnızca yerel geliştirme ve hata ayıklama içindir; üretim sunucusu olarak kullanılmamalıdır. Terminal istemcisi model konuşurken mikrofon aktarımını durdurarak hoparlör geri beslemesini önler; bu sırada modelin sözünü kesemezsiniz.

`patch_adk_web_audio.py`, ADK Web'in tarayıcı mikrofonunda yankı giderme, gürültü bastırma ve otomatik kazanç denetimini açıkça etkinleştirir. Ayrıca hoparlör geri beslemesini önlemek için model konuşurken mikrofon aktarımını geçici olarak durdurur ve arka plan seslerinin yanlış tetikleme ihtimalini azaltmak için Live API konuşma algılamasını düşük hassasiyete ayarlar. Bu yarı-dupleks koruma açıkken modelin sözünü konuşarak kesemezsiniz. Bağımlılıklar yeniden kurulursa betiği yeniden çalıştırın.
