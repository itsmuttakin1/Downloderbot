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

# ১. Render Port সচল রাখতে Flask সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Social Downloader Bot is Running Perfectly!"

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

# ৩. ডাটাবেজ সেটআপ (SQLite)
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
        return False, "⚠️ আপনি আজকের দৈনিক ৬ কয়েন বোনাস গ্রহণ করেছেন। আগামীকাল আবার আসুন।"

    cursor.execute("UPDATE users SET coins = coins + 6, last_bonus = ? WHERE user_id = ?", (today_str, user_id))
    conn.commit()
    conn.close()
    return True, "🎉 অভিনন্দন! আপনি সফলভাবে দৈনিক ৬ কয়েন বোনাস পেয়েছেন।"

def resolve_url(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except Exception:
        return url

# পেজ/প্রোফাইল ইউআরএল ঠিক করা (profile.php বা ইউজারনেম থাকলে /videos পাথ নিশ্চিত করা)
def format_fb_video_url(url):
    url = url.strip()
    if "profile.php" in url:
        if "sk=videos" not in url:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}sk=videos"
        return url
    else:
        clean_url = url.split("?")[0].rstrip("/")
        if not clean_url.endswith("/videos"):
            return f"{clean_url}/videos"
        return clean_url

# কনফার্মেশনের জন্য টেম্পোরারি ডাটা রাখার ডিকশনারি
PENDING_TASKS = {}

