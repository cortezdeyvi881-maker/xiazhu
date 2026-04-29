import os
import telebot
from flask import Flask, request, abort
from datetime import datetime
import pytz
import threading
import time

# ====================== 配置 & 启动打印 ======================
TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set!")
print(f"DEBUG: Bot starting with TOKEN (first 10 chars): {TOKEN[:10]}...")

# ====================== 启动时打印所有时间相关环境变量 ======================
print("\n=== 时间配置信息（启动检查） ===")
print(f"WORK_START : {os.environ.get('WORK_START')}")
print(f"WORK_END : {os.environ.get('WORK_END')}")
print(f"WORK_AEND : {os.environ.get('WORK_AEND')}")
print(f"WORK_TIMEZONE : {os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai')}")
print(f"EXPIRY_DATE : {os.environ.get('EXPIRY_DATE')}")
print("================================\n")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ====================== 全局变量 ======================
last_start_date = {}      # chat_id -> date
last_pre_end_date = {}    # chat_id -> date
active_chats = set()

# ====================== 时区 & 时间配置缓存（关键修复！） ======================
# 避免在多线程 + Gunicorn 环境下反复调用 pytz.timezone() 导致死锁/超时
WORK_TIMEZONE_STR = os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai')
try:
    TZ = pytz.timezone(WORK_TIMEZONE_STR)
    print(f"✅ 时区已成功缓存: {WORK_TIMEZONE_STR}")
except Exception as e:
    print(f"❌ 时区设置错误，使用 Asia/Shanghai 作为 fallback: {e}")
    TZ = pytz.timezone('Asia/Shanghai')

# 预解析工作时间（避免每次检查都 split + map）
try:
    START_H, START_M = map(int, os.environ['WORK_START'].split(':'))
    END_H, END_M = map(int, os.environ['WORK_END'].split(':'))
    PRE_END_H, PRE_END_M = map(int, os.environ['WORK_AEND'].split(':'))
    print(f"✅ 工作时间已缓存: {START_H:02d}:{START_M:02d} ~ {END_H:02d}:{END_M:02d} (提前结束提醒 {PRE_END_H:02d}:{PRE_END_M:02d})")
except Exception as e:
    print(f"❌ WORK_START / WORK_END / WORK_AEND 格式错误: {e}")
    START_H, START_M = 9, 0
    END_H, END_M = 23, 0
    PRE_END_H, PRE_END_M = 22, 30

# ====================== 核心提醒函数 ======================
def check_and_send_reminders(chat_id=None):
    """
    检查当前时间是否到达提醒时间点，如果是则发送提醒。
    使用缓存的 TZ 对象，避免 pytz 死锁问题。
    """
    now = datetime.now(TZ)          # ← 使用缓存的时区对象
    today = now.date()

    if chat_id is None:
        chats_to_check = list(active_chats)
    else:
        chats_to_check = [chat_id]

    for cid in chats_to_check:
        try:
            # === 开始下注提醒 ===
            if last_start_date.get(cid) != today and \
               (now.hour > START_H or (now.hour == START_H and now.minute >= START_M)):
                bot.send_message(cid, "✅ 开始下注")
                last_start_date[cid] = today
                print(f"[{now.strftime('%H:%M')}] ✅ 已发送：开始下注 → Chat {cid}")

            # === 即将结束提醒 ===
            if last_pre_end_date.get(cid) != today and \
               (now.hour > PRE_END_H or (now.hour == PRE_END_H and now.minute >= PRE_END_M)):
                bot.send_message(cid, "⛔ 即将结束500以上请勿报入")
                last_pre_end_date[cid] = today
                print(f"[{now.strftime('%H:%M')}] ⛔ 已发送：即将结束提醒 → Chat {cid}")

        except Exception as e:
            print(f"提醒检查出错 (Chat {cid}): {e}")

# ====================== 后台定时器线程 ======================
def run_scheduler():
    """每60秒检查一次时间，主动发送提醒（无需用户发消息）"""
    print("🕒 后台定时器线程已启动，每60秒检查一次提醒时间...")
    while True:
        try:
            check_and_send_reminders()
        except Exception as e:
            print(f"定时器出错: {e}")
        time.sleep(60)

# 启动后台线程
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# ====================== 消息处理函数 ======================
def handle_message(message):
    chat_id = message.chat.id
    active_chats.add(chat_id)

    # 1. 先执行提醒检查
    check_and_send_reminders(chat_id)

    # 2. 工作时间检查 + 转发
    try:
        now = datetime.now(TZ)          # ← 使用缓存的时区对象
        current_h, current_m = now.hour, now.minute

        is_work_time = (
            (current_h > START_H or (current_h == START_H and current_m >= START_M)) and
            (current_h < END_H or (current_h == END_H and current_m <= END_M))
        )
        if not is_work_time:
            return
    except Exception as e:
        print(f"工作时间检查出错: {e}")
        return

    if message.chat.type not in ['group', 'supergroup'] or message.from_user.is_bot:
        return

    try:
        bot.forward_message(chat_id, chat_id, message.message_id)
        print(f"✅ 已成功转发消息 | Chat: {message.chat.title or 'Private'} | ID: {message.message_id}")
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
    return "Bot is running! Scheduler active. (v2 - pytz cached)"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Flask服务器启动在端口 {port}")
    app.run(host='0.0.0.0', port=port)
