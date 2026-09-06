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

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

# Bot va Gemini Client
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

# --- ZAHIRALI AI GENERATION ENGINE ---
async def generate_ai_response(prompt_text: str) -> str:
    """Asosiy model limitga tushsa, avtomatik ravishda zahira modelga o'tadi"""
    models_to_try = ['gemini-3.6-flash', 'gemini-1.5-flash']
    
    for model_name in models_to_try:
        try:
            response = ai_client.models.generate_content(
                model=model_name,
                contents=prompt_text,
            )
            return response.text
        except Exception as e:
            logging.warning(f"Model {model_name} xatosi: {e}. Keyingi model sinab ko'rilmoqda...")
            continue
            
    raise Exception("Barcha AI modellar band yoki limitda!")

# --- O'Z-O'ZINI DAVOLASH (AUTO-HEALING) ENGINE ---
async def auto_fix_and_push(error_message: str):
    """Faqat mantiqiy kod xatolari uchun GitHub'ga avtomatik push qiladi"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logging.error("Auto-Fix xatosi: GITHUB_TOKEN yoki GITHUB_REPO sozlanmagan!")
        return False

    # Limit (429) yoki Model (404) xatolarida kodni o'zgartirish mantiqsiz
    if "RESOURCE_EXHAUSTED" in error_message or "429" in error_message or "404" in error_message:
        logging.info("Auto-Fix o'tkazib yuborildi: Bu kod xatosi emas, API limit xatosi.")
        return False

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        contents = repo.get_contents("main.py")
        current_code = contents.decoded_content.decode("utf-8")

        prompt = (
            f"You are an expert Python developer. The following script produced an error:\n\n"
            f"ERROR:\n{error_message}\n\n"
            f"CURRENT CODE:\n{current_code}\n\n"
            f"Please fix the code. Return ONLY the raw valid Python code without markdown code blocks (```python) or explanations."
        )

        # Auto-Fix uchun ham zahirali generator ishlatiladi
        fixed_code = await generate_ai_response(prompt)
        fixed_code = fixed_code.strip()
        
        if fixed_code.startswith("```python"):
            fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()

        repo.update_file(
            path=contents.path,
            message="🤖 Auto-Fix: Bot o'zidagi xatoni avtomatik tuzatdi",
            content=fixed_code,
            sha=contents.sha
        )
        logging.info("Auto-Fix muvaffaqiyatli bajarildi! GitHub'ga yangi kod push qilindi.")
        return True
    except Exception as e:
        logging.error(f"Auto-Fix jarayonida xatolik: {e}")
        return False

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    welcome_text = (
        "<b>Salom! Men sizning ko'p tilli AI yordamchingizman.</b>\n"
        "<b>Здравствуйте! Я ваш многоязычный AI-помощник.</b>\n"
        "<b>Hello! I am your multilingual AI assistant.</b>\n\n"
        "✨ <b>Imkoniyatlar / Capabilities:</b>\n"
        "• AI Chat (O'zbekcha, Русский, English)\n"
        "• Rasm generatsiyasi: <code>/image &lt;prompt&gt;</code>\n\n"
        "Menga istalgan tilda xabar yuboring!"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)

# Rasm generatsiyasi (/image buyrug'i)
@dp.message(Command("image"))
async def image_handler(message: types.Message):
    prompt = message.text.replace("/image", "").strip()
    if not prompt:
        await message.answer("⚠️ Iltimos, rasm tavsifini kiriting. Masalan: <code>/image space sunset</code>", parse_mode=ParseMode.HTML)
        return

    await message.answer("🎨 Rasm tayyorlanmoqda...")
    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://pollinations.ai/p/{encoded_prompt}?width=1024&height=1024&seed=42"
    
    try:
        await message.answer_photo(photo=image_url, caption=f"🖼 <b>Natija:</b> {prompt}", parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Image Error: {e}")
        await message.answer("❌ Rasm yaratishda xatolik yuz berdi.")

# AI Matn Chat (Zahirali va Auto-Healing)
@dp.message(F.text)
async def ai_chat_handler(message: types.Message):
    system_instruction = (
        "You are a helpful, intelligent, and polite AI assistant. "
        "Always respond in the same language the user speaks to you (Uzbek, Russian, or English)."
    )
    
    full_prompt = f"{system_instruction}\n\nUser: {message.text}"
    
    try:
        response_text = await generate_ai_response(full_prompt)
        await message.answer(response_text)
    except Exception as e:
        error_trace = traceback.format_exc()
        logging.error(f"Gemini AI error: {error_trace}")
        
        status_msg = await message.answer("⚠️ Botda kutilmagan koddagi xatolik yuz berdi. Auto-Fix ishga tushmoqda...")
        
        fixed = await auto_fix_and_push(error_trace)
        if fixed:
            await status_msg.edit_text("🔄 Kod avtomatik tuzatildi va GitHub'ga saqlandi! Render 1 daqiqada botni qayta deploy qiladi.")
        else:
            await status_msg.edit_text(f"⚠️ **Xatolik:** Hozirda serverlar band yoki API limitida. Birozdan keyin urinib ko'ring.", parse_mode=ParseMode.HTML)

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    await start_dummy_server()
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
