import os
import glob
import time
import shutil
import threading
from flask import Flask
import telebot
import yt_dlp

# ১. Render পোর্ট ফেইল ঠেকানোর ডামি ওয়েব সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is healthy and live!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env variable not set!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(
        message, 
        f"👋 হ্যালো {message.from_user.first_name}! যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান, ডাউনলোড করে দেব।"
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "সরাসরি লিঙ্ক পেস্ট করুন। টেলিগ্রাম লিমিট সর্বোচ্চ ৫০MB।")

@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ একটি সঠিক ভিডিও URL দিন।")
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিও যাচাই ও ডাউনলোড হচ্ছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    # yt-dlp পারফেক্ট অ্যান্টি-বট কনফিগারেশন
    ydl_opts = {
        'format': 'bestvideo[filesize<35M]+bestaudio[filesize<10M]/best[filesize<48M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        # একাধিক ক্লায়েন্ট ফলব্যাক (iOS, Android, TV) যাতে ডেটাসেন্টার আইপি ব্লক এড়িয়ে যায়
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'tv_embedded'],
                'player_skip': ['webpage']
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.ios.youtube/19.29.1 (iPhone14,3; U; CPU iOS 17_5_1 like Mac OS X; en_US)',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }

    if FFMPEG_DIR:
        ydl_opts['ffmpeg_location'] = FFMPEG_DIR

    # cookies.txt ফাইল থাকলে লোড করা
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = 'cookies.txt'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        downloaded_files = glob.glob(f"{output_dir}/*")
        if not downloaded_files:
            bot.edit_message_text(
                "❌ ফাইল পাওয়া যায়নি বা ফাইলের সাইজ ৫০MB-এর বেশি।", 
                user_id, 
                status_msg.message_id
            )
            return

        file_path = downloaded_files[0]
        bot.edit_message_text("📤 ভিডিও টেলিগ্রামে পাঠানো হচ্ছে...", user_id, status_msg.message_id)

        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ এরর: {str(e)[:120]}", user_id, status_msg.message_id)

    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()

    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    print("Bot is successfully listening...")

    # কনফ্লিক্ট (409) রিকভারি লুপ
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
