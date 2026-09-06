import os
import urllib.parse
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile

# Environment Variables
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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


# Rasmni yuklab olish funksiyasi (Pollinations Image)
async def fetch_image_bytes(prompt: str):
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=800&height=800&nologo=true"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=40) as response:
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
            photo_file = BufferedInputFile(image_bytes, filename="generated_image.jpg")
            await message.answer_photo(photo=photo_file, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode="HTML")
            await msg_processing.delete()
        else:
            await message.answer("❌ Rasm serveridan javob olib bo'lmadi. Keyinroq qayta urining.")
            await msg_processing.delete()

    except Exception:
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi.")
        try:
            await msg_processing.delete()
        except Exception:
            pass


# Rasmiy va o'ta tezkor Groq AI Chat API
async def fetch_groq_ai(prompt_text: str):
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY Render Environment Variables ga qo'shilmagan!"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt_text}],
        "temperature": 0.7
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
    return None


# AI Chat ishlovchisi
@dp.message()
async def ai_chat(message: types.Message):
    if message.text and (message.text.startswith("http") or "://" in message.text):
        return
        
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        reply_text = await fetch_groq_ai(message.text)
        if reply_text:
            await message.answer(reply_text)
        else:
            await message.answer("⚠️ AI serverida vaqtinchalik xatolik yuz berdi.")
    except Exception:
        await message.answer("⚠️ Xatolik yuz berdi, iltimos qaytadan yozib ko'ring.")


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
