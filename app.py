# ============================================================
# Render Starter 计划最终优化版（v13）
# ============================================================
# 最终稳定版 - 自定义提醒消息 + 15秒窗口逻辑
#
# 推荐 Start Command：
#    gunicorn --workers 2 --threads 8 app:app
#
# 提醒时间（请在 Render 环境变量中设置）：
# WORK_START = 18:00   →  ☑️ 开始下注 ☑️
# WORK_AEND  = 21:18   →  ⚠️ 即将结束 ⚠️ + 投注超500勿报进
# WORK_END   = 21:22   →  🛑 结束停止 🛑 + 以下都不计入账
# ============================================================

import os
import telebot
from flask import Flask, request, abort
from datetime import datetime, timedelta
import pytz
import threading
import time
import json

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

# ====================== 自定义提醒消息（醒目版） ======================
START_MSG = "☑️ 开始下注 ☑️"
PRE_END_MSG = "⚠️ 即将结束 ⚠️\n投注超500勿报进"
END_MSG = "🛑 结束停止 🛑\n以下都不计入账"

# ====================== 持久化提醒状态 ======================
REMINDER_STATUS_FILE = "reminder_status.json"

def load_reminder_status():
    global active_chats, last_start_date, last_pre_end_date
    if os.path.exists(REMINDER_STATUS_FILE):
        try:
            with open(REMINDER_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_chats = set(data.get("active_chats", []))
                last_start_date = {int(k): v for k, v in data.get("last_start_date", {}).items()}
                last_pre_end_date = {int(k): v for k, v in data.get("last_pre_end_date", {}).items()}
        except Exception as e:
            print(f"加载提醒状态失败: {e}")
            active_chats = set()
            last_start_date = {}
            last_pre_end_date = {}
    else:
        active_chats = set()
        last_start_date = {}
        last_pre_end_date = {}

def save_reminder_status():
    try:
        data = {
            "active_chats": list(active_chats),
            "last_start_date": {str(k): v for k, v in last_start_date.items()},
            "last_pre_end_date": {str(k): v for k, v in last_pre_end_date.items()}
        }
        with open(REMINDER_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存提醒状态失败: {e}")

# ====================== 全局变量 ======================
active_chats = set()
last_start_date = {}
last_pre_end_date = {}

load_reminder_status()

# ====================== 时区 & 时间配置缓存 ======================
WORK_TIMEZONE_STR = os.environ.get('WORK_TIMEZONE', 'Asia/Shanghai')
try:
    TZ = pytz.timezone(WORK_TIMEZONE_STR)
except Exception as e:
    TZ = pytz.timezone('Asia/Shanghai')

try:
    START_H, START_M = map(int, os.environ['WORK_START'].split(':'))
    END_H, END_M = map(int, os.environ['WORK_END'].split(':'))
    PRE_END_H, PRE_END_M = map(int, os.environ['WORK_AEND'].split(':'))
except Exception as e:
    START_H, START_M = 18, 0
    END_H, END_M = 21, 22
    PRE_END_H, PRE_END_M = 21, 18

# ====================== 核心提醒函数（15秒窗口 + 自定义消息） ======================
def check_and_send_reminders():
    now = datetime.now(TZ)
    today = str(now.date())

    start_time = now.replace(hour=START_H, minute=START_M, second=0, microsecond=0)
    pre_end_time = now.replace(hour=PRE_END_H, minute=PRE_END_M, second=0, microsecond=0)
    end_time = now.replace(hour=END_H, minute=END_M, second=0, microsecond=0)

    for cid in list(active_chats):
        try:
            # === 开始下注提醒（18:00） ===
            if (last_start_date.get(cid) != today and 
                start_time <= now < start_time + timedelta(seconds=15)):
                bot.send_message(cid, START_MSG)
                last_start_date[cid] = today
                save_reminder_status()
                print(f"[{now.strftime('%H:%M:%S')}] ✅ 已发送：开始下注 → Chat {cid}")

            # === 即将结束提醒（21:18） ===
            if (last_pre_end_date.get(cid) != today and 
                pre_end_time <= now < pre_end_time + timedelta(seconds=15)):
                bot.send_message(cid, PRE_END_MSG)
                last_pre_end_date[cid] = today
                save_reminder_status()
                print(f"[{now.strftime('%H:%M:%S')}] ⚠️ 已发送：即将结束 → Chat {cid}")

            # === 结束停止提醒（21:22） ===
            if (last_pre_end_date.get(cid) != today and 
                end_time <= now < end_time + timedelta(seconds=15)):
                bot.send_message(cid, END_MSG)
                last_pre_end_date[cid] = today
                save_reminder_status()
                print(f"[{now.strftime('%H:%M:%S')}] 🛑 已发送：结束停止 → Chat {cid}")

        except Exception as e:
            print(f"提醒检查出错 (Chat {cid}): {e}")

# ====================== 后台定时器线程 ======================
def run_scheduler():
    print("🕒 后台定时器线程已启动，每15秒检查一次（v13 自定义消息版）...")
    while True:
        try:
            load_reminder_status()
            check_and_send_reminders()
        except Exception as e:
            print(f"定时器出错: {e}")
        time.sleep(15)

scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# ====================== 自动注册群聊 ======================
@bot.my_chat_member_handler()
def auto_register_on_add(message: telebot.types.ChatMemberUpdated):
    chat_id = message.chat.id
    new_status = message.new_chat_member.status

    if new_status in ['member', 'administrator']:
        if chat_id not in active_chats:
            active_chats.add(chat_id)
            save_reminder_status()
            try:
                bot.send_message(chat_id, "✅ 机器人已成功加入本群，定时提醒功能已自动启用！")
            except:
                pass
    elif new_status in ['left', 'kicked']:
        if chat_id in active_chats:
            active_chats.discard(chat_id)
            save_reminder_status()

# ====================== /register 命令 ======================
@bot.message_handler(commands=['register'])
def register_chat(message):
    chat_id = message.chat.id
    if chat_id not in active_chats:
        active_chats.add(chat_id)
        save_reminder_status()
        bot.reply_to(message, f"✅ 已成功注册本群 (ID: {chat_id})，定时提醒已启用")

# ====================== /status 命令 ======================
@bot.message_handler(commands=['status'])
def status_command(message):
    chat_id = message.chat.id
    now = datetime.now(TZ)
    today = str(now.date())
    start_sent = last_start_date.get(chat_id) == today
    pre_end_sent = last_pre_end_date.get(chat_id) == today
    msg = f"""📊 **机器人状态**
🟢 活跃群聊: {len(active_chats)} 个
☑️ 开始下注已发送: {'是' if start_sent else '否'}
⚠️ 即将结束已发送: {'是' if pre_end_sent else '否'}
🛑 结束停止已发送: {'是' if pre_end_sent else '否'}
⏰ 当前时间: {now.strftime('%H:%M:%S')}"""
    bot.reply_to(message, msg)

# ====================== 消息处理函数（只转发） ======================
def handle_message(message):
    chat_id = message.chat.id
    active_chats.add(chat_id)
    save_reminder_status()

    try:
        now = datetime.now(TZ)
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
        elif update.my_chat_member:
            auto_register_on_add(update.my_chat_member)
        return '', 200
    abort(403)

@app.route('/')
def index():
    return "Bot is running! (v13 - 自定义醒目提醒消息)"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Flask服务器启动在端口 {port}")
    app.run(host='0.0.0.0', port=port)
