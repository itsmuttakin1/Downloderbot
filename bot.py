import os
import glob
import time
import shutil
import threading
import requests
from flask import Flask
import telebot
import yt_dlp

# ১. Render পোর্টের জন্য ওয়েব সার্ভার
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ২. টেলিগ্রাম বট কনফিগারেশন
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing!")

bot = telebot.TeleBot(BOT_TOKEN)
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

def download_youtube_stream(url, output_path):
    """
    Render-এর আইপি ব্লক এড়াতে মাল্টিপল পাবলিক ইনস্ট্যান্স ট্রাই করা
    """
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
            if r.status_code != 200:
                continue
            data = r.json()
            video_url = data.get("url")
            if video_url:
                with requests.get(video_url, stream=True, timeout=60) as dl_res:
                    dl_res.raise_for_status()
                    with open(output_path, "wb") as f:
                        for chunk in dl_res.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                return True
        except Exception:
            continue
    return False

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "ভিডিওর লিঙ্ক পাঠান (YouTube বা Facebook), ডাউনলোড করে দিচ্ছি।")

@bot.message_handler(commands=['help'])
def help(message):
    bot.reply_to(message, "সরাসরি লিঙ্ক পেস্ট করুন। টেলিগ্রামের সর্বোচ্চ সাইজ লিমিট ৫০MB।")

@bot.message_handler(func=lambda message: True)
def process_video(message):
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "সঠিক লিঙ্ক দিন।")
        return

    status = bot.reply_to(message, "⏳ প্রসেসিং চলছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)
    video_path = f"{output_dir}/video.mp4"

    is_downloaded = False

    # YouTube হলে থার্ড পার্টি স্ট্রিম ইঞ্জিন (Render IP বাইপাস)
    if "youtu" in url:
        bot.edit_message_text("⚡ YouTube বাইপাস ইঞ্জিন দিয়ে ডাউনলোড হচ্ছে...", user_id, status.message_id)
        if download_youtube_stream(url, video_path):
            is_downloaded = True

    # Facebook বা YouTube ফেইল করলে yt-dlp
    if not is_downloaded:
        bot.edit_message_text("⏳ ডাউনলোডার ইঞ্জিন চালানো হচ্ছে...", user_id, status.message_id)
        ydl_opts = {
            'format': 'best[filesize<48M]/bestvideo[filesize<35M]+bestaudio[filesize<10M]/best',
            'merge_output_format': 'mp4',
            'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }
        if FFMPEG_DIR:
            ydl_opts['ffmpeg_location'] = FFMPEG_DIR
        
        # কুকি থাকলে লোড করা
        if os.path.exists("cookies.txt"):
            ydl_opts['cookiefile'] = "cookies.txt"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            files = glob.glob(f"{output_dir}/*")
            if files:
                video_path = files[0]
                is_downloaded = True
        except Exception as e:
            bot.edit_message_text(f"ত্রুটি: {str(e)[:120]}", user_id, status.message_id)
            if os.path.exists(output_dir):
                shutil.rmtree(output_dir, ignore_errors=True)
            return

    # টেলিগ্রামে ফাইল আপলোড
    if is_downloaded and os.path.exists(video_path):
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if size_mb > 49.5:
            bot.edit_message_text("❌ ভিডিওটির সাইজ ৫০MB-এর বেশি। টেলিগ্রামে পাঠানো যাবে না।", user_id, status.message_id)
        else:
            bot.edit_message_text("📤 টেলিগ্রামে আপলোড হচ্ছে...", user_id, status.message_id)
            with open(video_path, 'rb') as f:
                bot.send_video(user_id, f, supports_streaming=True)
            bot.delete_message(user_id, status.message_id)
    else:
        bot.edit_message_text("❌ ভিডিও সংগ্রহ করা যায়নি।", user_id, status.message_id)

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
