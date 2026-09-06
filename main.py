import asyncio
import logging
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiohttp import web
from google import genai

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Environment variables (Atrof-muhit o'zgaruvchilari)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Bot va Gemini Client obyektlari
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

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

# --- HANDLERLAR (OBRABOTCHIKLAR) ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    welcome_text = (
        "<b>Salom! Men sizning ko'p tilli AI yordamchingizman.</b>\n"
        "<b>Здравствуйте! Я ваш многоязычный AI-помощник.</b>\n"
        "<b>Hello! I am your multilingual AI assistant.</b>\n\n"
        "✨ <b>Imkoniyatlar / Capabilities:</b>\n"
        "• AI Chat (O'zbekcha, Русский, English)\n"
        "• Rasm generatsiyasi / Image generation: <code>/image &lt;prompt&gt;</code>\n\n"
        "Menga istalgan tilda xabar yuboring!"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

# Rasm generatsiyasi (/image buyrug'i)
@dp.message(Command("image"))
async def image_handler(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer(
            "⚠️ Iltimos, rasm tavsifini kiriting / Пожалуйста, введите описание / Please enter an image description:\n"
            "Masalan: <code>/image space sunset</code>", 
            parse_mode=ParseMode.HTML
        )
        return

    await message.answer("🎨 Rasm tayyorlanmoqda... / Создается картинка... / Generating image...")
    
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija / Result:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Image Error: {e}")
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi / Ошибка при создании картинки / Image generation error.")

# AI Matn Chat (Google Gemini API - Uch tilli qo'llab-quvvatlash)
@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    system_instruction = (
        "You are a helpful, intelligent, and polite AI assistant. "
        "Always respond in the same language the user speaks to you (Uzbek, Russian, or English)."
    )
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_instruction}\n\nUser: {message.text}",
        )
        await message.answer(response.text)
    except Exception as e:
        logging.error(f"Gemini AI error: {e}")
        await message.answer(f"⚠️ **AI Xatosi / Ошибка ИИ / AI Error:**\n<code>{e}</code>", parse_mode=ParseMode.HTML)

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    await start_dummy_server()
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
