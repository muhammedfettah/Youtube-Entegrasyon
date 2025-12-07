import os
import requests
import json
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google import genai
from google.genai.errors import APIError

# --- 1. AYARLAR VE API İSTEMCİLERİ ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    client = None

TEXT_MODEL = "gemini-2.5-flash" 
IMAGE_MODEL = "imagen-2.0-generate-002" # Görsel modeli tekrar deniyoruz
TEMP_DURATION = 20 

# --- 2. YARDIMCI İŞLEVLER ---

def download_image(image_url, save_path="temp_image.png"):
    """Görseli URL'den indirir."""
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return save_path
    except Exception as e:
        print(f"Görsel indirme hatası: {e}")
        return None

def cleanup_files(*files):
    """İşlem bitince geçici dosyaları siler."""
    for f in files:
        if f and os.path.exists(f):
            os.remove(f)

# --- 3. TELEGRAM İŞLEYİCİSİ (ANA İŞ AKIŞI) ---

async def generate_and_process_video(update, context, video_idea):
    
    if not client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ HATA: Gemini API Anahtarı eksik veya geçersiz.")
        return
        
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=f"🤖 Fikir alındı: '{video_idea}'. Başlıyorum...")

    temp_image_path = None

    try:
        # AŞAMA 1: SENARYO VE GÖRSEL TALİMATI ÜRETİMİ (Gemini)
        await context.bot.send_message(chat_id=chat_id, text="📝 Senaryo ve görsel talimatları üretiliyor...")
        
        system_instruction = ("Tüm çıktılarını aşağıdaki formatta, SADECE JSON olarak ver. Ek metin EKLEME.")
        prompt = f"Video fikri: {video_idea}"
        
        response = client.chats.create(
            model=TEXT_MODEL,
            config={
                "systemInstruction": system_instruction, 
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT", "properties": {
                        "image_prompt": {"type": "STRING", "description": "Görsel üretim modeli için detaylı, İngilizce talimat."},
                        "script": {"type": "STRING", "description": f"{TEMP_DURATION} saniyelik Türkçe konuşma metni."},
                        "youtube_title": {"type": "STRING", "description": "YouTube videosu için ilgi çekici Türkçe başlık."}
                    }
                }
            }
        ).send_message(message=prompt)

        # HATA KORUMASI
        if not response.text:
            await context.bot.send_message(chat_id=chat_id, text="❌ Gemini'dan boş veya engellenmiş cevap geldi. Lütfen daha genel ve güvenli bir fikir deneyin.")
            return

        data = json.loads(response.text)
        image_prompt, script, youtube_title = data["image_prompt"], data["script"], data["youtube_title"]

        # AŞAMA 1.5: GÖRSEL ÜRETİMİ VE İNDİRME
        await context.bot.send_message(chat_id=chat_id, text="📸 Görsel oluşturuluyor ve indiriliyor...")
        
        image_result = client.models.generate_images( 
            model=IMAGE_MODEL,
            prompt=image_prompt,
            config=dict(number_of_images=1, aspect_ratio="16:9")
        )
        
        image_url = image_result.generated_images[0].image.url 
        temp_image_path = download_image(image_url) 
        
        # AŞAMA 2: TELEGRAM'A BİLDİRİM VE GÖRSEL GÖNDERME
        await context.bot.send_message(chat_id=chat_id, text="✅ İçerik Hazırlandı! Sonuç gönderiliyor...")
        
        if temp_image_path:
            # Görsel varsa, fotoğrafı senaryo ile birlikte gönder
            with open(temp_image_path, 'rb') as image_file:
                 await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=image_file,
                    caption=f"🎥 **{youtube_title}**\n\n**Senaryo:** {script}\n\n✅ BOT BAŞARIYLA ÇALIŞIYOR.",
                    parse_mode=telegram.constants.ParseMode.MARKDOWN
                )
        else:
            # Görsel oluşturma başarısız olursa sadece metni gönder
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Görsel Oluşturma Başarısız Oldu (API Anahtarınızı Kontrol Edin).\n\n🎥 **{youtube_title}**\n\n**Senaryo:** {script}",
                parse_mode=telegram.constants.ParseMode.MARKDOWN
            )

        
    except APIError as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ API Hatası (Gemini): Hata: {e}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Genel İşlem Hatası: {e}")
        
    finally:
        cleanup_files(temp_image_path) 


# --- 4. ANA FONKSİYON VE BAŞLATMA ---

async def start_command(update, context):
    teacher_response = "Ben bir yapay zekayım." 

    await update.message.reply_text(
        f"Merhaba! Öğretmenin sorarsa: {teacher_response}\n\nLütfen bir video fikri yazın."
    )

async def handle_message(update, context):
    video_idea = update.message.text.strip()
    if video_idea.startswith('/'):
        return 
        
    await generate_and_process_video(update, context, video_idea)


def main():
    if not TELEGRAM_BOT_TOKEN:
        return
        
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("YouTube Otomasyon Botu çalışmaya başladı...")
    app.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()
