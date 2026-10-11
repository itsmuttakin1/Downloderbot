import os
import glob
import time
import shutil
import threading
from flask import Flask
import telebot
import yt_dlp

# ১. Render পোর্টের জন্য ডামি সার্ভার (Web Service সচল রাখতে)
app = Flask(__name__)

@app.route('/')
def home():
    return "Social Downloader Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        f"👋 হ্যালো, {message.from_user.first_name}!\n\n"
        "আমি সোশ্যাল মিডিয়া ডাউনলোডার বট। আমাকে লিঙ্ক পাঠান:\n"
        "• Facebook (Reels/Videos)\n"
        "• Instagram (Reels/Posts)\n"
        "• TikTok (Watermark ছাড়া)\n"
        "• Pinterest (Pins/Videos)\n\n"
        "আমি ভিডিও ডাউনলোড করে পাঠিয়ে দেব।"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "যেকোনো FB, TikTok, Insta বা Pinterest ভিডিওর লিঙ্ক পেস্ট করুন। টেলিগ্রামের সর্বোচ্চ সাইজ লিমিট ৫০MB।")

@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক URL দিন।")
        return

    # ইউটিউব লিঙ্ক আসলে ভদ্রভাবে জানিয়ে দেওয়া
    if "youtu" in url:
        bot.reply_to(message, "⚠️ দুঃখিত! এই বটে শুধুমাত্র Facebook, TikTok, Instagram এবং Pinterest সাপোর্ট করে।")
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিও সংগ্রহ করা হচ্ছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    # FB, Insta, TikTok, Pinterest এর জন্য নির্ভরযোগ্য কনফিগারেশন
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
            ydl.download([url])

        downloaded_files = glob.glob(f"{output_dir}/*")
        if not downloaded_files:
            bot.edit_message_text(
                "❌ ফাইল পাওয়া যায়নি বা সাইজ ৫০MB-এর বেশি।", 
                user_id, 
                status_msg.message_id
            )
            return

        file_path = downloaded_files[0]
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if file_size_mb > 49.5:
            bot.edit_message_text("❌ ভিডিওটির সাইজ ৫০MB-এর বেশি, টেলিগ্রামে পাঠানো সম্ভব নয়।", user_id, status_msg.message_id)
            return

        bot.edit_message_text("📤 টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ এরর: {str(e)[:120]}", user_id, status_msg.message_id)

    finally:
        # প্রসেসিং শেষে লোকাল ফাইল ক্লিয়ার করা
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
