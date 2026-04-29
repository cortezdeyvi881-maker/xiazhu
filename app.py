import os
import telebot
from flask import Flask, request, abort
from datetime import datetime
import pytz

# ====================== 配置 ======================
TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set!")

print(f"DEBUG: Bot starting with TOKEN (first 10 chars): {TOKEN[:10]}...")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 记录每个群当天是否已发过提醒
last_start_date = {}
last_pre_end_date = {}

# ====================== 核心处理函数 ======================
def handle_message(message):
    chat_id = message.chat.id
    tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
    now = datetime.now(tz)
    today = now.date()

    # ====================== 定时提醒（新需求） ======================
    try:
        # 开始下注提醒
        start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
        if last_start_date.get(chat_id) != today and \
           (now.hour > start_h or (now.hour == start_h and now.minute >= start_m)):
            bot.send_message(chat_id, "✅ 开始下注")
            last_start_date[chat_id] = today
            print(f"[{now.strftime('%H:%M')}] ✅ 已发送：开始下注 | ChatID: {chat_id}")

        # 即将结束提醒
        pre_end_h, pre_end_m = map(int, os.environ['WORK_AEND'].split(':'))
        if last_pre_end_date.get(chat_id) != today and \
           (now.hour > pre_end_h or (now.hour == pre_end_h and now.minute >= pre_end_m)):
            bot.send_message(chat_id, "⛔ 即将结束500以上请勿报入")
            last_pre_end_date[chat_id] = today
            print(f"[{now.strftime('%H:%M')}] ⛔ 已发送：即将结束提醒 | ChatID: {chat_id}")

    except Exception as e:
        print(f"定时提醒出错: {e}")

    # ====================== 到期检查 ======================
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

    # ====================== 转发（原有核心功能） ======================
    if message.chat.type not in ['group', 'supergroup'] or message.from_user.is_bot:
        return

    try:
        bot.forward_message(
            chat_id=chat_id,
            from_chat_id=chat_id,
            message_id=message.message_id
        )
        print(f"✅ 已成功转发消息 | Chat: {
