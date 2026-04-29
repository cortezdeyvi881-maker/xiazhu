import os
import telebot
from flask import Flask, request, abort
from datetime import datetime
import pytz

# ====================== 配置 & 启动打印 ======================
TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set!")

print(f"DEBUG: Bot starting with TOKEN (first 10 chars): {TOKEN[:10]}...")

# ====================== 启动时打印所有时间相关环境变量 ======================
print("\n=== 时间配置信息（启动检查） ===")
print(f"WORK_START     : {os.environ.get('WORK_START')}")
print(f"WORK_END       : {os.environ.get('WORK_END')}")
print(f"WORK_AEND      : {os.environ.get('WORK_AEND')}")
print(f"WORK_TIMEZONE  : {os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai')}")
print(f"EXPIRY_DATE    : {os.environ.get('EXPIRY_DATE')}")
print("================================\n")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

last_start_date = {}
last_pre_end_date = {}

# ====================== 核心处理函数 ======================
def handle_message(message):
    chat_id = message.chat.id
    tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
    now = datetime.now(tz)
    today = now.date()

    # ====================== 定时提醒（收到消息时检查时间） ======================
    try:
        # 开始下注提醒
        start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
        if last_start_date.get(chat_id) != today and \
           (now.hour > start_h or (now.hour == start_h and now.minute >= start_m)):
            bot.send_message(chat_id, "✅ 开始下注")
            last_start_date[chat_id] = today
            print(f"[{now.strftime('%H:%M')}] ✅ 已发送：开始下注")

        # 即将结束提醒
        pre_end_h, pre_end_m = map(int, os.environ['WORK_AEND'].split(':'))
        if last_pre_end_date.get(chat_id) != today and \
           (now.hour > pre_end_h or (now.hour == pre_end_h and now.minute >= pre_end_m)):
            bot.send_message(chat_id, "⛔ 即将结束500以上请勿报入")
            last_pre_end_date[chat_id] = today
            print(f"[{now.strftime('%H:%M')}] ⛔ 已发送：即将结束提醒")
    except Exception as e:
        print(f"提醒检查出错: {e}")

    # ====================== 工作时间检查 + 转发 ======================
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

    # 干净转发
    try:
        bot.forward_message(chat_id, chat_id, message.message_id)
        print(f"✅ 已成功转发消息 | Chat: {message.chat.title or 'Private'}")
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
    return "Bot is running!"


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
