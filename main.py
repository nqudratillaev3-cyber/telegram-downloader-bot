import asyncio
import logging
import os
import re
import urllib.parse
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import (
    FSInputFile, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
from google import genai
from google.genai import types as genai_types
import yt_dlp

logging.basicConfig(level=logging.INFO)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# FSM holatlari
class BotStates(StatesGroup):
    waiting_for_music = State()
    waiting_for_image = State()

# 100% BEPUL Gemini Client
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
GEMINI_MODEL = "gemini-1.5-flash"

# --- BAZA (SQLITE) STATISTIKA ---
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

# --- ASOSIY REPLUY TUGMALAR (MAIN MENU) ---
def get_main_keyboard(user_id: int):
    buttons = [
        [KeyboardButton(text="🎧 Musiqa Qidirish"), KeyboardButton(text="🎨 Rasm Yaratish (AI Image)")],
        [KeyboardButton(text="ℹ️ Yordam")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="📊 Statistika")])
        
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- PORT SERVER (RENDER UCHUN) ---
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

# --- AI JAVOB GENERATORI (100% BEPUL GEMINI) ---
async def generate_ai_response(user_id: int, prompt: str) -> str:
    system_prompt = "You are a helpful AI assistant. Always reply in the user's language (Uzbek, Russian, or English)."

    if ai_client:
        try:
            response = ai_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=f"{system_prompt}\n\nUser: {prompt}"
            )
            return response.text
        except Exception as e:
            logging.error(f"Gemini Error: {e}")
            return "⚠️ AI serverida xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
    
    return "❌ AI xizmati ulanmagan."

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
                        'url': entry.get('url', f"https://www.youtube.com/watch?v={entry.get('id')}"),
                        'id': entry.get('id')
                    })
        return results

# --- COMMAND VA HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await state.clear()
    add_user(message.from_user.id)
    welcome_text = (
        "<b>Salom! Men sizning ko'p funktsiyali AI yordamchingiz va Downloader botingizman.</b>\n\n"
        "• 📥 <b>Social Media Downloader:</b> Instagram, TikTok yoki YouTube havolasini yuboring.\n"
        "• 💬 <b>AI Chat:</b> Istalgan matn, rasm yoki ovozli xabarga javob beraman.\n\n"
        "Pastdagi tugmalar orqali qo'shimcha imkoniyatlardan foydalaning 👇"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard(message.from_user.id))

@dp.message(F.text == "🎧 Musiqa Qidirish")
async def music_btn_handler(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_music)
    await message.answer("🎵 Qidirmoqchi bo'lgan qo'shigingiz nomini yoki ijrochini kiriting:\n<i>(Masalan: Janob Rasul)</i>", parse_mode=ParseMode.HTML)

@dp.message(BotStates.waiting_for_music)
async def process_music_search(message: types.Message, state: FSMContext):
    await state.clear()
    query = message.text.strip()
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
    except Exception:
        await status_msg.edit_text("❌ Musiqa qidirishda xatolik yuz berdi.")

@dp.message(F.text == "🎨 Rasm Yaratish (AI Image)")
async def image_btn_handler(message: types.Message, state: FSMContext):
    await state.set_state(BotStates.waiting_for_image)
    await message.answer("🖼 Qanday rasm yaratmoqchisiz? Tavsifini kiriting:\n<i>(Masalan: space sunset, cyber city)</i>", parse_mode=ParseMode.HTML)

@dp.message(BotStates.waiting_for_image)
async def process_image_gen(message: types.Message, state: FSMContext):
    await state.clear()
    prompt = message.text.strip()
    await message.answer("🎨 Rasm tayyorlanmoqda...")
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi.")

@dp.message(F.text == "ℹ️ Yordam")
async def help_btn_handler(message: types.Message):
    help_text = (
        "<b>Botdan foydalanish yo'riqnomasi:</b>\n\n"
        "• 💬 <b>AI Chat:</b> Istalgan matnli xabaringizga AI javob beradi.\n"
        "• 🎥 <b>Video yuklash:</b> Instagram, TikTok yoki YouTube havolasini yuboring.\n"
        "• 🎙 <b>Ovozli xabar:</b> Ovozli xabar yuborsangiz, AI uni tushunib javob qaytaradi.\n"
        "• 🖼 <b>Rasm Tahlili:</b> Botingizga rasm yuborsangiz, uni tahlil qilib beradi."
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)

@dp.message(F.text == "📊 Statistika")
async def stats_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = get_total_users()
    await message.answer(f"📊 <b>Bot Statistikasi:</b>\n\n👥 Jami foydalanuvchilar: <b>{total}</b> ta", parse_mode=ParseMode.HTML)

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
    except Exception:
        await callback.message.answer("❌ MP3 audio yuklab olishda xatolik yuz berdi.")

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
            model=GEMINI_MODEL,
            contents=[
                genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                f"You are a helpful AI assistant. Always reply in the user's language. Prompt: {caption}"
            ]
        )
        await status_msg.edit_text(response.text)
    except Exception:
        await status_msg.edit_text("❌ Rasmni tahlil qilishda xatolik yuz berdi.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

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
            model=GEMINI_MODEL,
            contents=[
                genai_types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                "Listen to this audio carefully and answer the question/request in the same language."
            ]
        )
        await status_msg.edit_text(f"🎙 <b>Sizning ovozingizga AI javobi:</b>\n\n{response.text}", parse_mode=ParseMode.HTML)
    except Exception:
        await status_msg.edit_text("❌ Ovozni qayta ishlashda xatolik yuz berdi.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- ASOSIY MATN HANDLERI (MEDIA DOWNLOADING VA AI CHAT) ---
@dp.message(F.text)
async def main_handler(message: types.Message):
    add_user(message.from_user.id)
    text = message.text.strip()
    
    url_pattern = re.compile(r'https?://[^\s]+')
    urls = url_pattern.findall(text)

    # Havola bo'lsa - media yuklab beradi
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

    # Oddiy matn bo'lsa - Gemini AI javob beradi
    try:
        response_text = await generate_ai_response(message.from_user.id, text)
        await message.answer(response_text)
    except Exception as e:
        logging.error(f"Chat error: {e}")
        await message.answer("⚠️ Vaqtincha xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")

async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