# ৪. /start কমান্ড
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)

    membership_status = "🌟 প্রিমিয়াম মেম্বার (আনলিমিটেড)" if user[2] == 1 else "সাধারণ ব্যবহারকারী"

    intro_text = (
        f"স্বাগতম **{message.from_user.first_name}**! 🚀\n\n"
        "এটি একটি উচ্চগতির সোশ্যাল মিডিয়া ভিডিও ডাউনলোডার বট।\n\n"
        "✨ **সাপোর্টেড ফিচারসমূহ:**\n"
        "🔹 **Facebook All Videos** (Page/Profile)\n"
        "🔹 **Facebook Single Videos & Reels**\n"
        "🔹 **Instagram Reels & Posts**\n"
        "🔹 **TikTok No-Watermark Videos**\n\n"
        "📊 **আপনার অ্যাকাউন্ট তথ্য:**\n"
        f"• স্ট্যাটাস: **{membership_status}**\n"
        f"• বর্তমান ব্যালেন্স: `{user[1]}` কয়েন\n\n"
        "💡 **কয়েন নিয়মাবলী:**\n"
        "• প্রতি ভিডিও ডাউনলোড: ২ কয়েন\n"
        "• দৈনিক ফ্রি বোনাস: ৬ কয়েন\n\n"
        "যেকোনো একটি ভিডিওর লিংক সরাসরি মেসেজে দিন অথবা ফেসবুকের সব ভিডিও ডাউনলোড করতে নিচের বাটনটি চাপুন:"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_fb_all = types.InlineKeyboardButton("📥 Facebook All Videos", callback_data="fb_all_start")
    btn_bonus = types.InlineKeyboardButton("🎁 দৈনিক বোনাস (+৬)", callback_data="claim_bonus")
    btn_bal = types.InlineKeyboardButton("💳 ব্যালেন্স দেখুন", callback_data="my_balance")
    markup.add(btn_fb_all)
    markup.add(btn_bonus, btn_bal)

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

# ৫. Admin Panel UI (/ad)
@bot.message_handler(commands=['ad'])
def admin_panel_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ আপনি এই বটের এডমিন নন!")
        return

    admin_text = "👑 **অ্যাডমিন কন্ট্রোল ড্যাশবোর্ড**\n\nনিচের বাটনগুলোর মাধ্যমে নিয়ন্ত্রণ করুন:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_chk = types.InlineKeyboardButton("🔍 ব্যালেন্স চেক", callback_data="adm_check")
    b_tot = types.InlineKeyboardButton("📊 মোট ইউজার", callback_data="adm_total")
    b_add = types.InlineKeyboardButton("➕ কয়েন যোগ", callback_data="adm_add")
    b_rmv = types.InlineKeyboardButton("➖ কয়েন কাটুন", callback_data="adm_remove")
    b_vip = types.InlineKeyboardButton("💎 প্রিমিয়াম দিন/নিন", callback_data="adm_vip")
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
        msg = bot.send_message(call.message.chat.id, "➕ কয়েন যোগ করতে পাঠান: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_add_coins)

    elif data == "adm_remove":
        msg = bot.send_message(call.message.chat.id, "➖ কয়েন কাটতে পাঠান: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_remove_coins)

    elif data == "adm_vip":
        msg = bot.send_message(call.message.chat.id, "💎 প্রিমিয়াম স্ট্যাটাস বদলাতে পাঠান: `USER_ID STATUS` (১ বা ০)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_toggle_vip)

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
        bot.reply_to(message, f"✅ ইউজার `{uid}`-এ **{amt}** কয়েন যোগ করা হয়েছে। ব্যালেন্স: **{u[1]}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল ফরম্যাট! দিন: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_remove_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, -amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ ইউজার `{uid}` থেকে **{amt}** কয়েন কাটা হয়েছে। ব্যালেন্স: **{u[1]}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল ফরম্যাট! দিন: `USER_ID AMOUNT`", parse_mode="Markdown")

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

# ৬. Facebook All Videos: লিঙ্ক গ্রহণ এবং নিশ্চিতকরণ
@bot.callback_query_handler(func=lambda call: call.data == "fb_all_start")
def ask_fb_page_link(call):
    msg = bot.send_message(
        call.message.chat.id,
        "🔗 **Facebook Page বা Profile-এর লিংকটি পাঠান:**\n\n"
        "(যেমন: `https://www.facebook.com/profile.php?id=...` অথবা পেজের লিংক)",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, scan_fb_page_videos)

def scan_fb_page_videos(message):
    url = message.text.strip()
    if not ("facebook.com" in url or "fb.watch" in url):
        bot.reply_to(message, "⚠️ এটি সঠিক ফেসবুক লিংক নয়। আবার চেষ্টা করুন।")
        return

    user_id = message.chat.id
    status_msg = bot.reply_to(message, "🔍 পেজের ভিডিওগুলো অনুসন্ধান করা হচ্ছে, দয়া করে অপেক্ষা করুন...")

    # প্রোফাইল ও পেজের জন্য সঠিক ভিডিও সেকশন নির্ধারণ
    target_url = format_fb_video_url(url)

    ydl_opts_scan = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_scan) as ydl:
            res = ydl.extract_info(target_url, download=False)
            
        entries = []
        if res and 'entries' in res and res['entries']:
            entries = [e for e in res['entries'] if e]
        elif res:
            entries = [res]

        total_videos = len(entries)
        if total_videos == 0:
            bot.edit_message_text("❌ এই প্রোফাইল বা পেজে কোনো পাবলিক ভিডিও পাওয়া যায়নি।", user_id, status_msg.message_id)
            return

        user = get_user(user_id)
        is_vip = user[2] == 1
        total_cost = 0 if is_vip else total_videos * 2

        # টেম্পোরারি ডাটাতে এন্ট্রি রাখা
        PENDING_TASKS[user_id] = {
            'entries': entries,
            'total_videos': total_videos,
            'total_cost': total_cost,
            'is_vip': is_vip
        }

        cost_text = "০ (💎 আপনি প্রিমিয়াম মেম্বার)" if is_vip else f"{total_cost} কয়েন (প্রতি ভিডিও ২ কয়েন)"
        balance_text = f"{user[1]} কয়েন"

        confirm_msg = (
            f"🎬 **ভিডিও অনুসন্ধানের ফলাফল:**\n\n"
            f"• মোট ভিডিও পাওয়া গেছে: **{total_videos} টি**\n"
            f"• মোট কয়েন খরচ হবে: **{cost_text}**\n"
            f"• আপনার বর্তমান ব্যালেন্স: **{balance_text}**\n\n"
            f"আপনি কি সবগুলো ভিডিও ডাউনলোড করতে চান?"
        )

        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_confirm = types.InlineKeyboardButton("✅ নিশ্চিত করুন (Confirm)", callback_data="confirm_fb_all")
        btn_cancel = types.InlineKeyboardButton("❌ বাতিল (Cancel)", callback_data="cancel_fb_all")
        markup.add(btn_confirm, btn_cancel)

        bot.edit_message_text(confirm_msg, user_id, status_msg.message_id, parse_mode="Markdown", reply_markup=markup)

    except Exception as e:
        bot.edit_message_text(f"⚠️ ভিডিও খুঁজতে সমস্যা হয়েছে: {str(e)[:120]}", user_id, status_msg.message_id)

# ৭. নিশ্চিতকরণ পরবর্তী ডাউনলোড একশন
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_fb_all", "cancel_fb_all"])
def handle_confirmation(call):
    user_id = call.message.chat.id

    if call.data == "cancel_fb_all":
        PENDING_TASKS.pop(user_id, None)
        bot.edit_message_text("❌ ভিডিও ডাউনলোড বাতিল করা হয়েছে।", user_id, call.message.message_id)
        return

    task = PENDING_TASKS.get(user_id)
    if not task:
        bot.edit_message_text("⚠️ অনুরোধটির মেয়াদ শেষ হয়ে গেছে। আবার পেজের লিংক দিন।", user_id, call.message.message_id)
        return

    user = get_user(user_id)
    is_vip = task['is_vip']
    total_cost = task['total_cost']
    total_videos = task['total_videos']
    entries = task['entries']

    if not is_vip and user[1] < total_cost:
        bot.answer_callback_query(call.id, f"❌ আপনার পর্যাপ্ত কয়েন নেই! প্রয়োজন {total_cost} কয়েন।", show_alert=True)
        return

    bot.edit_message_text(f"⏳ ডাউনলোড প্রক্রিয়া শুরু হয়েছে। মোট {total_videos}টি ভিডিও পাঠানো হবে...", user_id, call.message.message_id)

    # ব্যাকগ্রাউন্ডে ভিডিও পাঠানো যাতে টেলিগ্রাম টাইমআউট না হয়
    def run_batch_download():
        success_count = 0
        for index, item in enumerate(entries, start=1):
            curr_user = get_user(user_id)
            if not is_vip and curr_user[1] < 2:
                bot.send_message(user_id, f"⚠️ পর্যাপ্ত কয়েন না থাকায় {index-1}টি ভিডিওর পর ডাউনলোড বন্ধ হয়ে গেছে।")
                break

            video_target_url = item.get('url') or item.get('webpage_url')
            if not video_target_url:
                continue

            output_dir = f"downloads/{user_id}_{index}"
            os.makedirs(output_dir, exist_ok=True)

            ydl_opts_dl = {
                'format': 'best[filesize<48M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
                'merge_output_format': 'mp4',
                'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
                'quiet': True,
                'no_warnings': True,
            }
            if FFMPEG_DIR:
                ydl_opts_dl['ffmpeg_location'] = FFMPEG_DIR

            try:
                with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
                    info = ydl.extract_info(video_target_url, download=True)
                    video_title = info.get('title') or f"Facebook Video {index}"

                files = glob.glob(f"{output_dir}/*")
                if files:
                    file_path = files[0]
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

                    if file_size_mb <= 49.5:
                        if not is_vip:
                            update_coins(user_id, -2)

                        escaped_title = html.escape(video_title)
                        caption_text = (
                            f"🎬 <b>ভিডিও {index}/{total_videos}</b>\n\n"
                            f"📝 <b>ক্যাপশন (ক্লিক করলে কপি হবে):</b>\n"
                            f"<code>{escaped_title}</code>\n\n"
                            f'video download by "<a href="https://t.me/mrghost_121">Mr Ghost</a>"'
                        )

                        with open(file_path, 'rb') as vf:
                            bot.send_video(user_id, vf, caption=caption_text, parse_mode="HTML", supports_streaming=True)
                        success_count += 1
            except Exception:
                pass
            finally:
                if os.path.exists(output_dir):
                    shutil.rmtree(output_dir, ignore_errors=True)

        PENDING_TASKS.pop(user_id, None)
        rem_balance = get_user(user_id)[1]
        bot.send_message(user_id, f"🎉 সফলভাবে {success_count}টি ভিডিও পাঠানো সম্পন্ন হয়েছে!\n🪙 বর্তমান ব্যালেন্স: {rem_balance} কয়েন")

    threading.Thread(target=run_batch_download, daemon=True).start()

# ৮. সাধারণ বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: True)
def user_callbacks(call):
    if call.data == "claim_bonus":
        success, msg = claim_daily_bonus(call.from_user.id)
        bot.answer_callback_query(call.id, text=msg, show_alert=True)
    elif call.data == "my_balance":
        user = get_user(call.from_user.id)
        vip_tag = " (💎 প্রিমিয়াম মেম্বার)" if user[2] == 1 else ""
        bot.answer_callback_query(call.id, text=f"🪙 আপনার ব্যালেন্স: {user[1]} কয়েন{vip_tag}", show_alert=True)

# ৯. সাধারণ সিঙ্গেল লিংক হ্যান্ডলার
@bot.message_handler(func=lambda message: True)
def process_single_video_link(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ অনুগ্রহ করে একটি সঠিক ভিডিও লিংক পাঠান।")
        return

    if "youtu" in raw_url:
        bot.reply_to(message, "⚠️ দুঃখিত, এই বটে ইউটিউব সাপোর্ট করে না। ফেসবুক, ইনস্টাগ্রাম অথবা টিকটকের লিংক দিন।")
        return

    user_id = message.chat.id
    user = get_user(user_id)
    is_vip = user[2] == 1

    if not is_vip and user[1] < 2:
        bot.reply_to(message, "❌ পর্যাপ্ত কয়েন নেই! প্রতি ডাউনলোডে ২ কয়েন লাগে। /daily দিয়ে ফ্রি বোনাস নিন।")
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিও যাচাই ও ডাউনলোড হচ্ছে...")
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    resolved_url = resolve_url(raw_url)

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
        video_title = "Social Video"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(resolved_url, download=True)
            video_title = info.get('title') or "Social Video"

        downloaded_files = glob.glob(f"{output_dir}/*")
        if not downloaded_files:
            bot.edit_message_text("❌ ভিডিও পাওয়া যায়নি বা সাইজ ৫০MB অতিক্রম করেছে।", user_id, status_msg.message_id)
            return

        file_path = downloaded_files[0]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 49.5:
            bot.edit_message_text("❌ ভিডিওর সাইজ ৫০MB-এর বেশি হওয়ায় টেলিগ্রামে পাঠানো সম্ভব নয়।", user_id, status_msg.message_id)
            return

        bot.edit_message_text("📤 ভিডিও টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

        if not is_vip:
            update_coins(user_id, -2)
            rem_coins = get_user(user_id)[1]
            coin_info = f"🪙 ২ কয়েন কাটা হয়েছে | অবশিষ্ট ব্যালেন্স: {rem_coins} কয়েন"
        else:
            coin_info = "💎 প্রিমিয়াম মেম্বার (কয়েন খরচ হয়নি)"

        escaped_title = html.escape(video_title)
        caption = (
            f"✅ ডাউনলোড সফল হয়েছে!\n"
            f"{coin_info}\n\n"
            f"📝 <b>ক্যাপশন (ক্লিক করলে কপি হবে):</b>\n"
            f"<code>{escaped_title}</code>\n\n"
            f'video download by "<a href="https://t.me/mrghost_121">Mr Ghost</a>"'
        )

        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, caption=caption, parse_mode="HTML", supports_streaming=True)

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
