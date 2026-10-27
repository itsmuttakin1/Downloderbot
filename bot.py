import os
import glob
import time
import html
import shutil
import sqlite3
import threading
from datetime import datetime, date
from flask import Flask, request, jsonify, render_template_string, send_file
import telebot
from telebot import types
import yt_dlp
import requests

# ১. Flask ওয়েব সার্ভার ও রেসপনসিভ ড্যাশবোর্ড
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="bn">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Universal Video Downloader</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between font-sans">
    <div class="max-w-3xl mx-auto w-full px-4 py-12 flex-grow flex flex-col justify-center">
        <!-- Brand Header -->
        <div class="text-center mb-8">
            <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/20 mb-4">
                <i class="fa-solid fa-cloud-arrow-down text-2xl text-white"></i>
            </div>
            <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight text-white">
                Universal <span class="text-cyan-400">Downloader</span>
            </h1>
            <p class="text-slate-400 mt-2 text-sm md:text-base">
                Facebook, TikTok, Instagram, Twitter, Pinterest সহ যেকোনো ভিডিও সহজে ডাউনলোড করুন
            </p>
        </div>

        <!-- Download Card -->
        <div class="bg-slate-900/90 border border-slate-800 rounded-3xl p-6 md:p-8 shadow-2xl backdrop-blur-xl">
            <form id="downloadForm" class="space-y-4">
                <div>
                    <label class="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">ভিডিও লিংক পেস্ট করুন</label>
                    <div class="relative">
                        <input type="url" id="videoUrl" required placeholder="https://..." 
                            class="w-full bg-slate-950 border border-slate-700/80 rounded-2xl py-3.5 pl-4 pr-12 text-sm text-slate-200 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all">
                        <button type="button" onclick="pasteClipboard()" class="absolute right-3.5 top-3.5 text-slate-400 hover:text-cyan-400 transition-colors" title="Paste">
                            <i class="fa-regular fa-paste text-lg"></i>
                        </button>
                    </div>
                </div>

                <button type="submit" id="submitBtn" 
                    class="w-full py-4 rounded-2xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-semibold text-sm shadow-lg shadow-cyan-500/25 transition-all flex items-center justify-center gap-2">
                    <i class="fa-solid fa-bolt"></i>
                    <span>ডাউনলোড শুরু করুন</span>
                </button>
            </form>

            <!-- Status & Spinner -->
            <div id="statusBox" class="hidden mt-6 text-center">
                <div class="inline-flex items-center gap-3 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-cyan-400">
                    <svg class="animate-spin h-4 w-4 text-cyan-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                    </svg>
                    <span id="statusText">ভিডিও প্রসেস করা হচ্ছে...</span>
                </div>
            </div>

            <!-- Result Box -->
            <div id="resultBox" class="hidden mt-6 p-4 rounded-2xl bg-slate-950 border border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div class="truncate w-full sm:w-auto">
                    <p id="videoTitle" class="text-sm font-medium text-slate-200 truncate max-w-sm"></p>
                    <p class="text-xs text-emerald-400 mt-0.5"><i class="fa-solid fa-circle-check mr-1"></i>ভিডিও সম্পূর্ণ প্রস্তুত!</p>
                </div>
                <a id="downloadLink" href="#" download class="w-full sm:w-auto px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-xs font-semibold text-center transition-all flex items-center justify-center gap-2">
                    <i class="fa-solid fa-arrow-down"></i>
                    <span>Save Video</span>
                </a>
            </div>
        </div>

        <!-- Telegram Bot Link -->
        <div class="mt-8 text-center">
            <a href="https://t.me/mrghost_121" target="_blank" class="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-cyan-400 transition-colors">
                <i class="fa-brands fa-telegram text-base text-cyan-400"></i>
                <span>টেলিগ্রাম বটের সাথে যুক্ত হন (@mrghost_121)</span>
            </a>
        </div>
    </div>

    <footer class="py-4 text-center text-xs text-slate-600 border-t border-slate-900">
        Powered by Mr Ghost | Universal Video Engine
    </footer>

    <script>
        async function pasteClipboard() {
            try {
                const text = await navigator.clipboard.readText();
                document.getElementById('videoUrl').value = text;
            } catch (err) {}
        }

        document.getElementById('downloadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const url = document.getElementById('videoUrl').value.trim();
            if (!url) return;

            const submitBtn = document.getElementById('submitBtn');
            const statusBox = document.getElementById('statusBox');
            const resultBox = document.getElementById('resultBox');
            const statusText = document.getElementById('statusText');

            submitBtn.disabled = true;
            statusBox.classList.remove('hidden');
            resultBox.classList.add('hidden');
            statusText.innerText = "ভিডিও সংগ্রহ ও প্রসেস হচ্ছে, অপেক্ষা করুন...";

            try {
                const response = await fetch('/api/web-download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });

                const data = await response.json();
                if (data.success) {
                    statusBox.classList.add('hidden');
                    resultBox.classList.remove('hidden');
                    document.getElementById('videoTitle').innerText = data.title;
                    document.getElementById('downloadLink').href = data.download_url;
                } else {
                    alert('⚠️ ' + data.error);
                    statusBox.classList.add('hidden');
                }
            } catch (err) {
                alert('⚠️ সার্ভার রেসপন্স করতে পারেনি। পুনরায় চেষ্টা করুন।');
                statusBox.classList.add('hidden');
            } finally {
                submitBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
"""

# YouTube বাইপাস ডাউনলোড ইঞ্জিন
def download_youtube_via_api(url, output_path):
    instances = [
        "https://cobalt-api.kwiatekm.tokyo",
        "https://api.cobalt.tools",
        "https://cobalt.api.scub3d.com"
    ]
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": url,
        "videoQuality": "720",
        "youtubeVideoCodec": "h264"
    }

    for inst in instances:
        try:
            r = requests.post(f"{inst}/", json=payload, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                dl_url = data.get("url")
                if dl_url:
                    with requests.get(dl_url, stream=True, timeout=60) as res:
                        res.raise_for_status()
                        with open(output_path, "wb") as f:
                            for chunk in res.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    return True
        except Exception:
            continue
    return False

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/web-download', methods=['POST'])
def web_download_api():
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'success': False, 'error': 'কোনো ভিডিও URL দেওয়া হয়নি'}), 400

    temp_id = f"web_{int(time.time() * 1000)}"
    output_dir = f"downloads/{temp_id}"
    os.makedirs(output_dir, exist_ok=True)
    video_out = f"{output_dir}/video.mp4"

    is_youtube = ("youtu.be" in url or "youtube.com" in url)

    # YouTube হলে ক্লাউড আইপি ব্লক এড়াতে বাইপাস এপিআই ব্যবহার
    if is_youtube:
        success = False
        try:
            success = download_youtube_via_api(url, video_out)
        except Exception:
            pass

        if success and os.path.exists(video_out):
            return jsonify({
                'success': True,
                'title': 'YouTube Video',
                'download_url': f'/get-file/{temp_id}/video.mp4'
            })
        else:
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            return jsonify({
                'success': False,
                'error': 'ইউটিউবের ডেটাসেন্টার আইপি রেস্ট্রিকশনের কারণে এটি ডাউনলোড সম্ভব হয়নি। অনুগ্রহ করে Facebook, TikTok, Instagram, Pinterest ইত্যাদির লিংক দিন।'
            }), 400

    # অন্যান্য প্ল্যাটফর্মের জন্য সার্বজনীন yt-dlp
    ydl_opts = {
        'format': 'best[filesize<48M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/video.%(ext)s',
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
            info = ydl.extract_info(url, download=True)
            title = info.get('title') or "Social Video"

        files = glob.glob(f"{output_dir}/*")
        if not files:
            return jsonify({'success': False, 'error': 'ভিডিও পাওয়া যায়নি বা সাইজ ৫০MB-এর বেশি'}), 400

        filename = os.path.basename(files[0])
        return jsonify({
            'success': True,
            'title': title,
            'download_url': f'/get-file/{temp_id}/{filename}'
        })
    except Exception as e:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)
        return jsonify({'success': False, 'error': f'ভিডিও সংগ্রহ করতে সমস্যা হয়েছে: {str(e)[:100]}'}), 500

@app.route('/get-file/<folder>/<filename>')
def serve_downloaded_file(folder, filename):
    file_path = os.path.join("downloads", folder, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File Not Found", 404

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
            return False, "⚠️ আপনি আজকের দৈনিক ৬ কয়েন বোনাস ইতিমধ্যে গ্রহণ করেছেন! আগামীকাল পুনরায় চেষ্টা করুন।"

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

PENDING_DOWNLOADS = {}

def download_and_send_video(user_id, target_url, video_title, is_vip, status_msg_id=None):
    output_dir = f"downloads/{user_id}_{int(time.time())}"
    os.makedirs(output_dir, exist_ok=True)
    video_out = f"{output_dir}/video.mp4"

    is_youtube = ("youtu.be" in target_url or "youtube.com" in target_url)
    downloaded = False

    if is_youtube:
        try:
            downloaded = download_youtube_via_api(target_url, video_out)
        except Exception:
            downloaded = False

    if not downloaded:
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
            if files:
                video_out = files[0]
                downloaded = True
        except Exception as e:
            bot.send_message(user_id, f"⚠️ ত্রুটি: {str(e)[:120]}")
            if status_msg_id:
                try: bot.delete_message(user_id, status_msg_id)
                except Exception: pass
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            return

    if downloaded and os.path.exists(video_out):
        file_size_mb = os.path.getsize(video_out) / (1024 * 1024)
        if file_size_mb > 49.5:
            bot.send_message(user_id, "❌ ভিডিও সাইজ ৫০MB-এর বেশি হওয়ায় টেলিগ্রামে পাঠানো সম্ভব নয়।")
        else:
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

            with open(video_out, 'rb') as vf:
                bot.send_video(user_id, vf, caption=caption_text, parse_mode="HTML", supports_streaming=True)

        if status_msg_id:
            try: bot.delete_message(user_id, status_msg_id)
            except Exception: pass
    else:
        bot.send_message(user_id, "❌ ভিডিও ডাউনলোড করা সম্ভব হয়নি।")
        if status_msg_id:
            try: bot.delete_message(user_id, status_msg_id)
            except Exception: pass

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

# ৪. /start কমান্ড
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    user = get_user(user_id, username)

    membership_status = "🌟 প্রিমিয়াম মেম্বার (আনলিমিটেড)" if user[2] == 1 else "সাধারণ ব্যবহারকারী"

    intro_text = (
        f"👋 **সালাম {message.from_user.first_name}!** 🚀\n\n"
        "এই বটটি ব্যবহার করা খুবই সহজ! আপনি কেবল যেকোনো **ভিডিও লিংক চ্যাটে পাঠিয়ে দিন**, বাকি কাজ বট স্বয়ংক্রিয়ভাবে সম্পন্ন করবে।\n\n"
        "✨ **সাপোর্টেড প্ল্যাটফর্মসমূহ:**\n"
        "🔹 Facebook, TikTok, Instagram, Twitter (X)\n"
        "🔹 Pinterest, Reddit, Threads, Vimeo সহ যেকোনো পাবলিক লিংক\n\n"
        "📊 **আপনার অ্যাকাউন্ট তথ্য:**\n"
        f"• স্ট্যাটাস: **{membership_status}**\n"
        f"• বর্তমান ব্যালেন্স: `{user[1]}` কয়েন\n\n"
        "💡 **নিয়মাবলী:**\n"
        "• প্রতি ভিডিও ডাউনলোড: **২ কয়েন**\n"
        "• দৈনিক ফ্রি বোনাস: **৬ কয়েন**\n\n"
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
    bot.reply_to(message, f"🪙 আপনার বর্তমান ব্যালেন্স: **{user[1]} কয়েন**{vip_tag}", parse_mode="Markdown")

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

    admin_text = "👑 **অ্যাডমিন কন্ট্রোল ড্যাশবোর্ড**\n\nনিচের বাটনগুলোর মাধ্যমে নিয়ন্ত্রণ করুন:"
    markup = types.InlineKeyboardMarkup(row_width=2)
    b_chk = types.InlineKeyboardButton("🔍 ব্যালেন্স চেক", callback_data="adm_check")
    b_tot = types.InlineKeyboardButton("📊 মোট ব্যবহারকারী", callback_data="adm_total")
    b_add = types.InlineKeyboardButton("➕ কয়েন যোগ", callback_data="adm_add")
    b_rmv = types.InlineKeyboardButton("➖ কয়েন কাটুন", callback_data="adm_remove")
    b_vip = types.InlineKeyboardButton("💎 প্রিমিয়াম সেট", callback_data="adm_vip")
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
        bot.answer_callback_query(call.id, f"📊 মোট ব্যবহারকারী: {total_users}\n💎 প্রিমিয়াম ব্যবহারকারী: {total_vip}", show_alert=True)

    elif data == "adm_check":
        msg = bot.send_message(call.message.chat.id, "🔍 যার ব্যালেন্স চেক করবেন তার **User ID** পাঠান:")
        bot.register_next_step_handler(msg, step_check_balance)

    elif data == "adm_add":
        msg = bot.send_message(call.message.chat.id, "➕ কয়েন যোগ করার ফরম্যাট: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_add_coins)

    elif data == "adm_remove":
        msg = bot.send_message(call.message.chat.id, "➖ কয়েন কাটার ফরম্যাট: `USER_ID AMOUNT`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_remove_coins)

    elif data == "adm_vip":
        msg = bot.send_message(call.message.chat.id, "💎 প্রিমিয়াম পরিবর্তনের ফরম্যাট: `USER_ID STATUS` (১ বা ০)", parse_mode="Markdown")
        bot.register_next_step_handler(msg, step_toggle_vip)

def step_check_balance(message):
    try:
        uid = int(message.text.strip())
        u = get_user(uid)
        vip_str = "হ্যাঁ" if u[2] == 1 else "না"
        bot.reply_to(message, f"👤 ইউজার: `{uid}`\n🪙 ব্যালেন্স: **{u[1]} কয়েন**\n💎 প্রিমিয়াম: **{vip_str}**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ভুল আইডি দেওয়া হয়েছে।")

def step_add_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ ইউজার `{uid}`-এ **{amt}** কয়েন যোগ করা হয়েছে। ব্যালেন্স: **{u[1]} কয়েন**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_remove_coins(message):
    try:
        parts = message.text.strip().split()
        uid, amt = int(parts[0]), int(parts[1])
        get_user(uid)
        update_coins(uid, -amt)
        u = get_user(uid)
        bot.reply_to(message, f"✅ ইউজার `{uid}` থেকে **{amt}** কয়েন কাটা হয়েছে। ব্যালেন্স: **{u[1]} কয়েন**", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `USER_ID AMOUNT`", parse_mode="Markdown")

def step_toggle_vip(message):
    try:
        parts = message.text.strip().split()
        uid, st = int(parts[0]), int(parts[1])
        get_user(uid)
        set_premium(uid, st)
        status_txt = "💎 প্রিমিয়াম অ্যাক্টিভ করা হয়েছে।" if st == 1 else "সাধারণ মেম্বার করা হয়েছে।"
        bot.reply_to(message, f"✅ ইউজার `{uid}` {status_txt}", parse_mode="Markdown")
    except Exception:
        bot.reply_to(message, "❌ ফরম্যাট সঠিক নয়! উদাহরণ: `USER_ID STATUS` (১ বা ০)", parse_mode="Markdown")

# ৬. ভিডিও লিংক গ্রহণ (টেলিগ্রাম বট)
@bot.message_handler(func=lambda message: True)
def handle_incoming_link(message):
    raw_url = message.text.strip()

    if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক ভিডিও URL পাঠান।")
        return

    user_id = message.chat.id
    user = get_user(user_id)
    is_vip = user[2] == 1

    if not is_vip and user[1] < 2:
        bot.reply_to(message, "❌ আপনার অ্যাকাউন্টে পর্যাপ্ত কয়েন নেই!\nভিডিও ডাউনলোড করতে **২ কয়েন** প্রয়োজন।\n\n`/daily` লিখে ফ্রি ৬ কয়েন বোনাস নিন!", parse_mode="Markdown")
        return

    resolved_url = resolve_url(raw_url)

    # 💎 প্রিমিয়াম ইউজার: সরাসরি ডাউনলোড
    if is_vip:
        status_msg = bot.reply_to(message, "💎 প্রিমিয়াম অ্যাক্টিভ: ভিডিও সরাসরি প্রসেস করা হচ্ছে...")
        video_title = "Social Video"
        try:
            ydl_opts_info = {'extract_flat': False, 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(resolved_url, download=False)
                video_title = info.get('title') or "Social Video"
        except Exception:
            pass

        download_and_send_video(user_id, resolved_url, video_title, is_vip=True, status_msg_id=status_msg.message_id)
        return

    # 👤 সাধারণ ইউজার: কনফার্মেশন পপ-আপ
    status_msg = bot.reply_to(message, "🔍 ভিডিওর তথ্য অনুসন্ধান করা হচ্ছে, অপেক্ষা করুন...")
    video_title = "Social Video"
    try:
        ydl_opts_info = {'extract_flat': False, 'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(resolved_url, download=False)
            video_title = info.get('title') or info.get('description') or "Social Video"
            if len(video_title) > 200:
                video_title = video_title[:200] + "..."
    except Exception:
        pass

    PENDING_DOWNLOADS[user_id] = {
        'url': resolved_url,
        'title': video_title,
        'is_vip': False
    }

    escaped_title = html.escape(video_title)
    confirm_text = (
        f"🎬 <b>ভিডিওর বিবরণ:</b>\n\n"
        f"📝 <b>ক্যাপশন:</b>\n<code>{escaped_title}</code>\n\n"
        f"💰 <b>ডাউনলোড খরচ:</b> ২ কয়েন\n"
        f"🪙 <b>আপনার বর্তমান ব্যালেন্স:</b> {user[1]} কয়েন\n\n"
        f"আপনি কি ভিডিওটি ডাউনলোড করতে চান?"
    )

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_confirm = types.InlineKeyboardButton("✅ নিশ্চিত করুন (Confirm)", callback_data="confirm_dl")
    btn_cancel = types.InlineKeyboardButton("❌ বাতিল (Cancel)", callback_data="cancel_dl")
    markup.add(btn_confirm, btn_cancel)

    bot.edit_message_text(confirm_text, user_id, status_msg.message_id, parse_mode="HTML", reply_markup=markup)

# ৭. কনফার্মেশন বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_dl", "cancel_dl"])
def handle_download_confirmation(call):
    user_id = call.message.chat.id

    if call.data == "cancel_dl":
        PENDING_DOWNLOADS.pop(user_id, None)
        bot.edit_message_text("❌ ভিডিও ডাউনলোড বাতিল করা হয়েছে।", user_id, call.message.message_id)
        return

    task = PENDING_DOWNLOADS.get(user_id)
    if not task:
        bot.edit_message_text("⚠️ অনুরোধটির মেয়াদ শেষ হয়ে গেছে। আবার লিংক পাঠান।", user_id, call.message.message_id)
        return

    user = get_user(user_id)
    if user[1] < 2:
        bot.answer_callback_query(call.id, "❌ আপনার পর্যাপ্ত কয়েন নেই! প্রয়োজন ২ কয়েন।", show_alert=True)
        return

    bot.edit_message_text("⏳ ভিডিও ডাউনলোড ও টেলিগ্রামে প্রসেস করা হচ্ছে, অপেক্ষা করুন...", user_id, call.message.message_id)
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
        vip_tag = " (💎 প্রিমিয়াম মেম্বার)" if user[2] == 1 else ""
        bot.answer_callback_query(call.id, text=f"🪙 আপনার ব্যালেন্স: {user[1]} কয়েন{vip_tag}", show_alert=True)

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
