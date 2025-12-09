import os
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
IMAGE_MODEL = "imagen-2.0-generate-002" 

# --- 2. YARDIMCI İŞLEVLER ---

def cleanup_files(*files):
    """Bu projede geçici dosya olmadığı için pas geçiyoruz."""
    pass 

# --- 3. TELEGRAM İŞLEYİCİSİ (ANA İŞ AKIŞI) ---

async def generate_and_process_movie_info(update, context, search_query):
    
    if not client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ HATA: Gemini API Anahtarı eksik veya geçersiz.")
        return
        
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=f"🎬 Film/Dizi Bilgisi alınıyor: '{search_query}'. Başlıyorum...")

    try:
        # AŞAMA 1: FİLM BİLGİSİ ÜRETİMİ (Tarihler ve Özet)
        await context.bot.send_message(chat_id=chat_id, text="📝 Bilgiler (Özet, Tarih, Poster) Gemini'dan sorgulanıyor...")
        
        system_instruction = ("Tüm çıktılarını aşağıdaki formatta, SADECE JSON olarak ver. Ek metin EKLEME. Filmin posteri için görsel talimatı oluştur.")
        prompt = f"Şu film/dizi için Türkçe özet, başlangıç ve bitiş tarihlerini ve poster görseli için İngilizce bir talimat hazırla: {search_query}"
        
        response = client.chats.create(
            model=TEXT_MODEL,
            config={
                "systemInstruction": system_instruction, 
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT", "properties": {
                        "movie_title": {"type": "STRING", "description": "Sorgulanan filmin/dizinin resmi adı."},
                        "summary": {"type": "STRING", "description": "Filmin/dizinin kısa Türkçe özeti."},
                        "image_prompt": {"type": "STRING", "description": "Filmin posteri tarzında, İngilizce görsel talimatı."},
                        "start_date": {"type": "STRING", "description": "Filmin/dizinin başlangıç tarihi (Örn: 2023 veya 2023-11-01)."},
                        "end_date": {"type": "STRING", "description": "Filmin/dizinin bitiş tarihi (Devam ediyorsa 'Hala devam ediyor' yaz)."}
                    }
                }
            }
        ).send_message(message=prompt)

        if not response.text:
            await context.bot.send_message(chat_id=chat_id, text="❌ Gemini'dan boş cevap geldi. Lütfen farklı bir film adı deneyin.")
            return

        data = json.loads(response.text)
        movie_title, summary, image_prompt, start_date, end_date = data["movie_title"], data["summary"], data["image_prompt"], data["start_date"], data["end_date"]

        # AŞAMA 2: POSTER GÖRSELİ ÜRETİMİ (Sadece URL Alınıyor)
        await context.bot.send_message(chat_id=chat_id, text="📸 Poster görseli URL'si oluşturuluyor...")
        
        image_result = client.models.generate_images( 
            model=IMAGE_MODEL,
            prompt=image_prompt,
            config=dict(number_of_images=1, aspect_ratio="2:3")
        )
        
        poster_url = image_result.generated_images[0].image.url 
        
        # AŞAMA 3: TELEGRAM'A BİLGİ VE BUTON GÖNDERME
        
        caption_text = (
            f"🎬 **{movie_title}**\n\n"
            f"**Özet:** {summary}\n\n"
            f"**Başlangıç Tarihi:** {start_date}\n"
            f"**Bitiş Tarihi:** {end_date}\n\n"
            "✅ Bilgi Başarıyla Üretildi!"
        )
        
        # Butonu oluştur
        keyboard = [
            [telegram.InlineKeyboardButton("Poster Görselini İndir", url=poster_url)]
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)

        # Metni ve butonu gönder
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption_text,
            reply_markup=reply_markup,
            parse_mode=telegram.constants.ParseMode.MARKDOWN
        )

        
    except APIError as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ API Hatası (Gemini): Hata: {e}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Genel İşlem Hatası: {e}")
        
    finally:
        cleanup_files() 


# --- 4. ANA FONKSİYON VE BAŞLATMA ---

async def start_command(update, context):
    teacher_response = "Ben bir yapay zekayım." 

    await update.message.reply_text(
        f"Merhaba! Öğretmenin sorarsa: {teacher_response}\n\nLütfen bilgi almak istediğiniz bir filmin veya dizinin adını yazın."
    )

async def handle_message(update, context):
    search_query = update.message.text.strip()
    if search_query.startswith('/'):
        return 
        
    await generate_and_process_movie_info(update, context, search_query)


def main():
    if not TELEGRAM_BOT_TOKEN:
        return
        
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Film Bilgi Botu çalışmaya başladı...")
    app.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()
