import asyncio
import logging
import os
import re
import urllib.parse
import traceback
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from google import genai
from google.genai import types as genai_types
import anthropic
import github
from github import Github
import yt_dlp

logging.basicConfig(level=logging.INFO)

# --- ENVIRONMENT VARIABLES ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# AI Clientlarni sozlash
ai_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY) if CLAUDE_API_KEY else None

# --- BAZA (SQLITE) STATISTIKA VA MODEL SOZLAMALARI ---
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        selected_model TEXT DEFAULT 'gemini'
    )
""")
conn.commit()

def add_user(user_id: int):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, selected_model) VALUES (?, 'gemini')", (user_id,))
    conn.commit()

def set_user_model(user_id: int, model_name: str):
    add_user(user_id)
    cursor.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model_name, user_id))
    conn.commit()

def get_user_model(user_id: int) -> str:
    cursor.execute("SELECT selected_model FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row and row[0] else "gemini"

def get_total_users():
    cursor.execute("SELECT COUNT(*) FROM users")
    return cursor.fetchone()[0]

def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    return [row[0] for row in cursor.fetchall()]

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

# --- CLAUDE VA GEMINI CHAT FUNKSIYASI ---
async def generate_ai_response(user_id: int, prompt: str) -> str:
    selected_model = get_user_model(user_id)
    system_prompt = "You are a helpful AI assistant. Always reply in the user's language (Uzbek, Russian, or English)."

    if "claude" in selected_model and claude_client:
        try:
            model_name = "claude-sonnet-5" if selected_model == "claude-sonnet" else "claude-haiku-4-5-20251001"
            response = claude_client.messages.create(
                model=model_name,
                max_tokens=1500,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logging.error(f"Claude Error: {e}. Fallback to Gemini.")

    if ai_client:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"{system_prompt}\n\nUser: {prompt}"
        )
        return response.text
    
    return "❌ AI xizmatida vaqtincha xatolik yuz berdi."

# --- AUTO-HEALING ENGINE (CLAUDE SONNET) ---
async def auto_fix_and_push(error_message: str):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False

    err_str = str(error_message).upper()
    if any(k in err_str for k in ["RESOURCE_EXHAUSTED", "429", "503", "UNAVAILABLE", "404", "QUOTA"]):
        return False

    try:
        g = Github(auth=github.Auth.Token(GITHUB_TOKEN)) if hasattr(github, 'Auth') else Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        contents = repo.get_contents("main.py")
        current_code = contents.decoded_content.decode("utf-8")

        prompt = (
            f"You are an expert Python developer. Fix this code error in an aiogram 3 bot:\n\n"
            f"ERROR:\n{error_message}\n\n"
            f"CODE:\n{current_code}\n\n"
            f"Return ONLY valid raw Python code without markdown blocks or explanations."
        )

        if claude_client:
            res = claude_client.messages.create(
                model="claude-sonnet-5",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            fixed_code = res.content[0].text.strip()
        elif ai_client:
            res = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            fixed_code = res.text.strip()
        else:
            return False

        if fixed_code.startswith("```python"):
            fixed_code = fixed_code.replace("
