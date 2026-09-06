import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import aiohttp

# Logging sozlamasi
logging.basicConfig(level=logging.INFO)

# API Kalitlar
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Groq API kalit to'g'ridan-to'g'ri biriktirildi
GROQ_API_KEY = "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"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Groq AI orqali matnli javob olish funksiyasi
async def fetch_groq_ai(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY sozlanmagan!"
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "system",
                "content": "Siz aqlli, xushmuomala va har qanday savolga aniq javob beradigan Telegram AI yordamchisiz. Javoblarni o'zbek tilida, tushunarli va chiroyli formatda bering."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data['choices'][0]['message']['content']
                else:
                    err_text = await resp.text()
                    logging.error(f"Groq API Error: {resp.status} - {err_text}")
                    return "⚠️ AI serverida vaqtinchalik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."
    except Exception as e:
        logging.error(f"Groq Request Exception: {e}")
        return "⚠️ AI serveriga ulanishda xatolik yuz berdi."

# /start komandasi
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
    await message.answer(welcome_text)

# /image komandasi
@dp.message(Command("image"))
async def generate_image_cmd(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("⚠️ Iltimos, rasm tavsifini kiriting.\n<i>Masalan: /image kosmosdagi shahar</i>")
        return

    msg = await message.answer("🎨 Rasm tayyorlanmoqda, iltimos kuting...")
    
    image_url = f"https://pollinations.ai/p/{prompt.replace(' ', '%20')}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"✨ <b>Rasm tavsifi:</b> {prompt}")
        await msg.delete()
    except Exception as e:
        await msg.edit_text("⚠️ Rasm yaratishda xatolik yuz berdi. Qaytadan urinib ko'ring.")

# Oddiy matnli xabarlar (AI Chat)
@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    # Agar xabar havola (URL) bo'lsa, media yuklovchi qismga o'tishi uchun tekshiruv
    if message.text.startswith("http://") or message.text.startswith("https://"):
        await message.answer("📥 Media yuklash servisi hozircha o'rnatilmoqda...")
        return

    # Typing indikatori
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    # Groq AI ga so'rov yuborish
    response = await fetch_groq_ai(message.text)
    await message.answer(response)

async def main():
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
