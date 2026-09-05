import os
import asyncio
import logging
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
        base, _ = os.path.splitext(filename)
        final_filename = base + ".mp4"
        if os.path.exists(final_filename):
            return final_filename
        return filename

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Salom! \n\nMenga **Instagram**, **YouTube**, yoki **TikTok** videosining havolasini yuboring, "
        "men uni sizga yuklab beraman!"
    )

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    status_msg = await message.answer("⏳ Media qidirilmoqda va yuklanmoqda. Iltimos, kuting...")
    url = message.text.strip()

    try:
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(None, download_media, url)

        file_size = os.path.getsize(file_path) / (1024 * 1024)
        if file_size > 50:
            await status_msg.edit_text("❌ Fayl hajmi 50MB dan katta. Telegram yubora olmaydi.")
            os.remove(file_path)
            return

        await status_msg.edit_text("⬆️ Tayyor! Telegram'ga yuklanmoqda...")
        
        video = types.FSInputFile(file_path)
        await message.answer_video(video=video, caption="@Helpdowloads_bot orqali yuklab olindi 🚀")
        
        os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_msg.edit_text("❌ Yuklab olishda xatolik yuz berdi. Havolani tekshirib qaytadan urinib ko'ring.")

async def main():
    print("Bot muvaffaqiyatli ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
