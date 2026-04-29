import os
import telebot
from flask import Flask, request, abort
from datetime import datetime
import pytz
import threading
import time

TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set!")

print(f"DEBUG: Bot starting with TOKEN (first 10 chars): {TOKEN[:10]}...")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

active_chats = set()
last_start_date = {}
last_pre_end_date = {}

# ====================== 后台自动定时器 ======================
def background_timer():
    while True:
        try:
            tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
            now = datetime.now(tz)
            today = now.date()

            for chat_id in list(active_chats):
                try:
                    # 开始下注
                    start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
                    if last_start_date.get(chat_id) != today and (now.hour > start_h or (now.hour == start_h and now.minute >= start_m)):
                        bot.send_message(chat_id, "✅ 开始下注")
                        last_start_date[chat_id] = today

                    # 即将结束提醒
                    pre_end_h, pre_end_m = map(int, os.environ['WORK_AEND'].split(':'))
                    if last_pre_end_date.get(chat_id) != today and (now.hour > pre_end_h or (now.hour == pre_end_h and now.minute >= pre_end_m)):
                        bot.send_message(chat_id, "⛔ 即将结束500以上请勿报入")
                        last_pre_end_date[chat_id] = today
                except:
                    continue
        except:
            pass
        time.sleep(30)

threading.Thread(target=background_timer, daemon=True).start()

# ====================== 消息处理（仅转发） ======================
def handle_message(message):
    chat_id = message.chat.id
    active_chats.add(chat_id)   # 记录群组

    if message.chat.type not in ['group', 'supergroup'] or message.from_user.is_bot:
        return

    try:
        bot.forward_message(chat_id, chat_id, message.message_id)
    except:
        pass


@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        if update.message:
            handle_message(update.message)
        return '', 200
    abort(403)


@app.route('/')
def index():
    return "Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
