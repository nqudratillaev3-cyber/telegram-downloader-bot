import asyncio
import logging
import os
import urllib.parse
import traceback
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiohttp import web
from google import genai
from github import Github

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# --- PORT SERVER ---
async def handle(request):
    return web.Response(text="Bot ishlamoqda!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- AUTO-HEALING ENGINE ---
async def auto_fix_and_push(error_message: str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False

    # Limit (429) yoki Model (404) xatolarida GitHub'ga fayl yozmaymiz
    if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message or "404" in error_message:
        return False

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        contents = repo.get_contents("main.py")
        current_code = contents.decoded_content.decode("utf-8")

        prompt = (
            f"You are an expert Python developer. Fix this code error:\n\n"
            f"ERROR:\n{error_message}\n\n"
            f"CODE:\n{current_code}\n\n"
            f"Return ONLY raw Python code without markdown."
        )

        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        
        fixed_code = response.text.strip()
        if fixed_code.startswith("```python"):
            fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()

        repo.update_file(
            path=contents.path,
            message="🤖 Auto-Fix: Bot o'zidagi xatoni avtomatik tuzatdi",
            content=fixed_code,
            sha=contents.sha
        )
        return True
    except Exception as e:
        logging.error(f"Auto-Fix error: {e}")
        return False

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    welcome_text = (
        "<b>Salom! Men sizning ko'p tilli AI yordamchingizman.</b>\n"
        "<b>Здравствуйте! Я ваш многоязычный AI-помощник.</b>\n"
        "<b>Hello! I am your multilingual AI assistant.</b>\n\n"
        "✨ <b>Imkoniyatlar:</b>\n"
        "• AI Chat (O'zbekcha, Русский, English)\n"
        "• Rasm generatsiyasi: <code>/image &lt;prompt&gt;</code>\n\n"
        "Menga istalgan tilda xabar yuboring!"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

@dp.message(Command("image"))
async def image_handler(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("⚠️ Tavsif kiriting: <code>/image space sunset</code>", parse_mode=ParseMode.HTML)
        return

    await message.answer("🎨 Rasm tayyorlanmoqda...")
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"[https://pollinations.ai/p/](https://pollinations.ai/p/){encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi.")

@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    system_instruction = "You are a helpful AI assistant. Always reply in the user's language (Uzbek, Russian, or English)."
    
    try:
        response = ai_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=f"{system_instruction}\n\nUser: {message.text}",
        )
        await message.answer(response.text)
    except Exception as e:
        error_trace = traceback.format_exc()
        
        # Agar limitga tushgan bo'lsa (429), foydalanuvchiga tushunarli xabar beramiz
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            await message.answer("⏳ Bepul API limiti vaqtincha to'ldi. 1-2 daqiqadan so'ng qayta yozib ko'ring.")
            return

        # Kod xatosi bo'lsa, Auto-Fix ishga tushadi
        status_msg = await message.answer("⚠️ Botda koddagi xatolik aniqlandi. Auto-Fix ishga tushdi...")
        fixed = await auto_fix_and_push(error_trace)
        
        if fixed:
            await status_msg.edit_text("🔄 Kod tuzatildi va GitHub'ga saqlandi! Render 1 daqiqada qayta deploy qiladi.")
        else:
            await message.answer("⚠️ Serverda vaqtincha xatolik. Birozdan so'ng urinib ko'ring.")

async def main():
    await start_dummy_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
