# Gemini Live API + Google ADK

Bu proje, Google AI Studio ücretsiz katmanı üzerinden çalışan bir Gemini Live sesli terminal agentidir. Konuşmalar terminalde yazıya dökülür, Gemini yanıtı hem terminale yazılır hem hoparlörden oynatılır. Agent gerektiğinde Google Search ile güncel bilgi arar.

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

Ses aygıtlarını görmek veya varsayılan olmayan aygıtları seçmek için:

```bash
python main.py --list-devices
python main.py --input-device 2 --output-device 5
```

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

`adk web` yalnızca yerel geliştirme ve hata ayıklama içindir; üretim sunucusu olarak kullanılmamalıdır. Terminal istemcisi model konuşurken mikrofon aktarımını durdurarak hoparlör geri beslemesini önler; bu sırada modelin sözünü kesemezsiniz.

`patch_adk_web_audio.py`, ADK Web'in tarayıcı mikrofonunda yankı giderme, gürültü bastırma ve otomatik kazanç denetimini açıkça etkinleştirir. Ayrıca hoparlör geri beslemesini önlemek için model konuşurken mikrofon aktarımını geçici olarak durdurur ve arka plan seslerinin yanlış tetikleme ihtimalini azaltmak için Live API konuşma algılamasını düşük hassasiyete ayarlar. Bu yarı-dupleks koruma açıkken modelin sözünü konuşarak kesemezsiniz. Bağımlılıklar yeniden kurulursa betiği yeniden çalıştırın.
