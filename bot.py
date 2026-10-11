import os
import glob
import shutil
import telebot
import yt_dlp

# এনভায়রনমেন্ট ভ্যারিয়েবল থেকে টোকেন নেওয়া
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN এনভায়রনমেন্ট ভ্যারিয়েবল সেট করা হয়নি!")

bot = telebot.TeleBot(BOT_TOKEN)

# Render বা লোকাল সিস্টেমে FFmpeg লোকেশন চেক
FFMPEG_DIR = os.path.abspath("ffmpeg_bin") if os.path.exists("ffmpeg_bin") else None

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        f"👋 হ্যালো, {message.from_user.first_name}!\n\n"
        "আমি একটি ভিডিও ডাউনলোডার বট। আমাকে যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান, "
        "আমি সেটি ডাউনলোড করে টেলিগ্রামে পাঠিয়ে দেব।\n\n"
        "কমান্ড দেখতে টাইপ করুন: /help"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📌 **কীভাবে ব্যবহার করবেন:**\n"
        "১. যেকোনো Facebook বা YouTube ভিডিওর লিঙ্ক কপি করুন।\n"
        "২. চ্যাটে লিঙ্কটি পেস্ট করে সেন্ড করুন।\n\n"
        "⚠️ **সীমাবদ্ধতা:**\n"
        "- টেলিগ্রামের ফাইল সাইজ লিমিট সর্বোচ্চ ৫০MB।\n"
        "- প্রাইভেট বা রেস্ট্রিক্টেড ভিডিও ডাউনলোড হবে না।"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['about'])
def about_command(message):
    about_text = (
        "🤖 **ভিডিও ডাউনলোডার বট**\n"
        "- ইঞ্জিন: `yt-dlp` & `FFmpeg`\n"
        "- হোস্টিং: Render Cloud\n"
        "- সাপোর্ট: YouTube, Facebook, Reels, Shorts"
    )
    bot.reply_to(message, about_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def process_video_link(message):
    url = message.text.strip()

    # লিঙ্ক ভ্যালিডেশন
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "⚠️ দয়া করে একটি সঠিক ভিডিও URL পাঠান।")
        return

    status_msg = bot.reply_to(message, "⏳ ভিডিওর তথ্য যাচাই ও ডাউনলোড করা হচ্ছে...")
    user_id = message.chat.id
    output_dir = f"downloads/{user_id}"
    os.makedirs(output_dir, exist_ok=True)

    # yt-dlp কনফিগারেশন
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

        # ডাউনলোড হওয়া ফাইল খোঁজা
        downloaded_files = glob.glob(f"{output_dir}/*")
        if not downloaded_files:
            bot.edit_message_text(
                "❌ ভিডিও ডাউনলোড করা সম্ভব হয়নি। ভিডিওর সাইজ ৫০MB-এর বেশি হতে পারে।",
                user_id,
                status_msg.message_id
            )
            return

        file_path = downloaded_files[0]
        bot.edit_message_text("📤 ভিডিও টেলিগ্রামে আপলোড হচ্ছে...", user_id, status_msg.message_id)

        # ভিডিও সেন্ড করা
        with open(file_path, 'rb') as video_file:
            bot.send_video(user_id, video_file, supports_streaming=True)

        bot.delete_message(user_id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"⚠️ ত্রুটি ঘটেছে: {str(e)[:120]}", user_id, status_msg.message_id)

    finally:
        # ডাউনলোড শেষ হলে ফাইল এবং ফোল্ডার মুছে ফেলা
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == "__main__":
    print("Bot is active and running...")
    bot.infinity_polling()
