import os
import glob
import time
import html
import shutil
import sqlite3
import threading
from datetime import datetime, date
from flask import Flask
import telebot
from telebot import types
import yt_dlp
import requests

# 1. Flask server to keep Render port alive
app = Flask(__name__)

@app.route('/')
def home():
    return "Social Downloader Bot is Running Perfectly!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# 2. Telegram Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

ADMIN_ID = 5140546628  # Apnar Telegram Admin ID
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
            is_premium INTEGER DEFAULT 0,
            last_bonus DATE
        )
    ''')
    conn.commit()
    conn.close()

def get_user(user_id, username=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, coins, is_premium, last_bonus FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, username, coins, is_premium, last_bonus) VALUES (?, ?, 10, 0, NULL)", (user_id, username))
        conn.commit()
        cursor.execute("SELECT user_id, coins, is_premium, last_bonus FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return user

def update_coins(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def set_premium(user_id, status=1):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (status, user_id))
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
        return False, "⚠️ Apni ajker 6 coin daily bonus already claim korechen! Agamikal abar ashben."

    cursor.execute("UPDATE users SET coins = coins + 6, last_bonus = ? WHERE user_id = ?", (today_str, user_id))
    conn.commit()
    conn.close()
    return True, "🎉 Shobash! Apni shofolbhabe 6 coin daily bonus peyechen."

def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

# Temporary pending downloads dictionary
PENDING_DOWNLOADS = {}

# 4. /start Command
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)

    membership_status = "🌟 Premium Member (Unlimited)" if user[2] == 1 else "Normal User"

    intro_text = (
        f"👋 **Salam {message.from_user.first_name}!** 🚀\n\n"
        "Ai bot bebohar kora khub-i shohoj! Shudhu apnar pochonder **video link chat-e pathiye din**, bot baki kaj automatic kore debe.\n\n"
        "✨ **Supported Platforms:**\n"
        "🔹 **Facebook** (Reels & Public Videos)\n"
        "🔹 **TikTok** (No Watermark Videos)\n"
        "🔹 **Instagram** (Reels & Posts)\n\n"
        "📊 **Account Info:**\n"
        f"• Status: **{membership_status}**\n"
        f"• Bortoman Balance: `{user[1]}` Coins\n\n"
        "💡 **Rules:**\n"
        "• Proti video download: **2 Coin**\n"
        "• Daily Free Bonus: **6 Coin**\n\n"
        "👉 Download korte ekhoni kono video link send korun!"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_bonus = types.InlineKeyboardButton("🎁 Daily Bonus (+6)", callback_data="claim_bonus")
    btn_bal = types.InlineKeyboardButton("💳 Balance Check", callback_data="my_balance")
    markup.add(btn_bonus, btn_bal)

    bot.reply_to(message, intro_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['balance'])
def balance_cmd(message):
    user = get_user(message.from_user.id)
    vip_tag = " [💎 Premium]" if user[2] == 1 else ""
    bot.reply_to(message, f"🪙 Apnar bortoman balance: **{user[1]} Coins**{vip_tag}", parse_mode="Markdown")

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    success, msg = claim_daily_bonus(message.from_user.id)
    bot.reply_to(message, msg)

# 5. Admin Panel UI (/ad)
@bot.message_handler(commands=['ad'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Apni ai bot-er admin non!")
        return

    admin_text = "👑 **Admin Control Dashboard**\n\nNicher button gulo diye manage korun:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_chk = types.InlineKeyboardButton("🔍 Balance Check", callback_data="adm_check")
    b_tot = types.InlineKeyboardButton("📊 Total Users", callback_data="adm_total")
    b_add = types.InlineKeyboardButton("➕ Coin Add", callback_data="adm_add")
    b_rmv = types.InlineKeyboardButton("➖ Coin Remove", callback_data="adm_remove")
    b_vip = types.InlineKeyboardButton("💎 Premium Set", callback_data="adm_vip")
    markup.add(b_chk, b_tot)
    markup.add(b_add, b_rmv)
    markup.add(b_vip)

    bot.reply_to(message, admin_text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Access Denied!", show_alert=True)
        return

    data = call.data
    if data == "adm_total":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*), SUM(is_premium) FROM users")
        row = cursor.fetchone()
        conn.close()
        total_users = row[0] or 0
        total_vip = row[1] or 0
        bot.answer_callback_query(call.id, f"📊 Total Users: {total_users}\n💎 Premium Users: {total_vip}", show_alert=True)

    elif data == "adm_check":
        msg = bot.send_message(call.message.chat.id, "🔍 Jar balance check korben tar **User ID** pathan:")
        bot.register_next_step_handler(msg, step_check_balance)

    elif data == "adm_add":
        msg = bot.send_message(call.message.chat.id, "➕ Coin add korte format: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_add_coins)

    elif data == "adm_remove":
        msg = bot.send_message(call.message.chat.id, "➖ Coin cut korte format: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_remove_coins)

    elif data == "adm_vip":
        msg = bot.send_message(call.message.chat.id, "💎 Premium change korte format: `USER_ID STATUS` (1 ba 0)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_toggle_vip)

def step_check_balance(message):
    try:
        uid = int(message.text.strip())
        u = get_user(uid)
        vip_str = "Hae" if u[2] == 1 else "Na"
        bot.reply_to(message, f"👤 User: `{uid}`\n🪙 Coins: **{u[1]}**\n💎 Premium: **{vip_str}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ Bhul ID dewa hoyeche.")

def step_add_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ User `{uid}`-e **{amt}** coin add kora hoyeche. Balance: **{u[1]}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ Format thik nei! Format: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_remove_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, -amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ User `{uid}` theke **{amt}** coin kata hoyeche. Balance: **{u[1]}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ Format thik nei! Format: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_toggle_vip(message):
    try:
        parts = message.text.strip().split()
        uid, st = int(parts[0]), int(parts[1])
        get_user(uid)
        set_premium(uid, st)
        status_txt = "💎 Premium Active kora hoyeche." if st == 1 else "Normal Member kora hoyeche."
        bot.reply_to(message, f"✅ User `{uid}` {status_txt}", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ Format thik nei! Format: `USER_ID STATUS` (1 ba 0)", parse_mode="Markdown")

# 6. Video Link Received: Information Extract and Confirmation Request
@bot.message_handler(func=lambda message: True)
def handle_incoming_link(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ Dayakore ekti shothik video URL pathan.")
        return

    # YouTube ba Pinterest block kora
    if "youtu" in raw_url:
        bot.reply_to(message, "⚠️ YouTube video ai bote support kore na! Facebook, Instagram, ba TikTok link pathan.")
        return

    # Shudhu Facebook, TikTok, Instagram allow kora
    valid_platforms = ["facebook.com", "fb.watch", "tiktok.com", "instagram.com"]
    if not any(p in raw_url.lower() for p in valid_platforms):
        bot.reply_to(message, "⚠️ Shudhumatro Facebook, TikTok, ebong Instagram video link support kore.")
        return

    user_id = message.chat.id
    user = get_user(user_id)
    is_vip = user[2] == 1

    if not is_vip and user[1] < 2:
        bot.reply_to(message, "❌ Apnar kache porjopto coin nei!\nVideo download korte **2 Coin** lagbe.\n\n`/daily` likhe free 6 coin bonus nin!", parse_mode="Markdown")
        return

    status_msg = bot.reply_to(message, "🔍 Video details check kora hocche...")
    resolved_url = resolve_url(raw_url)

    ydl_opts_info = {
        'extract_flat': False,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(resolved_url, download=False)
            video_title = info.get('title') or info.get('description') or "Social Video"
            # Limit title length
            if len(video_title) > 200:
                video_title = video_title[:200] + "..."

        # Store in pending task
        PENDING_DOWNLOADS[user_id] = {
            'url': resolved_url,
            'title': video_title,
            'is_vip': is_vip
        }

        cost_str = "0 Coin (💎 Premium)" if is_vip else "2 Coin"
        escaped_title = html.escape(video_title)

        confirm_text = (
            f"🎬 <b>Video Information:</b>\n\n"
            f"📝 <b>Caption:</b>\n<code>{escaped_title}</code>\n\n"
            f"💰 <b>Download Cost:</b> {cost_str}\n"
            f"🪙 <b>Apnar Bortoman Balance:</b> {user[1]} Coins\n\n"
            f"Apni ki video ti download korte chan?"
        )

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_confirm = types.InlineKeyboardButton("✅ Confirm", callback_data="confirm_dl")
        btn_cancel = types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_dl")
        markup.add(btn_confirm, btn_cancel)

        bot.edit_message_text(confirm_text, user_id, status_msg.message_id, parse_mode="HTML", reply_markup=markup)

    except Exception as e:
        bot.edit_message_text(f"⚠️ Video details pete shomossha hoyeche: {str(e)[:120]}", user_id, status_msg.message_id)

# 7. Confirmation Button Handler (Download & Send)
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_dl", "cancel_dl"])
def handle_download_confirmation(call):
    user_id = call.message.chat.id

    if call.data == "cancel_dl":
        PENDING_DOWNLOADS.pop(user_id, None)
        bot.edit_message_text("❌ Download batil kora hoyeche.", user_id, call.message.message_id)
        return

    task = PENDING_DOWNLOADS.get(user_id)
    if not task:
        bot.edit_message_text("⚠️ Request-er somoy sesh hoye geche. Abar link pathan.", user_id, call.message.message_id)
        return

    user = get_user(user_id)
    is_vip = task['is_vip']

    if not is_vip and user[1] < 2:
        bot.answer_callback_query(call.id, "❌ Apnar porjopto coin nei! Proyojon 2 coin.", show_alert=True)
        return

    bot.edit_message_text("⏳ Video download ebong Telegram-e processing hocche, ektu opeksha korun...", user_id, call.message.message_id)

    target_url = task['url']
    video_title = task['title']
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'format': 'best[filesize<48M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    if FFMPEG_DIR:
        ydl_opts['ffmpeg_location'] = FFMPEG_DIR

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])

        files = glob.glob(f"{output_dir}/*")
        if not files:
            bot.send_message(user_id, "❌ Video download kora jayni ba 50MB er beshi size.")
            return

        file_path = files[0]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 49.5:
            bot.send_message(user_id, "❌ File size 50MB er beshi, Telegram a pathano shombhob na.")
            return

        # Coin deduction
        if not is_vip:
            update_coins(user_id, -2)
            rem_coins = get_user(user_id)[1]
            coin_info = f"🪙 ২ কয়েন কাটা হয়েছে | অবশিষ্ট ব্যালেন্স: {rem_coins} কয়েন"
        else:
            coin_info = "💎 প্রিমিয়াম মেম্বার (কয়েন খরচ হয়নি)"

        escaped_title = html.escape(video_title)
        caption_text = (
            f"✅ ডাউনলোড সফল হয়েছে!\n"
            f"{coin_info}\n\n"
            f"📝 <b>ক্যাপশন (ক্লিক করলে কপি হবে):</b>\n"
            f"<code>{escaped_title}</code>\n\n"
            f'video download by "<a href="https://t.me/mrghost_121">Mr Ghost</a>"'
        )

        with open(file_path, 'rb') as vf:
            bot.send_video(user_id, vf, caption=caption_text, parse_mode="HTML", supports_streaming=True)

        bot.delete_message(user_id, call.message.message_id)

    except Exception as e:
        bot.send_message(user_id, f"⚠️ Error: {str(e)[:120]}")

    finally:
        PENDING_DOWNLOADS.pop(user_id, None)
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

# 8. Generic Inline Callback Query Handler
@bot.callback_query_handler(func=lambda call: True)
def user_callbacks(call):
    if call.data == "claim_bonus":
        success, msg = claim_daily_bonus(call.from_user.id)
        bot.answer_callback_query(call.id, text=msg, show_alert=True)
    elif call.data == "my_balance":
        user = get_user(call.from_user.id)
        vip_tag = " (💎 Premium Member)" if user[2] == 1 else ""
        bot.answer_callback_query(call.id, text=f"🪙 Balance: {user[1]} Coins{vip_tag}", show_alert=True)

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
