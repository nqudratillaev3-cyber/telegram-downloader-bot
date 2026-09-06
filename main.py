import os
import re
import urllib.parse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, URLInputFile
from aiohttp import web
import yt_dlp
from google import genai

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ai_client = genai.Client(api_key=GEMINI_API_KEY)

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    welcome_text = (
        "<b>Salom! Men ko'p funksiyali AI va Downloader botman!</b> 🤖🚀\n\n"
        "<b>Imkoniyatlarim:</b>\n"
        "1. 📥 <b>Media yuklash:</b> Instagram, TikTok yoki YouTube havolasini yuboring.\n"
        "2. 💬 <b>AI Chat:</b> Har qanday savolingizni matn ko'rinishida yozing.\n"
        "3. 🎨 <b>Rasm generatsiya:</b> <code>/image rasm matni</code> deb yuboring.\n"
        "<i>Masalan: /image kosmosda uchayotgan futuristik avtomobil</i>"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@dp.message(Command("image"))
async def generate_image(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("Iltimos, rasmni tasvirlab bering.\nMasalan: <code>/image tog' ustidagi zamonaviy shahar</code>", parse_mode="HTML")
        return

    status_msg = await message.answer("🎨 Rasm chizilmoqda, kuting...")
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42&model=flux"
        photo = URLInputFile(image_url)
        
        await message.answer_photo(photo, caption=f"✨ <b>So'rov:</b> {prompt}", parse_mode="HTML")
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Rasm yaratishda xatolik yuz berdi: {e}")

@dp.message(F.text.contains("instagram.com") | F.text.contains("tiktok.com") | F.text.contains("youtu.be") | F.text.contains("youtube.com"))
async def download_media(message: types.Message):
    url = message.text.strip()
    status_msg = await message.answer("⏳ Media yuklanmoqda, kuting...")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        video = FSInputFile(filename)
        await message.answer_video(video)
        await status_msg.delete()

        if os.path.exists(filename):
            os.remove(filename)
    except Exception as e:
        await status_msg.edit_text("❌ Mediani yuklab bo'lmadi. Havola to'g'riligini tekshiring.")

@dp.message(F.text)
async def ai_chat(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    try:
        response = ai_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=message.text,
        )
        await message.answer(response.text)
    except Exception as e:
        await message.answer(f"🤖 Xatolik yuz berdi: {e}")

async def handle(request):
    return web.Response(text="Bot runs 24/7 autonomously!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
