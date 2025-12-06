import os
import json
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google import genai
from google.genai.errors import APIError

# TARTIŞMA SONU: Video/Görsel Modülleri ve Kodları TAMAMEN KALDIRILDI.
# Artık sadece metin üreteceğiz.

# --- 1. AYARLAR VE API İSTEMCİLERİ ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    client = None

TEXT_MODEL = "gemini-2.5-flash" 
TEMP_DURATION = 20 

# --- 2. YARDIMCI İŞLEVLER ---

def cleanup_files(*files):
    """İşlem bitince geçici dosyaları siler."""
    pass 

# --- 3. TELEGRAM İŞLEYİCİSİ (ANA İŞ AKIŞI) ---

async def generate_and_process_video(update, context, video_idea):
    
    if not client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ HATA: Gemini API Anahtarı eksik veya geçersiz.")
        return
        
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=f"🤖 Fikir alındı: '{video_idea}'. Başlıyorum...")

    try:
        # AŞAMA 1: SENARYO VE BAŞLIK ÜRETİMİ (Gemini)
        await context.bot.send_message(chat_id=chat_id, text="📝 Senaryo ve başlıklar üretiliyor...")
        
        system_instruction = ("Tüm çıktılarını aşağıdaki formatta, SADECE JSON olarak ver. Ek metin EKLEME.")
        prompt = f"Video fikri: {video_idea}"
        
        response = client.chats.create(
            model=TEXT_MODEL,
            config={
                "systemInstruction": system_instruction, 
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT", "properties": {
                        "script": {"type": "STRING", "description": f"{TEMP_DURATION} saniyelik Türkçe konuşma metni."},
                        "youtube_title": {"type": "STRING", "description": "YouTube videosu için ilgi çekici Türkçe başlık."}
                    }
                }
            }
        ).send_message(message=prompt)

        # HATA KORUMASI
        if not response.text:
            await context.bot.send_message(chat_id=chat_id, text="❌ Gemini'dan boş veya engellenmiş cevap geldi. Lütfen daha güvenli bir fikir deneyin.")
            return

        data = json.loads(response.text)
        script, youtube_title = data["script"], data["youtube_title"]

        # AŞAMA 2: TELEGRAM'A BİLDİRİM GÖNDERME (Sadece Metin)
        await context.bot.send_message(chat_id=chat_id, text="✅ İçerik Hazırlandı! Sonuç bildiriliyor...")
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎥 **{youtube_title}**\n\n**Senaryo:** {script}\n\n✅ BOT BAŞARIYLA ÇALIŞIYOR. (Video özelliği teknik kısıtlamalar nedeniyle devre dışı bırakıldı.)",
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
