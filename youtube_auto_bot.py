import os
import requests
import json
import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from google import genai
from google.genai.errors import APIError

# Hata kaynağını denemek için MoviePy geri eklendi!
from moviepy.editor import ImageClip, TextClip, CompositeVideoClip, AudioFileClip, ColorClip 

# --- 1. AYARLAR VE API İSTEMCİLERİ ---

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

try:
    client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    client = None

TEXT_MODEL = "gemini-2.5-flash" 
IMAGE_MODEL = "imagen-2.0-generate-002"
TEMP_DURATION = 20 

# --- 2. YARDIMCI İŞLEVLER ---

def download_image(image_url, save_path="temp_image.png"):
    """Görsel üretim devre dışı olduğu için çağrılmaz."""
    return None

def cleanup_files(*files):
    """İşlem bitince geçici dosyaları siler."""
    for f in files:
        if f and os.path.exists(f):
            os.remove(f)

# --- 3. VİDEO MONTAJ İŞLEVİ (GERÇEK KOD) ---

def create_final_video(image_path, script_text, title):
    """Sadece metin ve siyah arka plan kullanarak video oluşturur."""
    
    # 1. Klibin arka planını oluştur (Siyah ekran)
    clip_duration = TEMP_DURATION 
    final_clip = ColorClip(size=(1280, 720), color=[0, 0, 0], duration=clip_duration)
    
    # 2. Metin Klibini oluştur (Senaryo)
    text_clip = TextClip(
        script_text, 
        fontsize=40, 
        color='white', 
        size=(1200, 600), 
        align='center',
        bg_color='transparent'
    )
    
    # Metin klibini ortala ve video süresi kadar ayarla
    text_clip = text_clip.set_duration(clip_duration).set_pos('center')
    
    # 3. Klipleri birleştir
    final_video = CompositeVideoClip([final_clip, text_clip])
    
    output_path = "final_video.mp4"
    
    # 4. Video dosyasını yaz
    final_video.write_videofile(
        output_path, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac', 
        temp_audiofile='temp-audio.m4a', 
        remove_temp=True
    )
    
    return output_path

# --- 4. TELEGRAM İŞLEYİCİSİ (ANA İŞ AKIŞI) ---

async def generate_and_process_video(update, context, video_idea):
    
    if not client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ HATA: Gemini API Anahtarı eksik veya geçersiz.")
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

        # AŞAMA 1.5: GÖRSEL ÜRETİMİ VE İNDİRME - HATA KAYNAĞI ATLANDI.
        await context.bot.send_message(chat_id=chat_id, text="🚫 Görsel oluşturma adımı (API Hatası kaynağı) ATLANDI.")
        temp_image_path = None 

        # AŞAMA 2: VİDEO MONTAJI (MoviePy çalışıyor olmalı)
        await context.bot.send_message(chat_id=chat_id, text="🎬 VİDEO MONTAJI BAŞLADI (Siyah ekran üzerine metin)...")
        temp_video_path = create_final_video(temp_image_path, script, youtube_title)

        # AŞAMA 3: TELEGRAM'A VİDEO GÖNDERME
        await context.bot.send_message(chat_id=chat_id, text="✅ Video İçeriği Hazırlandı! Telegram üzerinden video gönderiliyor...")
        
        # Video dosyasını Telegram'a gönder
        with open(temp_video_path, 'rb') as video_file:
            await context.bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption=f"🎥 **{youtube_title}**",
                parse_mode=telegram.constants.ParseMode.MARKDOWN
            )
        
    except APIError as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ API Hatası (Gemini): Hata: {e}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Genel İşlem Hatası (MoviePy kurulumunu kontrol edin): {e}")
        
    finally:
        cleanup_files(temp_image_path, temp_video_path) 


# --- 5. ANA FONKSİYON VE BAŞLATMA ---

async def start_command(update, context):
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
