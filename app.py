import os
import telebot
from flask import Flask, request, abort
from datetime import datetime
import pytz

TOKEN = os.environ.get('TOKEN')
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set!")

print(f"DEBUG: Bot starting with TOKEN (first 10 chars): {TOKEN[:10]}...")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

print("=== Bot 已启动（调试模式）===")

def handle_message(message):
    print("=== Webhook 收到消息 ===")
    print(f"时间: {datetime.now()}")
    print(f"来自: {message.from_user.first_name} (@{message.from_user.username or '无'})")
    print(f"群组: {message.chat.title or 'Private'} (ID: {message.chat.id})")
    print(f"消息内容: {message.text or '[非文本消息]'}")
    print("-" * 50)

    # 无条件转发（暂时关闭所有时间检查）
    try:
        bot.forward_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        print("✅ 已成功转发消息")
    except Exception as e:
        print(f"转发失败: {e}")

    # 测试发送一条消息，确认机器人能发消息
    try:
        bot.send_message(message.chat.id, "🧪 机器人收到消息并转发成功")
    except Exception as e:
        print(f"测试消息发送失败: {e}")


@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    print("=== Webhook 端点被调用 ===")
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        if update.message:
            handle_message(update.message)
        return '', 200
    abort(403)


@app.route('/')
def index():
    return "Bot is running! (Debug Mode)"


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
