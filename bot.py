import os
import glob
import telebot
import yt_dlp

# Environment Variable থেকে টোকেন নেওয়া
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "স্বাগতম! আমাকে যেকোনো YouTube বা Facebook ভিডিওর লিঙ্ক পাঠান, আমি ডাউনলোড করে পাঠিয়ে দেব।"
    )

@bot.message_handler(func=lambda message: True)
def handle_video(message):
    url = message.text.strip()
    
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "দয়া করে একটি সঠিক ভিডিও লিঙ্ক পাঠান।")
        return

    status_msg = bot.reply_to(message, "ভিডিও প্রসেস করা হচ্ছে, অপেক্ষা করুন...")
    
    # 50MB এর নিচে 720p/বেস্ট কোয়ালিটি ডাউনলোড অপশন (Telegram Bot API limit ~50MB)
    ydl_opts = {
        'format': 'best[filesize<48M]/best[ext=mp4]/best',
        'outtmpl': f'downloads/{message.chat.id}_%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        os.makedirs("downloads", exist_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # ডাউনলোড করা ফাইলটি খোঁজা
        matching_files = glob.glob(f"downloads/{message.chat.id}_*")
        if not matching_files:
            bot.edit_message_text("ভিডিও ডাউনলোড করা সম্ভব হয়নি বা সাইজ ৫০MB-এর বেশি।", message.chat.id, status_msg.message_id)
            return

        file_path = matching_files[0]
        bot.edit_message_text("ভিডিও টেলিগ্রামে আপলোড হচ্ছে...", message.chat.id, status_msg.message_id)
        
        with open(file_path, 'rb') as video_file:
            bot.send_video(message.chat.id, video_file, supports_streaming=True)

        bot.delete_message(message.chat.id, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"ত্রুটি ঘটেছে: {str(e)[:100]}", message.chat.id, status_msg.message_id)
    
    finally:
        # স্টোরেজ খালি করার জন্য ফাইল মুছে ফেলা
        for f in glob.glob(f"downloads/{message.chat.id}_*"):
            try:
                os.remove(f)
            except OSError:
                pass

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
