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
last_start_date = {}      # chat_id -> date  (记录今天是否已发送“开始下注”)
last_pre_end_date = {}    # chat_id -> date  (记录今天是否已发送“即将结束”)
active_chats = set()      # 记录所有活跃的群聊ID（收到消息后加入）

# ====================== 核心提醒函数（可被消息触发和定时器调用） ======================
def check_and_send_reminders(chat_id=None):
    """
    检查当前时间是否到达提醒时间点，如果是则发送提醒。
    - 如果传入 chat_id：只检查该聊天（来自用户消息触发）
    - 如果 chat_id=None：检查所有 active_chats（来自后台定时器）
    """
    tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
    now = datetime.now(tz)
    today = now.date()

    if chat_id is None:
        chats_to_check = list(active_chats)
    else:
        chats_to_check = [chat_id]

    for cid in chats_to_check:
        try:
            # === 开始下注提醒 ===
            start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
            if last_start_date.get(cid) != today and \
               (now.hour > start_h or (now.hour == start_h and now.minute >= start_m)):
                bot.send_message(cid, "✅ 开始下注")
                last_start_date[cid] = today
                print(f"[{now.strftime('%H:%M')}] ✅ 已发送：开始下注 → Chat {cid}")

            # === 即将结束提醒 ===
            pre_end_h, pre_end_m = map(int, os.environ['WORK_AEND'].split(':'))
            if last_pre_end_date.get(cid) != today and \
               (now.hour > pre_end_h or (now.hour == pre_end_h and now.minute >= pre_end_m)):
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
            check_and_send_reminders()  # 检查所有活跃群聊
        except Exception as e:
            print(f"定时器出错: {e}")
        time.sleep(60)  # 可根据需要改为30或更短

# 启动后台线程（daemon=True 确保主进程退出时自动停止）
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# ====================== 消息处理函数 ======================
def handle_message(message):
    chat_id = message.chat.id
    active_chats.add(chat_id)  # 记录活跃群聊

    # 1. 先执行提醒检查（无论是否在工作时间都检查）
    check_and_send_reminders(chat_id)

    # 2. 工作时间检查 + 转发
    try:
        start_h, start_m = map(int, os.environ['WORK_START'].split(':'))
        end_h, end_m = map(int, os.environ['WORK_END'].split(':'))
        tz = pytz.timezone(os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai'))
        now = datetime.now(tz)
        current_h, current_m = now.hour, now.minute

        is_work_time = (
            (current_h > start_h or (current_h == start_h and current_m >= start_m)) and
            (current_h < end_h or (current_h == end_h and current_m <= end_m))
        )
        if not is_work_time:
            return
    except Exception as e:
        print(f"工作时间检查出错: {e}")
        return

    # 只处理群组消息，且不是机器人自己发的
    if message.chat.type not in ['group', 'supergroup'] or message.from_user.is_bot:
        return

    # 干净转发
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
    return "Bot is running! Scheduler active."

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Flask服务器启动在端口 {port}")
