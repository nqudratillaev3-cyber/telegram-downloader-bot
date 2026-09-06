import asyncio
import logging
import os
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiohttp import web
from groq import Groq

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Environment variables (Muhit o'zgaruvchilari)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Bot va Groq klientlarini retsializatsiya qilish
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
groq_client = Groq(api_key=GROQ_API_KEY)

# --- RENDER PORT SCAN FIX (PORT SERVER) ---
async def handle(request):
    return web.Response(text="Bot barqaror ishlamoqda!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Port server {port}-portda ishga tushdi.")

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    welcome_text = (
        "<b>Salom! Men sizning ko'p funksiyali AI yordamchingizman.</b>\n\n"
        "✨ <b>Imkoniyatlar:</b>\n"
        "• AI bilan muloqot (Llama 3.3 70B)\n"
        "• Rasm generatsiya qilish: <code>/image &lt;tasvir tavsifi&gt;</code>\n\n"
        "Manga shunchaki savolingizni yuboring!"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

# Rasm generatsiyasi (/image buyrug'i)
@dp.message(Command("image"))
async def image_handler(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("⚠️ Iltimos, rasm tavsifini kiriting. Masalan: <code>/image space sunset</code>", parse_mode=ParseMode.HTML)
        return

    await message.answer("🎨 Rasm tayyorlanmoqda, kuting...")
    
    # Pollinations AI integratsiyasi
    encoded_prompt = httpx.URL(prompt).raw_path.decode('utf-8')
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Image Error: {e}")
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

# AI Matn Chat (Groq AI - Llama 3.3)
@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Siz foydali, aqlli va xushmuomala AI yordamchisiz. Foydalanuvchiga aniq va o'zbek tilida javob bering."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        answer = response.choices[0].message.content
        await message.answer(answer)
    except Exception as e:
        logging.error(f"Groq AI error: {e}")
        await message.answer("🤖 AI javob qaytarishda xatolik yuz berdi. API kalit to'g'riligini tekshiring.")

# --- ASOSIY ISHGA TUSHMASH FUNKSIYASI ---
async def main():
    # Render portini ochish (Port Scan Timeout xatosini bartaraf etadi)
    await start_dummy_server()
    
    # Polling boshlash
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
