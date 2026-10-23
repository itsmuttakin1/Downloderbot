import os
import glob
import time
import html
import shutil
import sqlite3
import threading
from datetime import datetime, date
from flask import Flask, request, jsonify
from flask_cors import CORS
import telebot
from telebot import types
import yt_dlp
import requests

# ১. Flask সার্ভার ও CORS কনফিগারেশন (ওয়েবসাইট থেকে API রিকোয়েস্টের জন্য)
app = Flask(__name__)
CORS(app)  # Cloudflare Pages থেকে API কল করার অনুমতি নিশ্চিত করে

@app.route('/')
def home():
    return "Social Downloader Bot & API are Running Perfectly!"

# ওয়েবসাইট থেকে কল করার API এন্ডপয়েন্ট
@app.route('/api/download', methods=['POST'])
def api_download():
    data = request.get_json(silent=True) or {}
    raw_url = data.get("url", "").strip()

    if not raw_url:
        return jsonify({"status": "error", "message": "দয়া করে একটি ভিডিও লিংক প্রদান করুন।"}), 400

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        return jsonify({"status": "error", "message": "ভুল URL ফরম্যাট! সঠিক লিংক দিন।"}), 400

    if "youtu" in raw_url:
        return jsonify({"status": "error", "message": "ইউটিউব ভিডিও সাপোর্ট করে না।"}), 400

    valid_platforms = ["facebook.com", "fb.watch", "tiktok.com", "instagram.com"]
    if not any(p in raw_url.lower() for p in valid_platforms):
        return jsonify({"status": "error", "message": "শুধুমাত্র Facebook, TikTok এবং Instagram সাপোর্ট করে।"}), 400

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
            
            title = info.get('title') or info.get('description') or "সোশ্যাল ভিডিও"
            thumbnail = info.get('thumbnail') or ""
            
            # সরাসরি ডাউনলোডযোগ্য মিডিয়া লিংক বের করা
            download_url = None
            if 'url' in info:
                download_url = info['url']
            elif 'formats' in info:
                # অডিও+ভিডিও সহ সেরা কোয়ালিটির লিংক বাছাই
                formats = [f for f in info['formats'] if f.get('url')]
                if formats:
                    download_url = formats[-1].get('url')

            if not download_url:
                return jsonify({"status": "error", "message": "ডাউনলোড লিংক বের করা যায়নি।"}), 500

            return jsonify({
                "status": "success",
                "title": title[:100],
                "thumbnail": thumbnail,
                "download_url": download_url
            })

    except Exception as e:
        return jsonify({"status": "error", "message": f"ত্রুটি: {str(e)[:100]}"}), 500

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

ADMIN_ID = 5140546628  # আপনার Telegram Admin ID
bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

# ৩. ডাটাবেজ সেটআপ
DB_PATH = "bot_database.db"
db_mutex = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn

