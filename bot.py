import os
import glob
import time
import shutil
import sqlite3
import threading
from datetime import datetime, date
from flask import Flask
import telebot
from telebot import types
import yt_dlp
import requests

# 1. Render Port Alive Rakhar Jonno Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# 2. Telegram Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable missing!")

ADMIN_ID = 5140546628  # Apnar Admin ID
bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

# 3. Database Setup (SQLite)
DB_PATH = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER DEFAULT 10,
            last_bonus DATE
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id, username=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, coins, last_bonus FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, coins, last_bonus) VALUES (?, ?, 10, NULL)", (user_id, username))
        conn.commit()
        cursor.execute("SELECT user_id, coins, last_bonus FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def update_coins(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def claim_daily_bonus(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row and row[0] == today_str:
        conn.close()
        return False, "Apni ajker 6 coin bonus already claim korechen! Agamikal abar asben."
    
    cursor.execute("UPDATE users SET coins = coins + 6, last_bonus = ? WHERE user_id = ?", (today_str, user_id))
    conn.commit()
    conn.close()
    return True, "🎉 Shobash! Apni 6 coin daily bonus peyechen!"

# 4. Pinterest Short/Redirect Link Resolver
def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

# 5. User Commands
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)

    intro_text = (
        f"👋 **Salam, {message.from_user.first_name}!**\n\n"
        "🎬 **Ai Bot Ki Ki Korte Pare:**\n"
        "• **Facebook:** Reels, Videos download korte pare.\n"
        "• **Instagram:** Reels, Posts download korte pare.\n"
        "• **TikTok:** No-watermark video download korte pare.\n"
        "• **Pinterest:** Pins ebong Videos direct download korte pare.\n\n"
        "💰 **Coin Niyom:**\n"
        "• Proti video download: **2 Coin** kete neya hoy.\n"
        "• Daily Bonus: **6 Coin** shobai pabe.\n\n"
        f"🪙 **Apnar Balance:** `{user[1]}` Coins\n\n"
        "Link pathan download shuru korar jonno, othoba niche theke bonus nin!"
    )

    markup = types.InlineKeyboardMarkup()
    btn_bonus = types.InlineKeyboardButton("🎁 Daily Bonus (+6 Coin)", callback_data="claim_bonus")
    btn_bal = types.InlineKeyboardButton("💳 My Balance", callback_data="my_balance")
    markup.add(btn_bonus, btn_bal)

    bot.reply_to(message, intro_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    success, msg = claim_daily_bonus(message.from_user.id)
    bot.reply_to(message, msg)

@bot.message_handler(commands=['balance'])
def balance_cmd(message):
    user = get_user(message.from_user.id)
    bot.reply_to(message, f"🪙 Apnar bortoman balance: **{user[1]} Coins**", parse_mode="Markdown")

# 6. Admin Panel (/ad)
@bot.message_handler(commands=['ad'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Shudhumatro Admin ei command ti bebohar korte parbe!")
        return

    admin_text = (
        "👑 **Admin Control Panel**\n\n"
        "Commands:\n"
        "• Balance check: `/check <USER_ID>`\n"
        "• Coin add: `/add <USER_ID> <AMOUNT>`\n"
        "• Coin remove: `/remove <USER_ID> <AMOUNT>`\n"
        "• Total Users: `/total`"
    )
    bot.reply_to(message, admin_text, parse_mode="Markdown")

@bot.message_handler(commands=['check'])
def admin_check_user(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_id = int(message.text.split()[1])
        user = get_user(target_id)
        bot.reply_to(message, f"👤 User: `{target_id}`\n🪙 Balance: **{user[1]} Coins**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "Usage: `/check 12345678`", parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def admin_add_coins(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, target_id, amount = message.text.split()
        target_id, amount = int(target_id), int(amount)
        get_user(target_id)  # Ensure user exists
        update_coins(target_id, amount)
        user = get_user(target_id)
        bot.reply_to(message, f"✅ `{amount}` coin add kora hoyeche.\nUser: `{target_id}`\nNotun Balance: **{user[1]} Coins**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "Usage: `/add 12345678 10`", parse_mode="Markdown")

@bot.message_handler(commands=['remove'])
def admin_remove_coins(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        _, target_id, amount = message.text.split()
        target_id, amount = int(target_id), int(amount)
        get_user(target_id)
        update_coins(target_id, -amount)
        user = get_user(target_id)
        bot.reply_to(message, f"✅ `{amount}` coin kete neya hoyeche.\nUser: `{target_id}`\nNotun Balance: **{user[1]} Coins**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "Usage: `/remove 12345678 5`", parse_mode="Markdown")

@bot.message_handler(commands=['total'])
def admin_total_users(message):
    if message.from_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    bot.reply_to(message, f"📊 Total registered users: **{count}**", parse_mode="Markdown")

# Callback Query Handler
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data == "claim_bonus":
        success, msg = claim_daily_bonus(call.from_user.id)
        bot.answer_callback_query(call.id, text=msg, show_alert=True)
    elif call.data == "my_balance":
        user = get_user(call.from_user.id)
        bot.answer_callback_query(call.id, text=f"🪙 Balance: {user[1]} Coins", show_alert=True)

# 7. Video Download Handler
@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ Dayakore ekti shothik URL pathan.")
        return

    if "youtu" in raw_url:
        bot.reply_to(message, "⚠️ YouTube video ai bote support kore na. Shudhu FB, TikTok, Insta, Pinterest cholbe.")
        return

    user_id = message.chat.id
    user = get_user(user_id)

    # Balance Check
    if user[1] < 2:
        bot.reply_to(message, "❌ Apnar kache porjopto coin nei! Video download korte **2 coin** lagbe.\n\n`/daily` likhe 6 coin bonus nin!", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "⏳ Video check kora hocche...")
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    # Pinterest Short link (pin.it) handle kora
    resolved_url = resolve_url(raw_url)

    ydl_opts = {
        'format': 'best[filesize<48M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Referer': 'https://www.pinterest.com/'
        }
    }

    if FFMPEG_DIR:
        ydl_opts['ffmpeg_location'] = FFMPEG_DIR

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([resolved_url])

        downloaded_files = glob.glob(f"{output_dir}/*")
        if not downloaded_files:
            bot.edit_message_text("❌ Video download kora jayni ba 50MB er beshi size.", user_id, status_msg.message_id)
            return

        file_path = downloaded_files[0]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 49.5:
            bot.edit_message_text("❌ File size 50MB er beshi, Telegram a pathano shombhob na.", user_id, status_msg.message_id)
            return

        bot.edit_message_text("📤 Telegram a pathano hocche...", user_id, status_msg.message_id)

        # 2 Coins Deduct Kora
        update_coins(user_id, -2)
        new_balance = get_user(user_id)[1]

        with open(file_path, 'rb') as video_file:
            caption_text = f"✅ Download Shompurno!\n🪙 2 Coins kata hoyeche. Baki Balance: {new_balance}"
            bot.send_video(user_id, video_file, caption=caption_text, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ Truti: {str(e)[:120]}", user_id, status_msg.message_id)

    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_web_server, daemon=True).start()

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    print("Bot is successfully running...")

    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 409:
                time.sleep(5)
            else:
                time.sleep(3)
        except Exception:
            time.sleep(3)
