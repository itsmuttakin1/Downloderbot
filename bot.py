import os
import glob
import shutil
import threading
from flask import Flask
import telebot
import yt_dlp

# Render Web Service পোর্ট ম্যানেজমেন্ট
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running healthy!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN এনভায়রনমেন্ট ভ্যারিয়েবল সেট করা হয়নি!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        f"👋 হ্যালো, {message.from_user.first_name}!\n\n"
        "ভিডিও ডাউনলোডার বট চালু আছে। যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান।"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "সরাসরি লিঙ্ক পেস্ট করুন। টেলিগ্রামের সর্বোচ্চ ফাইল সাইজ ৫০MB।")

@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক URL দিন।")
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিও যাচাই ও ডাউনলোড হচ্ছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    # yt-dlp অপশন কনফিগারেশন
    ydl_opts = {
        'format': 'bestvideo[filesize<35M]+bestaudio[filesize<10M]/best[filesize<48M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    # FFmpeg লোকেশন যুক্ত করা
    if FFMPEG_DIR:
        ydl_opts['ffmpeg_location'] = FFMPEG_DIR

    # কুকিজ ফাইল যুক্ত করা (বট ডিটেকশন ও সাইন-ইন বাইপাস)
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = 'cookies.txt'

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
        bot.edit_message_text("📤 ভিডিও টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

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
    except Exception:
        pass

    print("Bot is successfully listening...")
    bot.infinity_polling(skip_pending=True)