def init_db():
    with db_mutex:
        conn = get_db_connection()
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
    with db_mutex:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, coins, is_premium, last_bonus FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute("INSERT OR IGNORE INTO users (user_id, username, coins, is_premium, last_bonus) VALUES (?, ?, 10, 0, NULL)", (user_id, username))
            conn.commit()
            cursor.execute("SELECT user_id, coins, is_premium, last_bonus FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
        conn.close()
        return user

def update_coins(user_id, amount):
    with db_mutex:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()

def set_premium(user_id, status=1):
    with db_mutex:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_premium = ? WHERE user_id = ?", (status, user_id))
        conn.commit()
        conn.close()

def claim_daily_bonus(user_id):
    with db_mutex:
        conn = get_db_connection()
        cursor = conn.cursor()
        today_str = date.today().isoformat()
        cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if row and row[0] == today_str:
            conn.close()
            return False, "⚠️ আপনি আজকের দৈনিক ৬ কয়েন বোনাস ইতিমধ্যে গ্রহণ করেছেন! আগামীকাল পুনরায় চেষ্টা করুন।"

        cursor.execute("UPDATE users SET coins = coins + 6, last_bonus = ? WHERE user_id = ?", (today_str, user_id))
        conn.commit()
        conn.close()
        return True, "🎉 অভিনন্দন! আপনি সফলভাবে দৈনিক ৬ কয়েন বোনাস পেয়েছেন।"

def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

# সাধারণ ইউজারদের পেন্ডিং ডাউনলোডের মেমোরি ক্যাশ
PENDING_DOWNLOADS = {}

# ভিডিও ডাউনলোড ও ডেলিভারি করার সেন্ট্রাল ফাংশন
def download_and_send_video(user_id, target_url, video_title, is_vip, status_msg_id=None):
    output_dir = f"downloads/{user_id}_{int(time.time())}"
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
            bot.send_message(user_id, "❌ ভিডিও ডাউনলোড করা সম্ভব হয়নি অথবা ফাইলের সাইজ ৫০MB-এর বেশি।")
            if status_msg_id:
                try: bot.delete_message(user_id, status_msg_id)
                except Exception: pass
            return

        file_path = files[0]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 49.5:
            bot.send_message(user_id, "❌ ভিডিও সাইজ ৫০MB-এর বেশি হওয়ায় টেলিগ্রামে পাঠানো সম্ভব নয়।")
            if status_msg_id:
                try: bot.delete_message(user_id, status_msg_id)
                except Exception: pass
            return

        if not is_vip:
            update_coins(user_id, -2)
            rem_coins = get_user(user_id)[1]
            coin_info = f"🪙 ২ কয়েন কাটা হয়েছে | অবশিষ্ট ব্যালেন্স: {rem_coins} কয়েন"
        else:
            coin_info = "💎 প্রিমিয়াম মেম্বার (কয়েন খরচ হয়নি)"

        escaped_title = html.escape(video_title)
        caption_text = (
            f"✅ ডাউনলোড সফল হয়েছে!\n"
            f"{coin_info}\n\n"
            f"📝 <b>ক্যাপশন (ক্লিক করলে কপি হবে):</b>\n"
            f"<code>{escaped_title}</code>\n\n"
            f'video download by "<a href="https://t.me/mrghost_121">Mr Ghost</a>"'
        )

        with open(file_path, 'rb') as vf:
            bot.send_video(user_id, vf, caption=caption_text, parse_mode="HTML", supports_streaming=True)

        if status_msg_id:
            try: bot.delete_message(user_id, status_msg_id)
            except Exception: pass

    except Exception as e:
        bot.send_message(user_id, f"⚠️ ত্রুটি: {str(e)[:120]}")
        if status_msg_id:
            try: bot.delete_message(user_id, status_msg_id)
            except Exception: pass

    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

# ৪. /start কমান্ড
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)

    membership_status = "🌟 প্রিমিয়াম মেম্বার (আনলিমিটেড)" if user[2] == 1 else "সাধারণ ব্যবহারকারী"

    intro_text = (
        f"👋 **সালাম {message.from_user.first_name}!** 🚀\n\n"
        "এই বটটি ব্যবহার করা খুবই সহজ! আপনি কেবল যেকোনো **ভিডিওর লিংক চ্যাটে পাঠিয়ে দিন**, বাকি কাজ বট স্বয়ংক্রিয়ভাবে সম্পন্ন করবে।\n\n"
        "✨ **সাপোর্টেড প্ল্যাটফর্মসমূহ:**\n"
        "🔹 **Facebook** (Reels ও পাবলিক ভিডিও)\n"
        "🔹 **TikTok** (ওয়াটারমার্ক ছাড়া ক্লিয়ার ভিডিও)\n"
        "🔹 **Instagram** (Reels ও পোস্ট ভিডিও)\n\n"
        "📊 **আপনার অ্যাকাউন্ট তথ্য:**\n"
        f"• স্ট্যাটাস: **{membership_status}**\n"
        f"• বর্তমান ব্যালেন্স: `{user[1]}` কয়েন\n\n"
        "💡 **নিয়মাবলী:**\n"
        "• প্রতি ভিডিও ডাউনলোড: **২ কয়েন**\n"
        "• দৈনিক ফ্রি বোনাস: **৬ কয়েন**\n\n"
        "👉 ভিডিও পেতে এখনই যেকোনো ভিডিওর লিংক মেসেজে পাঠান!"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_bonus = types.InlineKeyboardButton("🎁 দৈনিক বোনাস (+৬)", callback_data="claim_bonus")
    btn_bal = types.InlineKeyboardButton("💳 ব্যালেন্স দেখুন", callback_data="my_balance")
    markup.add(btn_bonus, btn_bal)

    bot.reply_to(message, intro_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['balance'])
def balance_cmd(message):
    user = get_user(message.from_user.id)
    vip_tag = " [💎 Premium]" if user[2] == 1 else ""
    bot.reply_to(message, f"🪙 আপনার বর্তমান ব্যালেন্স: **{user[1]} কয়েন**{vip_tag}", parse_mode="Markdown")

@bot.message_handler(commands=['daily'])
def daily_cmd(message):
    success, msg = claim_daily_bonus(message.from_user.id)
    bot.reply_to(message, msg)

# ৫. এডমিন প্যানেল UI (/ad)
@bot.message_handler(commands=['ad'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ আপনি এই বটের অ্যাডমিন নন!")
        return

    admin_text = "👑 **অ্যাডমিন কন্ট্রোল ড্যাশবোর্ড**\n\nনিচের বাটনগুলোর মাধ্যমে নিয়ন্ত্রণ করুন:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_chk = types.InlineKeyboardButton("🔍 ব্যালেন্স চেক", callback_data="adm_check")
    b_tot = types.InlineKeyboardButton("📊 মোট ব্যবহারকারী", callback_data="adm_total")
    b_add = types.InlineKeyboardButton("➕ কয়েন যোগ", callback_data="adm_add")
    b_rmv = types.InlineKeyboardButton("➖ কয়েন কাটুন", callback_data="adm_remove")
    b_vip = types.InlineKeyboardButton("💎 প্রিমিয়াম সেট", callback_data="adm_vip")
    markup.add(b_chk, b_tot)
    markup.add(b_add, b_rmv)
    markup.add(b_vip)

    bot.reply_to(message, admin_text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "অ্যাক্সেস ডিনাইড!", show_alert=True)
        return

    data = call.data
    if data == "adm_total":
        with db_mutex:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(is_premium) FROM users")
            row = cursor.fetchone()
            conn.close()
        total_users = row[0] or 0
        total_vip = row[1] or 0
        bot.answer_callback_query(call.id, f"📊 মোট ব্যবহারকারী: {total_users}\n💎 প্রিমিয়াম ব্যবহারকারী: {total_vip}", show_alert=True)

    elif data == "adm_check":
        msg = bot.send_message(call.message.chat.id, "🔍 যার ব্যালেন্স চেক করবেন তার **User ID** পাঠান:")
        bot.register_next_step_handler(msg, step_check_balance)

    elif data == "adm_add":
        msg = bot.send_message(call.message.chat.id, "➕ কয়েন যোগ করার ফরম্যাট: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_add_coins)

    elif data == "adm_remove":
        msg = bot.send_message(call.message.chat.id, "➖ কয়েন কাটার ফরম্যাট: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_remove_coins)

    elif data == "adm_vip":
        msg = bot.send_message(call.message.chat.id, "💎 প্রিমিয়াম পরিবর্তনের ফরম্যাট: `USER_ID STATUS` (১ বা ০)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_toggle_vip)

def step_check_balance(message):
    try:
        uid = int(message.text.strip())
        u = get_user(uid)
        vip_str = "হ্যাঁ" if u[2] == 1 else "না"
        bot.reply_to(message, f"👤 ইউজার: `{uid}`\n🪙 ব্যালেন্স: **{u[1]} কয়েন**\n💎 প্রিমিয়াম: **{vip_str}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল আইডি দেওয়া হয়েছে।")

def step_add_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ ইউজার `{uid}`-এ **{amt}** কয়েন যোগ করা হয়েছে। ব্যালেন্স: **{u[1]} কয়েন**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_remove_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, -amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ ইউজার `{uid}` থেকে **{amt}** কয়েন কাটা হয়েছে। ব্যালেন্স: **{u[1]} কয়েন**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_toggle_vip(message):
    try:
        parts = message.text.strip().split()
        uid, st = int(parts[0]), int(parts[1])
        get_user(uid)
        set_premium(uid, st)
        status_txt = "💎 প্রিমিয়াম অ্যাক্টিভ করা হয়েছে।" if st == 1 else "সাধারণ মেম্বার করা হয়েছে।"
        bot.reply_to(message, f"✅ ইউজার `{uid}` {status_txt}", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `USER_ID STATUS` (১ বা ০)", parse_mode="Markdown")

# ৬. ভিডিও লিংক গ্রহণ
@bot.message_handler(func=lambda message: True)
def handle_incoming_link(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক ভিডিও URL পাঠান।")
        return

    if "youtu" in raw_url:
        bot.reply_to(message, "⚠️ ইউটিউব ভিডিও এই বটে সাপোর্ট করে না! ফেসবুক, ইনস্টাগ্রাম অথবা টিকটকের লিংক দিন।")
        return

    valid_platforms = ["facebook.com", "fb.watch", "tiktok.com", "instagram.com"]
    if not any(p in raw_url.lower() for p in valid_platforms):
        bot.reply_to(message, "⚠️ শুধুমাত্র ফেসবুক, টিকটক এবং ইনস্টাগ্রাম ভিডিও লিংক সাপোর্ট করে।")
        return

    user_id = message.chat.id
    user = get_user(user_id)
    is_vip = user[2] == 1

    if not is_vip and user[1] < 2:
        bot.reply_to(message, "❌ আপনার অ্যাকাউন্টে পর্যাপ্ত কয়েন নেই!\nভিডিও ডাউনলোড করতে **২ কয়েন** প্রয়োজন।\n\n`/daily` লিখে ফ্রি ৬ কয়েন বোনাস নিন!", parse_mode="Markdown")
        return

    resolved_url = resolve_url(raw_url)

    # 💎 প্রিমিয়াম ইউজার: সরাসরি ডাউনলোড
    if is_vip:
        status_msg = bot.reply_to(message, "💎 প্রিমিয়াম অ্যাক্টিভ: ভিডিও সরাসরি ডাউনলোড ও প্রসেস করা হচ্ছে...")
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
                video_title = info.get('title') or info.get('description') or "সোশ্যাল ভিডিও"
                if len(video_title) > 200:
                    video_title = video_title[:200] + "..."
        except Exception:
            video_title = "সোশ্যাল ভিডিও"

        download_and_send_video(user_id, resolved_url, video_title, is_vip=True, status_msg_id=status_msg.message_id)
        return

    # 👤 সাধারণ ইউজার: ক্যাপশন ও কনফার্মেশন পপ-আপ
    status_msg = bot.reply_to(message, "🔍 ভিডিওর তথ্য অনুসন্ধান করা হচ্ছে, দয়া করে অপেক্ষা করুন...")

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
            video_title = info.get('title') or info.get('description') or "সোশ্যাল ভিডিও"
            if len(video_title) > 200:
                video_title = video_title[:200] + "..."

        PENDING_DOWNLOADS[user_id] = {
            'url': resolved_url,
            'title': video_title,
            'is_vip': False
        }

        escaped_title = html.escape(video_title)
        confirm_text = (
            f"🎬 <b>ভিডিওর বিবরণ:</b>\n\n"
            f"📝 <b>ক্যাপশন:</b>\n<code>{escaped_title}</code>\n\n"
            f"💰 <b>ডাউনলোড খরচ:</b> ২ কয়েন\n"
            f"🪙 <b>আপনার বর্তমান ব্যালেন্স:</b> {user[1]} কয়েন\n\n"
            f"আপনি কি ভিডিওটি ডাউনলোড করতে চান?"
        )

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_confirm = types.InlineKeyboardButton("✅ নিশ্চিত করুন (Confirm)", callback_data="confirm_dl")
        btn_cancel = types.InlineKeyboardButton("❌ বাতিল (Cancel)", callback_data="cancel_dl")
        markup.add(btn_confirm, btn_cancel)

        bot.edit_message_text(confirm_text, user_id, status_msg.message_id, parse_mode="HTML", reply_markup=markup)

    except Exception as e:
        bot.edit_message_text(f"⚠️ ভিডিওর তথ্য পেতে সমস্যা হয়েছে: {str(e)[:120]}", user_id, status_msg.message_id)

# ৭. কনফার্মেশন বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_dl", "cancel_dl"])
def handle_download_confirmation(call):
    user_id = call.message.chat.id

    if call.data == "cancel_dl":
        PENDING_DOWNLOADS.pop(user_id, None)
        bot.edit_message_text("❌ ভিডিও ডাউনলোড বাতিল করা হয়েছে।", user_id, call.message.message_id)
        return

    task = PENDING_DOWNLOADS.get(user_id)
    if not task:
        bot.edit_message_text("⚠️ অনুরোধটির মেয়াদ শেষ হয়ে গেছে। আবার লিংক পাঠান।", user_id, call.message.message_id)
        return

    user = get_user(user_id)
    if user[1] < 2:
        bot.answer_callback_query(call.id, "❌ আপনার পর্যাপ্ত কয়েন নেই! প্রয়োজন ২ কয়েন।", show_alert=True)
        return

    bot.edit_message_text("⏳ ভিডিও ডাউনলোড ও টেলিগ্রামে প্রসেস করা হচ্ছে, অনুগ্রহ করে অপেক্ষা করুন...", user_id, call.message.message_id)
    download_and_send_video(user_id, task['url'], task['title'], is_vip=False, status_msg_id=call.message.message_id)
    PENDING_DOWNLOADS.pop(user_id, None)

# ৮. সাধারণ বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: True)
def user_callbacks(call):
    if call.data == "claim_bonus":
        success, msg = claim_daily_bonus(call.from_user.id)
        bot.answer_callback_query(call.id, text=msg, show_alert=True)
    elif call.data == "my_balance":
        user = get_user(call.from_user.id)
        vip_tag = " (💎 প্রিমিয়াম মেম্বার)" if user[2] == 1 else ""
        bot.answer_callback_query(call.id, text=f"🪙 আপনার ব্যালেন্স: {user[1]} কয়েন{vip_tag}", show_alert=True)

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
