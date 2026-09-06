import asyncio
import logging
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiohttp import web
from groq import AsyncGroq

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Bot va AsyncGroq klientlari
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# --- RENDER PORT SERVER FIX ---
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
        "• AI bilan muloqot\n"
        "• Rasm generatsiya qilish: <code>/image &lt;tasvir tavsifi&gt;</code>\n\n"
        "Menga shunchaki savolingizni yuboring!"
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
    
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Image Error: {e}")
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")

# AI Matn Chat (Groq Async AI - Zaxira modellar bilan)
@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
    ]
    
    success = False
    for model_name in models_to_try:
        try:
            response = await groq_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Siz foydali, aqlli va xushmuomala AI yordamchisiz. Foydalanuvchiga aniq va o'zbek tilida javob bering."},
                    {"role": "user", "content": message.text}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            answer = response.choices[0].message.content
            await message.answer(answer)
            success = True
            break
        except Exception as e:
            logging.warning(f"Model {model_name} xatosi: {e}")
            continue

    if not success:
        await message.answer("🤖 Groq API kalitingizda yoki modellarga kirishda xatolik bor. Iltimos, console.groq.com saytidan yangi API kalit oling.")

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    await start_dummy_server()
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
