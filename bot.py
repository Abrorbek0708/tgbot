import os
import re
import time
import threading

import telebot
from telebot import types
import yt_dlp

bot = telebot.TeleBot("8534806219:AAFe47NU2cGZeCsGKESWkB7rOc6sxZMiR8A", threaded=False)


def main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("ℹ️ Biz haqimizda")
    keyboard.row("📞 Aloqa")
    return keyboard


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "Instagram, YouTube yoki Pinterest havolasini yuboring — men videoni yuklab beraman:",
        reply_markup=main_menu()
    )


active_status_threads = {}


def animate_status(chat_id, message_id, stop_event):
    frames = ["⏳ Video yuklanmoqda.", "⏳ Video yuklanmoqda..", "⏳ Video yuklanmoqda..."]
    index = 0
    while not stop_event.is_set():
        try:
            bot.edit_message_text(frames[index], chat_id, message_id)
        except Exception:
            pass
        index = (index + 1) % len(frames)
        stop_event.wait(1)


@bot.message_handler(func=lambda message: re.search(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am|youtu\.be|youtube\.com|pinterest\.com|pin\.it)/",
    message.text or ""
))
def download_video(message):
    url = message.text.strip()
    bot.send_chat_action(message.chat.id, "upload_video")
    status_message = bot.send_message(message.chat.id, "⏳ Video yuklanmoqda...")
    status_stop = threading.Event()
    active_status_threads[message.chat.id] = status_stop
    status_thread = threading.Thread(
        target=animate_status,
        args=(message.chat.id, status_message.message_id, status_stop),
        daemon=True
    )
    status_thread.start()

    os.makedirs("downloads", exist_ok=True)
    output_template = os.path.join("downloads", f"{message.chat.id}_%(id)s.%(ext)s")
    options = {
        "outtmpl": output_template,
        "format": "bv*[ext=mp4][height<=720]+ba[ext=m4a]/b[ext=mp4]/b/best",
        "noplaylist": True,
        "max_filesize": 50 * 1024 * 1024,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
            filepath = downloader.prepare_filename(info)

            if filepath.endswith(".webm"):
                filepath = os.path.splitext(filepath)[0] + ".mp4"

            if not os.path.exists(filepath):
                matches = [name for name in os.listdir("downloads") if name.startswith(f"{message.chat.id}_")]
                if matches:
                    filepath = os.path.join("downloads", matches[-1])

        if not os.path.isfile(filepath):
            raise FileNotFoundError("Yuklangan video fayli topilmadi")

        if os.path.getsize(filepath) > 50 * 1024 * 1024:
            raise ValueError("Video 50 MB dan katta")

        send_video_with_retry(message.chat.id, filepath)

    except Exception as error:
        bot.reply_to(message, f"Videoni yuklab bo‘lmadi: {error}")

    finally:
        status_stop.set()
        try:
            bot.delete_message(message.chat.id, status_message.message_id)
        except Exception:
            pass

        for name in os.listdir("downloads"):
            if name.startswith(f"{message.chat.id}_"):
                try:
                    os.remove(os.path.join("downloads", name))
                except OSError:
                    pass


def send_video_with_retry(chat_id, filepath):
    last_error = None

    for attempt in range(3):
        try:
            with open(filepath, "rb") as video:
                bot.send_video(chat_id, video, timeout=60)
            return
        except Exception as error:
            last_error = error
            time.sleep(2)

    with open(filepath, "rb") as video:
        bot.send_document(chat_id, video, timeout=60)


@bot.message_handler(func=lambda message: message.text == "📞 Aloqa")
def contact(message):
    bot.send_message(message.chat.id, "Aloqa uchun: @brorbe")


@bot.message_handler(func=lambda message: True)
def other_text(message):
    bot.reply_to(message, "Instagram, YouTube  videolarining havolasini yuboring.")


bot.infinity_polling()
