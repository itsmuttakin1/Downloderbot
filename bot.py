import os
import glob
import shutil
import threading
from flask import Flask
import telebot
import yt_dlp

# ১. Render-এর পোর্টের জন্য ডামি ওয়েব সার্ভার (সার্ভিস ফেইল হওয়া ঠেকাবে)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running healthy!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN এনভায়রনমেন্ট ভ্যারিয়েবল সেট করা হয়নি!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        f"👋 হ্যালো, {message.from_user.first_name}!\n\n"
        "ভিডিও ডাউনলোডার বটে স্বাগতম। যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান, "
        "আমি ডাউনলোড করে দেব।"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "ভিডিওর লিঙ্ক সরাসরি চ্যাটে পাঠান। টেলিগ্রামের সর্বোচ্চ সাইজ লিমিট ৫০MB।")

@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক URL দিন।")
        return

    status_msg = bot.reply_to(message, "⏳ প্রসেসিং চলছে, অপেক্ষা করুন...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        'format': 'bestvideo[filesize<35M]+bestaudio[filesize<10M]/best[filesize<48M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
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
        bot.edit_message_text("📤 টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ এরর: {str(e)[:100]}", user_id, status_msg.message_id)

    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    # পোর্টের জন্য সার্ভার ব্যাকগ্রাউন্ড থ্রেডে স্টার্ট করা
    threading.Thread(target=run_web_server, daemon=True).start()

    # পুরনো সেশনের কনফ্লিক্ট এড়িয়ে চলা
    try:
        bot.remove_webhook()
    except Exception:
        pass

    print("Bot is successfully listening...")
    # skip_pending=True দিলে ৪০৯ কনফ্লিক্ট হবে না
    bot.infinity_polling(skip_pending=True)
