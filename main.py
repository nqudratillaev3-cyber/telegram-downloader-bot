import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
import yt_dlp

# @Helpdowloads_bot tokeni
BOT_TOKEN = "8201911449:AAG5zn-D9seGtzK2N4RnyALMHCR3nF9jfso"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def download_media(url: str, download_folder: str = "downloads"):
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': f'{download_folder}/%(id)s.%(ext)s',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not filename.endswith('.mp4'):
            filename = os.path.splitext(filename)[0] + '.mp4'
        return filename

@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.answer("Salom! Menga Instagram, TikTok yoki YouTube havolasini yuboring.")

@dp.message(F.text)
async def handle_message(message: types.Message):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("Iltimos, to'g'ri havola yuboring.")
        return

    msg = await message.answer("Video yuklanmoqda, kuting...")
    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, download_media, url)
        
        video_file = types.FSInputFile(file_path)
        await message.answer_video(video_file)
        
        if os.path.exists(file_path):
            os.remove(file_path)
        await msg.delete()
    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await msg.edit_text("Videoni yuklab bo'lmadi. Havolani tekshirib qayta urinib ko'ring.")

async def start_dummy_server():
    async def handle(request):
        return web.Response(text="Bot runs 24/7!")
    
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())