import os
import glob
import time
import shutil
import threading
import requests
from flask import Flask
import telebot
import yt_dlp

# ১. Render পোর্ট লাইভ রাখার জন্য Flask সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

def download_via_cobalt(url, output_path):
    """ইউটিউব আইপি ব্লক এড়াতে অল্টারনেটিভ API দিয়ে ডাউনলোড"""
    api_url = "https://api.cobalt.tools/api/json"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "url": url,
        "vQuality": "720",
        "filenamePattern": "basic"
    }
    
    res = requests.post(api_url, json=payload, headers=headers, timeout=20)
    data = res.json()
    
    if "url" in data:
        # সরাসরি ভিডিও ফাইল ডাউনলোড করা
        stream_res = requests.get(data["url"], stream=True, timeout=60)
        with open(output_path, 'wb') as f:
            for chunk in stream_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        return True
    return False

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.reply_to(message, "👋 স্বাগতম! যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান, ডাউনলোড করে পাঠিয়ে দেব।")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, "সরাসরি লিঙ্ক দিন। টেলিগ্রামের সর্বোচ্চ ফাইল সাইজ ৫০MB।")

@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    url = message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে সঠিক লিঙ্ক পাঠান।")
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিও সংগ্রহ করা হচ্ছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)
    video_file_path = f"{output_dir}/video.mp4"

    downloaded = False

    # ধাপ ১: ইউটিউব লিঙ্কের জন্য সরাসরি এপিআই দিয়ে চেষ্টা (আইপি ব্লক বাইপাস)
    if "youtu" in url:
        try:
            bot.edit_message_text("⚡ সার্ভার বাইপাস দিয়ে ডাউনলোড শুরু হচ্ছে...", user_id, status_msg.message_id)
            if download_via_cobalt(url, video_file_path):
                downloaded = True
        except Exception:
            downloaded = False

    # ধাপ ২: যদি এপিআই কাজ না করে বা ফেসবুকের লিঙ্ক হয়, তবে yt-dlp চালানো
    if not downloaded:
        bot.edit_message_text("⏳ ডাউনলোডার দিয়ে প্রসেস করা হচ্ছে...", user_id, status_msg.message_id)
        ydl_opts = {
            'format': 'best[filesize<48M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
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
            files = glob.glob(f"{output_dir}/*")
            if files:
                video_file_path = files[0]
                downloaded = True
        except Exception as e:
            bot.edit_message_text(f"⚠️ ত্রুটি: {str(e)[:120]}", user_id, status_msg.message_id)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            return

    # ধাপ ৩: টেলিগ্রামে ভিডিও পাঠানো
    if downloaded and os.path.exists(video_file_path):
        # ৫০MB চেক
        file_size_mb = os.path.getsize(video_file_path) / (1024 * 1024)
        if file_size_mb > 49.5:
            bot.edit_message_text("❌ ভিডিওটির সাইজ ৫০MB-এর বেশি, টেলিগ্রামে পাঠানো সম্ভব নয়।", user_id, status_msg.message_id)
        else:
            bot.edit_message_text("📤 টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)
            with open(video_file_path, 'rb') as vf:
                bot.send_video(user_id, vf, supports_streaming=True)
            bot.delete_message(user_id, status_msg.message_id)
    else:
        bot.edit_message_text("❌ ভিডিও ডাউনলোড করা সম্ভব হয়নি।", user_id, status_msg.message_id)

    # ক্যাশ পরিষ্কার
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
