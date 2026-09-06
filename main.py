import asyncio
import logging
import os
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiohttp import web
from google import genai

# Настройки логирования
logging.basicConfig(level=logging.INFO)

# Переменные окружения (Environment Variables)
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Инициализация бота и клиента Gemini
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- ФИКС ДЛЯ RENDER PORT SERVER ---
async def handle(request):
    return web.Response(text="Бот успешно работает!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Порт-сервер запущен на порту {port}.")

# --- ОБРАБОТЧИКИ (HANDLERS) ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    welcome_text = (
        "<b>Здравствуйте! Я ваш многофункциональный AI-помощник.</b>\n\n"
        "✨ <b>Возможности:</b>\n"
        "• Чат с ИИ (Google Gemini)\n"
        "• Генерация картинок: <code>/image &lt;описание картинки&gt;</code>\n\n"
        "Просто отправьте мне ваш вопрос!"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

# Генерация картинок (/image команда)
@dp.message(Command("image"))
async def image_handler(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("⚠️ Пожалуйста, введите описание картинки. Например: <code>/image space sunset</code>", parse_mode=ParseMode.HTML)
        return

    await message.answer("🎨 Картинка создается, подождите...")
    
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Результат:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Image Error: {e}")
        await message.answer("❌ Ошибка при создании картинки. Попробуйте еще раз.")

# Чат с ИИ (Google Gemini API - Быстро и стабильно)
@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message.text,
        )
        await message.answer(response.text)
    except Exception as e:
        logging.error(f"Gemini AI error: {e}")
        await message.answer(f"⚠️ **Ошибка ИИ:**\n<code>{e}</code>", parse_mode=ParseMode.HTML)

# --- ЗАПУСК БОТА ---
async def main():
    await start_dummy_server()
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
