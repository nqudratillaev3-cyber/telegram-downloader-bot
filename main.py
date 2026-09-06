import os
import urllib.parse
import asyncio
import io
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from google import genai

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Bot va Client obyektlari
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)


# /start va /help buyruqlari
@dp.message(Command("start"))
@dp.message(Command("help"))
async def send_welcome(message: types.Message):
    welcome_text = (
        "Salom! Men ko'p funksiyali AI va Downloader botman! 🤖🚀\n\n"
        "Imkoniyatlarim:\n"
        "1. 📥 <b>Media yuklash:</b> Instagram, TikTok yoki YouTube havolasini yuboring.\n"
        "2. 💬 <b>AI Chat:</b> Har qanday savolingizni matn ko'rinishida yozing.\n"
        "3. 🎨 <b>Rasm generatsiya:</b> <code>/image rasm matni</code> deb yuboring.\n"
        "<i>Masalan: /image kosmosda uchayotgan futuristik avtomobil</i>"
    )
    await message.answer(welcome_text, parse_mode="HTML")


# Rasmni Pollinations API'dan xavfsiz yuklab olish funksiyasi
async def fetch_image_bytes(prompt: str):
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://pollinations.ai/p/{encoded_prompt}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=30) as response:
            if response.status == 200:
                return await response.read()
    return None


# Rasm generatsiyasi (/image buyrug'i)
@dp.message(Command("image"))
async def generate_image_cmd(message: types.Message):
    prompt = message.text.replace("/image", "").strip()

    if not prompt:
        await message.answer("Iltimos, rasm tavsifini kiriting. Masalan:\n<code>/image futuristik shahar</code>", parse_mode="HTML")
        return

    msg_processing = await message.answer("🎨 Rasm yaratilmoqda, kuting...")

    try:
        image_bytes = await fetch_image_bytes(prompt)
        
        if image_bytes:
            # Bytes faylini Telegram tayyor ushlaydigan obyektga o'tkazish
            photo_file = BufferedInputFile(image_bytes, filename="generated_image.jpg")
            await message.answer_photo(photo=photo_file, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode="HTML")
            await msg_processing.delete()
        else:
            await message.answer("❌ Rasm yaratishda xatolik: Serverdan javob olib bo'lmadi.")
            await msg_processing.delete()

    except Exception as e:
        await message.answer(f"❌ Rasm yuklashda kutilmagan xatolik: {e}")
        try:
            await msg_processing.delete()
        except:
            pass


# Gemini API so'rovi (Limit va xatoliklar ushlab qolinadi)
def generate_ai_response(prompt_text: str):
    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    last_error = None

    for model_name in models:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt_text,
            )
            return response.text
        except Exception as e:
            last_error = e
            continue
            
    raise last_error


# AI Chat ishlovchisi
@dp.message()
async def ai_chat(message: types.Message):
    if message.text and (message.text.startswith("http") or "://" in message.text):
        return
        
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        reply_text = generate_ai_response(message.text)
        await message.answer(reply_text)
    except Exception as e:
        err_str = str(e).upper()
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "QUOTA" in err_str:
            await message.answer("⚠️ API limiti to'lib qoldi. Iltimos, 1 daqiqadan so'ng qayta urining.")
        elif "503" in err_str or "UNAVAILABLE" in err_str:
            await message.answer("🤖 AI serverlarida vaqtinchalik juda yuqori yuklama mavjud. Bir ozdan so'ng qayta urining.")
        else:
            await message.answer("🤖 AI javob berishda vaqtinchalik xatolik yuz berdi. Iltimos, keyinroq qayta urining.")


# Health Check web serveri
async def handle(request):
    return web.Response(text="Bot runs 24/7 autonomously!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# Asosiy ishga tushirish
async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
