import asyncio
import logging
import os
import io
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from groq import Groq

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Direct credentials (Environment variable xatolarini oldini olish uchun)
BOT_TOKEN = "8201911449:AAEkpCTEJc9aki4mxTLpDh4DU0A02rnNfcI"
GROQ_API_KEY = "gsk_..." # O'zingizning Groq API kalitingizni shu yerda saqlang

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Groq mijozini sozlash (agar API key mavjud bo'lsa)
try:
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    logging.error(f"Groq initialization error: {e}")
    groq_client = None

# /start komandasi
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    await message.answer(
        "Salom! Men sizning ko'p funksiyali AI yordamchingizman.\n\n"
        "✨ **Imkoniyatlar:**\n"
        "• AI bilan muloqot (Llama 3.3 70B)\n"
        "• Rasm generatsiya qilish: `/image <tasvir tavsifi>`\n\n"
        "Manga shunchaki savolingizni yuboring!"
    )

# /image komandasi - Pollinations AI orqali rasm yaratish
@dp.message(Command("image"))
async def generate_image(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("Iltimos, rasm tavsifini kiriting. Masalan: `/image kosmosdagi oltin mashina`")
        return

    msg = await message.answer("🎨 Rasm chizilmoqda, biroz kuting...")
    
    try:
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        
        await message.answer_photo(photo=image_url, caption=f"🖼 **Natija:** {prompt}")
        await msg.delete()
    except Exception as e:
        logging.error(f"Image generation error: {e}")
        await msg.edit_text("❌ Rasm yaratishda xatolik yuz berdi. Qayta urinib ko'ring.")

# Oddiy matnli xabarlar uchun Groq AI javobi
@dp.message(F.text)
async def ai_chat(message: types.Message):
    if not groq_client:
        await message.answer(" Groq AI kaliti sozlanmagan.")
        return

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Siz foydali, aqlli va xushfe'l Telegram AI yordamchisiz. O'zbek tilida aniq va ravon javob bering."},
                {"role": "user", "content": message.text}
            ],
            temperature=0.7,
            max_tokens=2048,
        )
        response_text = completion.choices[0].message.content
        await message.answer(response_text)
    except Exception as e:
        logging.error(f"Groq AI error: {e}")
        await message.answer("🤖 AI javob qaytarishda xatolik yuz berdi.")

async def main():
    logging.info("Bot ishga tushmoqda...")
    # Eski update'larni o'chirish (so'rovlar to'silib qolmasligi uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
