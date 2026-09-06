import asyncio
import logging
import os
import re
import urllib.parse
import traceback
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from google import genai
from google.genai import types as genai_types
import github
from github import Github
import yt_dlp

logging.basicConfig(level=logging.INFO)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- BAZA (SQLITE) STATISTIKA UCHUN ---
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY
    )
""")
conn.commit()

def add_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def get_total_users():
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

# --- PORT SERVER ---
async def handle(request):
    return web.Response(text="Bot ishlamoqda!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- AUTO-HEALING ENGINE ---
async def auto_fix_and_push(error_message: str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False

    err_str = str(error_message).upper()
    if any(k in err_str for k in ["RESOURCE_EXHAUSTED", "429", "503", "UNAVAILABLE", "404", "QUOTA"]):
        return False

    try:
        g = Github(auth=github.Auth.Token(GITHUB_TOKEN)) if hasattr(github, 'Auth') else Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        contents = repo.get_contents("main.py")
        current_code = contents.decoded_content.decode("utf-8")

        prompt = (
            f"You are an expert Python developer. Fix this code error:\n\n"
            f"ERROR:\n{error_message}\n\n"
            f"CODE:\n{current_code}\n\n"
            f"Return ONLY raw Python code without markdown."
        )

        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        
        fixed_code = response.text.strip()
        if fixed_code.startswith("```python"):
            fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()

        repo.update_file(
            path=contents.path,
            message="🤖 Auto-Fix: Bot o'zidagi xatoni avtomatik tuzatdi",
            content=fixed_code,
            sha=contents.sha
        )
        return True
    except Exception as e:
        logging.error(f"Auto-Fix error: {e}")
        return False

# --- YUKLAB OLISH FUNKSIYALARI ---
def download_media(url: str, is_audio: bool = False, output_path: str = "downloaded_file"):
    common_opts = {
        'quiet': True,
        'no_warnings': True,
        'max_filesize': 50 * 1024 * 1024,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    
    if is_audio:
        ydl_opts = {
            **common_opts,
            'format': 'bestaudio/best',
            'outtmpl': f"{output_path}.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
    else:
        ydl_opts = {
            **common_opts,
            'format': 'best[ext=mp4]/best',
            'outtmpl': f"{output_path}.mp4",
        }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    return f"{output_path}.mp3" if is_audio else f"{output_path}.mp4"

# QOSHIK QIDIRISH FUNKSIYASI
def search_youtube_music(query: str, limit: int = 5):
    ydl_opts = {
        'default_search': 'ytsearch',
        'quiet': True,
        'extract_flat': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        results = []
        if info and 'entries' in info:
            for entry in info['entries']:
                if entry:
                    results.append({
                        'title': entry.get('title', 'Noma\'lum qo\'shiq'),
                        'url': entry.get('url', f"[https://www.youtube.com/watch?v=](https://www.youtube.com/watch?v=){entry.get('id')}"),
                        'id': entry.get('id')
                    })
        return results

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    add_user(message.from_user.id)
    welcome_text = (
        "<b>Salom! Men sizning ko'p funktsiyali AI yordamchingiz va Downloader botingizman.</b>\n\n"
        "✨ <b>Imkoniyatlar:</b>\n"
        "• 🎧 Qo'shiq izlash: <code>/music &lt;nomi&gt;</code>\n"
        "• 🎥 Video / 🎵 MP3 yuklash (YouTube, Instagram, TikTok havolasi)\n"
        "• 🎙 Ovozli xabarlarni tushunish va AI javobi\n"
        "• 🖼 Rasmlarni tahlil qilish (Vision AI)\n"
        "• 🎨 Rasm generatsiyasi: <code>/image &lt;tavsif&gt;</code>\n"
        "• 💬 AI Chat (O'zbek, Rus, Ingliz tillarida)\n\n"
        "Shunchaki havola, matn, rasm yoki ovozli xabar yuboring!"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

# MUSIQA IZLASH HANDLERI (/music)
@dp.message(Command("music"))
async def music_search_handler(message: types.Message):
    add_user(message.from_user.id)
    query = message.text.replace("/music", "").strip()
    if not query:
        await message.answer("⚠️ Qo'shiq nomini yoki ijrochini kiriting:\nMasalan: <code>/music Janob Rasul</code>", parse_mode=ParseMode.HTML)
        return

    status_msg = await message.answer("🔍 Qo'shiqlar qidirilmoqda...")
    
    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, search_youtube_music, query, 5)
        
        if not results:
            await status_msg.edit_text("❌ Hech qanday qo'shiq topilmadi.")
            return

        buttons = []
        for i, res in enumerate(results, start=1):
            title = res['title'][:35]
            buttons.append([InlineKeyboardButton(text=f"🎵 {i}. {title}", callback_data=f"dl_mp3:{res['url']}")])

        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await status_msg.edit_text(f"🎧 <b>'{query}' bo'yicha topilgan qo'shiqlar:</b>\n\nKerakli qo'shiqni tanlang 👇", reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text("❌ Musiqa qidirishda xatolik yuz berdi.")

# ADMIN PANEL & STATISTIKA
@dp.message(Command("stats"))
async def stats_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = get_total_users()
    await message.answer(f"📊 <b>Bot Statistikasi:</b>\n\n👥 Jami foydalanuvchilar: <b>{total}</b> ta", parse_mode=ParseMode.HTML)

@dp.message(Command("send"))
async def broadcast_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text_to_send = message.text.replace("/send", "").strip()
    if not text_to_send:
        await message.answer("⚠️ Yuboriladigan matnni kiriting: <code>/send Salom hammaga!</code>", parse_mode=ParseMode.HTML)
        return

    users = get_all_users()
    count = 0
    await message.answer(f"📢 {len(users)} ta foydalanuvchiga xabar yuborilmoqda...")
    
    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=text_to_send)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await message.answer(f"✅ Xabar {count} ta foydalanuvchiga muvaffaqiyatli yetkazildi!")

# RASM GENERATSIYASI
@dp.message(Command("image"))
async def image_handler(message: types.Message):
    add_user(message.from_user.id)
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("⚠️ Tavsif kiriting: <code>/image space sunset</code>", parse_mode=ParseMode.HTML)
        return

    await message.answer("🎨 Rasm tayyorlanmoqda...")
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"[https://pollinations.ai/p/](https://pollinations.ai/p/){encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi.")

# YOUTUBE / MEDIA MP3 CALLBACK
@dp.callback_query(F.data.startswith("dl_mp3:"))
async def callback_dl_mp3(callback: types.CallbackQuery):
    url = callback.data.split("dl_mp3:", 1)[1]
    await callback.message.answer("🎵 MP3 audio yuklanmoqda, biroz kuting...")
    
    file_prefix = f"audio_{callback.from_user.id}"
    try:
        loop = asyncio.get_event_loop()
        final_file = await loop.run_in_executor(None, download_media, url, True, file_prefix)
        
        audio = FSInputFile(final_file)
        await callback.message.answer_audio(audio=audio, caption="✅ Audio tayyor!")
        
        if os.path.exists(final_file):
            os.remove(final_file)
    except Exception as e:
        await callback.message.answer("❌ MP3 audio yuklab olishda xatolik yuz berdi.")

# VISION AI (RASMLARNI TAHLIL QILISH)
@dp.message(F.photo)
async def photo_analysis_handler(message: types.Message):
    add_user(message.from_user.id)
    status_msg = await message.answer("🔍 Rasm tahlil qilinmoqda...")
    
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_path = f"photo_{message.from_user.id}.jpg"
    await bot.download_file(file.file_path, file_path)

    caption = message.caption if message.caption else "Rasmni batafsil tahlil qilib, tushuntirib ber."

    try:
        with open(file_path, "rb") as img_file:
            img_bytes = img_file.read()

        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[
                genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                f"You are a helpful AI assistant. Always reply in the user's language. Prompt: {caption}"
            ]
        )
        await status_msg.edit_text(response.text)
    except Exception as e:
        await status_msg.edit_text("❌ Rasmni tahlil qilishda xatolik yuz berdi.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# VOICE MESSAGE TO TEXT / AI (OVOZLI XABARLAR)
@dp.message(F.voice)
async def voice_handler(message: types.Message):
    add_user(message.from_user.id)
    status_msg = await message.answer("🎙 Ovoz tinglanmoqda va tahlil qilinmoqda...")
    
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = f"voice_{message.from_user.id}.ogg"
    await bot.download_file(file.file_path, file_path)

    try:
        with open(file_path, "rb") as audio_file:
            audio_bytes = audio_file.read()

        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=[
                genai_types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                "Listen to this audio carefully and answer the question/request in the same language."
            ]
        )
        await status_msg.edit_text(f"🎙 <b>Sizning ovozingizga AI javobi:</b>\n\n{response.text}", parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.edit_text("❌ Ovozni qayta ishlashda xatolik yuz berdi.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# MATN VA HAVOLALAR HANDLERI
@dp.message(F.text)
async def main_handler(message: types.Message):
    add_user(message.from_user.id)
    text = message.text.strip()
    
    url_pattern = re.compile(r'https?://[^\s]+')
    urls = url_pattern.findall(text)

    # Havola bo'lsa (Downloader + MP3 tugmasi)
    if urls:
        url = urls[0]
        status_msg = await message.answer("📥 Video yuklanmoqda, biroz kuting...")
        file_prefix = f"video_{message.from_user.id}"
        
        try:
            loop = asyncio.get_event_loop()
            final_file = await loop.run_in_executor(None, download_media, url, False, file_prefix)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎵 MP3 formatda yuklash", callback_data=f"dl_mp3:{url}")]
            ])
            
            video = FSInputFile(final_file)
            await message.answer_video(video=video, caption="✅ Videongiz tayyor!", reply_markup=kb)
            await status_msg.delete()
            
            if os.path.exists(final_file):
                os.remove(final_file)
            return
        except Exception:
            if os.path.exists(f"{file_prefix}.mp4"):
                os.remove(f"{file_prefix}.mp4")
            await status_msg.edit_text("❌ Ushbu havoladan videoni yuklab bo'lmadi yoki fayl hajmi juda katta (50MB+).")
            return

    # AI Chat
    system_instruction = "You are a helpful AI assistant. Always reply in the user's language (Uzbek, Russian, or English)."
    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=f"{system_instruction}\n\nUser: {text}",
        )
        await message.answer(response.text)
    except Exception as e:
        error_trace = traceback.format_exc()
        logging.error(f"Chat error: {error_trace}")
        
        full_err_text = f"{str(e)} {repr(e)} {error_trace}".upper()
        
        if any(keyword in full_err_text for keyword in ["429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "QUOTA", "RATE_LIMIT"]):
            await message.answer("⏳ Serverlarda yuklama yuqori. 1 daqiqadan so'ng qayta urinib ko'ring.")
            return

        status_msg = await message.answer("⚠️ Botda koddagi xatolik aniqlandi. Auto-Fix ishga tushdi...")
        fixed = await auto_fix_and_push(error_trace)
        
        if fixed:
            await status_msg.edit_text("🔄 Kod avtomatik tuzatildi va GitHub'ga saqlandi!")
        else:
            await status_msg.edit_text("⚠️ Serverda vaqtincha xatolik. Birozdan so'ng urinib ko'ring.")

async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
