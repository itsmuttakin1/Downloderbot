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
    return "Social Downloader Bot is Running Perfectly!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# 2. Telegram Configuration
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
        return False, "⚠️ আপনি আজকের দৈনিক ৬ কয়েন বোনাস ইতিমধ্যে গ্রহণ করেছেন। আগামীকাল পুনরায় চেষ্টা করুন।"

    cursor.execute("UPDATE users SET coins = coins + 6, last_bonus = ? WHERE user_id = ?", (today_str, user_id))
    conn.commit()
    conn.close()
    return True, "🎉 অভিনন্দন! আপনি সফলভাবে দৈনিক ৬ কয়েন বোনাস পেয়ে গেছেন।"

# 4. Pinterest & Short URL Resolver
def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

# 5. Professional /start Command
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)

    membership_status = "🌟 প্রিমিয়াম মেম্বার (আনলিমিটেড)" if user[2] == 1 else "সাধারণ ব্যবহারকারী"

    intro_text = (
        f"স্বাগতম **{message.from_user.first_name}**! 🚀\n\n"
        "এটি একটি উচ্চগতির সোশ্যাল মিডিয়া ভিডিও ডাউনলোডার বট।\n"
        "যেকোনো ভিডিওর লিংক পাঠিয়ে সহজেই ফুল এইচডি কোয়ালিটিতে ডাউনলোড করে নিতে পারবেন।\n\n"
        "✨ **সাপোর্টেড প্ল্যাটফর্মসমূহ:**\n"
        "🔹 **Facebook** (Reels, Watch, Public Videos)\n"
        "🔹 **Instagram** (Reels, Posts, IGTV)\n"
        "🔹 **TikTok** (Watermark ছাড়া ক্লিয়ার ভিডিও)\n"
        "🔹 **Pinterest** (Pins, Videos & Short links)\n\n"
        "📊 **আপনার অ্যাকাউন্ট তথ্য:**\n"
        f"• স্ট্যাটাস: **{membership_status}**\n"
        f"• বর্তমান ব্যালেন্স: `{user[1]}` কয়েন\n\n"
        "💡 **কয়েন নিয়মাবলী:**\n"
        "• প্রতি ভিডিও ডাউনলোড: ২ কয়েন\n"
        "• দৈনিক ফ্রি বোনাস: ৬ কয়েন\n"
        "• প্রিমিয়াম ব্যবহারকারীদের কোনো কয়েন খরচ হবে না।\n\n"
        "ভিডিও পেতে সরাসরি লিংক মেসেজে পাঠিয়ে দিন অথবা নিচের বাটন চাপুন:"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_bonus = types.InlineKeyboardButton("🎁 দৈনিক বোনাস (+৬)", callback_data="claim_bonus")
    btn_bal = types.InlineKeyboardButton("💳 ব্যালেন্স দেখুন", callback_data="my_balance")
    btn_vip = types.InlineKeyboardButton("💎 প্রিমিয়াম সুবিধা", callback_data="vip_info")
    markup.add(btn_bonus, btn_bal)
    markup.add(btn_vip)

    bot.reply_to(message, intro_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['balance'])
def balance_cmd(message):
    user = get_user(message.from_user.id)
    vip_tag = " [💎 Premium]" if user[2] == 1 else ""
    bot.reply_to(message, f"🪙 আপনার বর্তমান ব্যালেন্স: **{user[1]} কয়েন**{vip_tag}", parse_mode="Markdown")

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    success, msg = claim_daily_bonus(message.from_user.id)
    bot.reply_to(message, msg)

# 6. Admin Panel UI (/ad)
@bot.message_handler(commands=['ad'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ আপনি এই বটের এডমিন নন!")
        return

    admin_text = (
        "👑 **অ্যাডমিন কন্ট্রোল ড্যাশবোর্ড**\n\n"
        "নিচের বাটনগুলোর মাধ্যমে সরাসরি ইউজার ম্যানেজ করতে পারবেন:"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    b_chk = types.InlineKeyboardButton("🔍 ইউজার ব্যালেন্স চেক", callback_data="adm_check")
    b_add = types.InlineKeyboardButton("➕ কয়েন যোগ করুন", callback_data="adm_add")
    b_rmv = types.InlineKeyboardButton("➖ কয়েন কাটুন", callback_data="adm_remove")
    b_vip = types.InlineKeyboardButton("💎 প্রিমিয়াম দিন/নিন", callback_data="adm_vip")
    b_tot = types.InlineKeyboardButton("📊 মোট ব্যবহারকারী", callback_data="adm_total")
    markup.add(b_chk, b_tot)
    markup.add(b_add, b_rmv)
    markup.add(b_vip)

    bot.reply_to(message, admin_text, parse_mode="Markdown", reply_markup=markup)

# Admin UI Action Handlers
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "অ্যাক্সেস ডিনাইড!", show_alert=True)
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
        bot.answer_callback_query(call.id, f"📊 মোট ইউজার: {total_users}\n💎 প্রিমিয়াম ইউজার: {total_vip}", show_alert=True)

    elif data == "adm_check":
        msg = bot.send_message(call.message.chat.id, "🔍 যার ব্যালেন্স চেক করবেন তার **User ID** পাঠান:")
        bot.register_next_step_handler(msg, step_check_balance)

    elif data == "adm_add":
        msg = bot.send_message(call.message.chat.id, "➕ কয়েন যোগ করতে পাঠান: `USER_ID AMOUNT`\nউদাহরণ: `123456789 20`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_add_coins)

    elif data == "adm_remove":
        msg = bot.send_message(call.message.chat.id, "➖ কয়েন কাটতে পাঠান: `USER_ID AMOUNT`\nউদাহরণ: `123456789 10`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_remove_coins)

    elif data == "adm_vip":
        msg = bot.send_message(call.message.chat.id, "💎 প্রিমিয়াম স্ট্যাটাস বদলাতে পাঠান: `USER_ID STATUS`\n(১ দিলে প্রিমিয়াম, ০ দিলে সাধারণ)\nউদাহরণ: `123456789 1`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_toggle_vip)

# Admin Step Functions
def step_check_balance(message):
    try:
        uid = int(message.text.strip())
        u = get_user(uid)
        vip_str = "হ্যাঁ" if u[2] == 1 else "না"
        bot.reply_to(message, f"👤 ইউজার: `{uid}`\n🪙 কয়েন: **{u[1]}**\n💎 প্রিমিয়াম: **{vip_str}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল আইডি দেওয়া হয়েছে।")

def step_add_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ সফল হয়েছে!\nইউজার `{uid}`-এ **{amt}** কয়েন যোগ করা হয়েছে।\nবর্তমান ব্যালেন্স: **{u[1]} কয়েন**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ অনুযায়ী দিন: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_remove_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, -amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ সফল হয়েছে!\nইউজার `{uid}` থেকে **{amt}** কয়েন কাটা হয়েছে।\nবর্তমান ব্যালেন্স: **{u[1]} কয়েন**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল ফরম্যাট! উদাহরণ অনুযায়ী দিন: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_toggle_vip(message):
    try:
        parts = message.text.strip().split()
        uid, st = int(parts[0]), int(parts[1])
        get_user(uid)
        set_premium(uid, st)
        status_txt = "💎 প্রিমিয়াম অ্যাক্টিভ করা হয়েছে।" if st == 1 else "সাধারণ মেম্বার করা হয়েছে।"
        bot.reply_to(message, f"✅ ইউজার `{uid}` এর {status_txt}", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল ফরম্যাট! দিন: `USER_ID STATUS` (১ বা ০)", parse_mode="Markdown")

# User Callback Query Handler
@bot.callback_query_handler(func=lambda call: True)
def user_callbacks(call):
    if call.data == "claim_bonus":
        success, msg = claim_daily_bonus(call.from_user.id)
        bot.answer_callback_query(call.id, text=msg, show_alert=True)
    elif call.data == "my_balance":
        user = get_user(call.from_user.id)
        vip_tag = " (💎 প্রিমিয়াম মেম্বার)" if user[2] == 1 else ""
        bot.answer_callback_query(call.id, text=f"🪙 আপনার ব্যালেন্স: {user[1]} কয়েন{vip_tag}", show_alert=True)
    elif call.data == "vip_info":
        vip_text = (
            "💎 প্রিমিয়াম মেম্বারশিপের সুবিধাসমূহ:\n\n"
            "• কোনো কয়েন খরচ হবে না (আনলিমিটেড ডাউনলোড)।\n"
            "• কোনো প্রকার ওয়াটারমার্ক বা স্পিড লিমিট থাকবে না।\n\n"
            "প্রিমিয়াম নিতে অ্যাডমিনের সাথে যোগাযোগ করুন।"
        )
        bot.answer_callback_query(call.id, text=vip_text, show_alert=True)

# 7. Video Download Engine
@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ অনুগ্রহ করে একটি সঠিক ভিডিও লিংক পাঠান।")
        return

    if "youtu" in raw_url:
        bot.reply_to(message, "⚠️ দুঃখিত, এই বটে ইউটিউব সাপোর্ট করে না। ফেসবুক, ইনস্টাগ্রাম, টিকটক এবং পিন্টারেস্টের লিংক পাঠান।")
        return

    user_id = message.chat.id
    user = get_user(user_id)
    is_vip = user[2] == 1

    # Coins check (VIP hole kono coin lagbe na)
    if not is_vip and user[1] < 2:
        bot.reply_to(
            message, 
            "❌ আপনার অ্যাকাউন্টে পর্যাপ্ত কয়েন নেই!\n\n"
            "ভিডিও ডাউনলোড করতে নূন্যতম **২ কয়েন** প্রয়োজন।\n"
            "প্রতিদিন ৬ কয়েন ফ্রি পেতে /daily চাপুন অথবা বোনাস বাটন ব্যবহার করুন।", 
            parse_mode="Markdown"
        )
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিও যাচাই ও ডাউনলোড করা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...")
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    # Pinterest Short Link (pin.it) Resolve
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
            bot.edit_message_text("❌ ভিডিও পাওয়া যায়নি অথবা ফাইল সাইজ ৫০MB অতিক্রম করেছে।", user_id, status_msg.message_id)
            return

        file_path = downloaded_files[0]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 49.5:
            bot.edit_message_text("❌ ভিডিও সাইজ ৫০MB-এর বেশি হওয়ায় টেলিগ্রামে আপলোড সম্ভব নয়।", user_id, status_msg.message_id)
            return

        bot.edit_message_text("📤 ভিডিও টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

        # Coin Deduction (VIP chara shobar 2 coin kete neya)
        if not is_vip:
            update_coins(user_id, -2)
            rem_coins = get_user(user_id)[1]
            caption = f"✅ ডাউনলোড সফল হয়েছে!\n🪙 ২ কয়েন কাটা হয়েছে | অবশিষ্ট ব্যালেন্স: {rem_coins} কয়েন"
        else:
            caption = "✅ ডাউনলোড সফল হয়েছে!\n💎 প্রিমিয়াম মেম্বার (কয়েন খরচ হয়নি)"

        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, caption=caption, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ ত্রুটি: {str(e)[:120]}", user_id, status_msg.message_id)

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
