import os
import telebot
from flask import Flask, request, abort
from datetime import datetime
import pytz
import threading
import time

# ====================== 配置 ======================
TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set!")

print(f"DEBUG: Bot starting with TOKEN (first 10 chars): {TOKEN[:10]}...")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 所有机器人所在的群（只要机器人收到消息就会自动加入）
active_chats = set()

# ====================== 后台定时器（每30秒检查一次） ======================
def background_timer():
    while True:
        try:
            tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
            now = datetime.now(tz)
            today = now.date()

            for chat_id in list(active_chats):
                try:
                    # 开始下注提醒
                    start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
                    if (now.hour > start_h or (now.hour == start_h and now.minute >= start_m)):
                        if chat_id not in last_start_date or last_start_date[chat_id] != today:
                            bot.send_message(chat_id, "✅ 开始下注")
                            last_start_date[chat_id] = today
                            print(f"[{now.strftime('%H:%M')}] ✅ 开始下注 | ChatID: {chat_id}")

                    # 即将结束提醒
                    pre_end_h, pre_end_m = map(int, os.environ.get('WORK_AEND', '21:00').split(':'))
                    if (now.hour > pre_end_h or (now.hour == pre_end_h and now.minute >= pre_end_m)):
                        if chat_id not in last_pre_end_date or last_pre_end_date[chat_id] != today:
                            bot.send_message(chat_id, "⛔ 即将结束500以上请勿报入")
                            last_pre_end_date[chat_id] = today
                            print(f"[{now.strftime('%H:%M')}] ⛔ 即将结束提醒 | ChatID: {chat_id}")

                except:
                    continue
        except Exception as e:
            print(f"定时器错误: {e}")

        time.sleep(30)


# 全局变量定义
last_start_date = {}
last_pre_end_date = {}

# 启动后台定时器
timer_thread = threading.Thread(target=background_timer, daemon=True)
timer_thread.start()

# ====================== 消息处理（仅转发 + 自动激活群） ======================
def handle_message(message):
    chat_id = message.chat.id

    # 自动把所有机器人所在的群加入活跃列表（关键！）
    active_chats.add(chat_id)

    # ====================== 到期检查 ======================
    tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
    now = datetime.now(tz)

    try:
        expiry_str = os.environ.get('EXPIRY_DATE')
        if expiry_str and now.date() > datetime.strptime(expiry_str, '%Y-%m-%d').date():
            return
    except:
        return

    # ====================== 工作时间检查 ======================
    try:
        start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
        end_h, end_m = map(int, os.environ['WORK_END'].split(':'))
        current_h, current_m = now.hour, now.minute
        is_work_time = (
            (current_h > start_h or (current_h == start_h and current_m >= start_m)) and
            (current_h < end_h or (current_h == end_h and current_m <= end_m))
        )
        if not is_work_time:
            return
    except:
        return

    if message.chat.type not in ['group', 'supergroup'] or message.from_user.is_bot:
        return

    # ====================== 干净转发 ======================
    try:
        bot.forward_message(
            chat_id=chat_id,
            from_chat_id=chat_id,
            message_id=message.message_id
        )
        print(f"已成功转发消息 | Chat: {message.chat.title or 'Private'}")
    except Exception as e:
        print(f"转发失败: {e}")


# ====================== Webhook ======================
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
    return "Bot is running! (Auto Reminder in All Groups)"


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
