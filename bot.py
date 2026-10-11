import os
import glob
import time
import shutil
import threading
from flask import Flask
import telebot
import yt_dlp

# ১. Render Web Service যাতে পোর্ট ফেইল না করে
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট সেটআপ
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        f"👋 হ্যালো, {message.from_user.first_name}!\n\n"
        "ভিডিও ডাউনলোডার বট চালু আছে। যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান, "
        "আমি ডাউনলোড করে পাঠিয়ে দেব।"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "সরাসরি যেকোনো ভিডিওর লিঙ্ক পাঠান। টেলিগ্রামের সর্বোচ্চ ফাইল সাইজ ৫০MB।")

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

    # yt-dlp সেটিংস ('The page needs to be reloaded' বাইপাস করতে অ্যান্ড্রয়েড ক্লায়েন্ট ব্যবহার)
    ydl_opts = {
        'format': 'bestvideo[filesize<35M]+bestaudio[filesize<10M]/best[filesize<48M]/best',
        'merge_output_format': 'mp4',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
                'player_skip': ['webpage', 'configs']
            }
        }
    }

    # FFmpeg পাওয়া গেলে যুক্ত করা
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
        bot.edit_message_text("📤 ভিডিও টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ এরর: {str(e)[:120]}", user_id, status_msg.message_id)

    finally:
        # কাজ শেষে ডাউনলোড ফাইল ও ফোল্ডার ডিলিট করা
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    # Flask ওয়েব সার্ভার আলাদা থ্রেডে চালু করা
    threading.Thread(target=run_web_server, daemon=True).start()

    # পুরনো সেশনের কনফ্লিক্ট সরানো
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception:
        pass

    print("Bot is successfully listening...")

    # সেশন কনফ্লিক্ট (409) ও রিলোড হ্যান্ডলার
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=20)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 409:
                print("সেশন কনফ্লিক্ট হয়েছে। পুরনো সেশন বন্ধ হতে ৫ সেকেন্ড অপেক্ষা করা হচ্ছে...")
                time.sleep(5)
            else:
                print(f"টেলিগ্রাম এরর: {e}")
                time.sleep(3)
        except Exception as e:
            print(f"অপ্রত্যাশিত ত্রুটি: {e}")
            time.sleep(3)
