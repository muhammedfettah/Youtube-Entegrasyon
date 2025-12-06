import os
import requests
import json
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google import genai
from google.genai.errors import APIError

# HATA KAYNAKLARI GEÇİCİ OLARAK DEVRE DIŞI BIRAKILDI:
# 1. MoviePy kütüphanesi (Kurulum sorunları nedeniyle)
# from moviepy.editor import ImageClip, TextClip, CompositeVideoClip, AudioFileClip, ColorClip 

# --- 1. AYARLAR VE API İSTEMCİLERİ ---

# Ortam değişkenlerinden okunur
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    client = None

TEXT_MODEL = "gemini-2.5-flash" 
# HATA NEDENİYLE GÖRSEL MODEL TANIMI GEREKSİZ, ancak kodu sade bırakmak için tutulabilir.
IMAGE_MODEL = "imagen-2.0-generate-002" 
TEMP_DURATION = 20 

# --- 2. YARDIMCI İŞLEVLER ---

# Görsel üretim devre dışı olduğu için indirme ve temizlik fonksiyonları basitleştirildi.

def download_image(image_url, save_path="temp_image.png"):
    """Görsel üretim devre dışı olduğu için bu fonksiyon çağrılmayacak."""
    return None

def cleanup_files(*files):
    """İşlem bitince geçici dosyaları siler."""
    for f in files:
        if f and os.path.exists(f):
            os.remove(f)

# --- 3. VİDEO MONTAJ İŞLEVİ (GEÇİCİ YER TUTUCU) ---
def create_final_video(image_path, script_text, title):
    """MoviePy kodu devre dışı olduğu için yer tutucudur."""
    print("--- MoviePy ve Görsel Üretim Atlandı ---")
    return "temp_video_placeholder.mp4" 

# --- 4. TELEGRAM İŞLEYİCİSİ (ANA İŞ AKIŞI) ---

async def generate_and_process_video(update, context, video_idea):
    
    if not client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ HATA: Gemini API Anahtarı eksik veya geçersiz. Lütfen kontrol edin.")
        return
        
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text=f"🤖 Fikir alındı: '{video_idea}'. Başlıyorum...")

    temp_image_path, temp_video_path = None, None

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

        # HATA KORUMASI: Boş (None) cevap gelmesi durumunda botun çökmesini engeller.
        if not response.text:
            await context.bot.send_message(chat_id=chat_id, text="❌ Gemini'dan boş veya engellenmiş cevap geldi. Lütfen daha genel ve güvenli bir fikir deneyin.")
            return

        data = json.loads(response.text)
        image_prompt, script, youtube_title = data["image_prompt"], data["script"], data["youtube_title"]

        # AŞAMA 1.5: GÖRSEL ÜRETİMİ VE İNDİRME - TAMAMEN ATLANDI!
        await context.bot.send_message(chat_id=chat_id, text="🚫 Görsel oluşturma adımı (Hata kaynağı) ATLANDI.")
        temp_image_path = None # Görsel üretilmedi

        # AŞAMA 2: VİDEO MONTAJI (Atlanıyor)
        await context.bot.send_message(chat_id=chat_id, text="🎬 Video montajı adımı şimdilik atlanıyor...")
        temp_video_path = create_final_video(temp_image_path, script, youtube_title)

        # AŞAMA 3: TELEGRAM'A BİLDİRİM GÖNDERME
        await context.bot.send_message(chat_id=chat_id, text="✅ Video İçeriği Hazırlandı! Telegram üzerinden sonuç bildiriliyor...")
        
        # Sadece Metin Gönderme
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🎥 **{youtube_title}**\n\n**Senaryo:** {script[:300]}...\n\n✅ BOT BAŞARIYLA ÇALIŞIYOR. Metin Üretimi Tamamlandı!",
            parse_mode=telegram.constants.ParseMode.MARKDOWN
        )
        
    except APIError as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ API Hatası (Gemini): Anahtarınızı veya model adını kontrol edin. Hata: {e}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Genel İşlem Hatası: {e}")
        
    finally:
        cleanup_files(temp_image_path) 


# --- 5. ANA FONKSİYON VE BAŞLATMA ---

async def start_command(update, context):
    # Kullanıcı bilgisi hatılatması
    teacher_response = "Ben bir yapay zekayım." 

    await update.message.reply_text(
        f"Merhaba! Öğretmenin sorarsa: {teacher_response}\n\nBen Otomatik YouTube İçerik Botuyum. Lütfen bir video fikri yazın."
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
