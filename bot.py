import json
import os
import time
import pytz
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ================== تنظیمات ثابت ==================
COIN_GAIN_INTERVAL = timedelta(minutes=5)
COIN_GAIN_AMOUNT = 1
PERIODIC_PRIZE_INTERVAL = timedelta(minutes=30)
PERIODIC_PRIZE_AMOUNT = 20
MAX_LEVEL = 60

RANKS = [
    "فرزاد(بدون فرم)ولگرد",
    "فرزاد فمبوی سرباز",
    "فرزاد فمبوی شوالیه",
    "فرزاد فمبوی فرمانده",
    "فرزاد فمبوی فرمانده کل فرقه",
    "فرزاد فمبوی فرمانروا فرقه",
    "فرزاد فمبوی فرمانروا قاره",
    "فرزاد فمبوی پادشاه زمین سکای",
    "فرزاد فمبوی تجسم فمبوی ساما",
    "فرزاد فمبوی ساما حقیقی",
    "فرزاد فمبوی ساما مطلق",
    "فرزاد فمبوی گاد گی",
    "فرزاد فمبوی ابر گاد گی",
    "فرزاد فمبوی مقدس یونیورس گاد گی"
]

DATA_FILE = "users.json"
user_data = {}

# ================== ذخیره و لود ==================
def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, ensure_ascii=False, indent=4)

def load_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except:
            user_data = {}

# ================== تبدیل رشته به datetime امن ==================
def parse_time(s):
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = pytz.UTC.localize(dt)
    return dt

# ================== ضد اسپم ==================
SPAM_TIME = 5
SPAM_LIMIT = 8
blocked_users = {}
user_message_log = {}

def check_spam(user_id):
    now = time.time()
    if user_id in blocked_users and now < blocked_users[user_id]:
        return True

    user_message_log.setdefault(user_id, [])
    user_message_log[user_id] = [t for t in user_message_log[user_id] if now - t <= SPAM_TIME]
    user_message_log[user_id].append(now)

    if len(user_message_log[user_id]) > SPAM_LIMIT:
        blocked_users[user_id] = now + 30
        return "blocked"
    return False

# ================== منطق بازی ==================
def get_rank_and_level_info(score):
    level = 1 + (score // 500)
    level = min(level, MAX_LEVEL)
    rank_index = min((level - 1) // 5, len(RANKS) - 1)
    return level, RANKS[rank_index]

def get_leaderboard_data():
    lst = []
    for uid, d in user_data.items():
        level, rank = get_rank_and_level_info(d['score'])
        lst.append({"user_id": uid, "username": d['username'], "score": d['score'], "level": level, "rank": rank})
    return sorted(lst, key=lambda x: x['score'], reverse=True)

def handle_message(message_text, user_id, username):
    # ضد اسپم
    spam = check_spam(user_id)
    if spam == True:
        return "⛔ شما موقتاً بلاک شده‌اید (۳۰ ثانیه)."
    if spam == "blocked":
        return "⚠️ خیلی سریع پیام می‌فرستی! برای ۳۰ ثانیه بلاک شدی."

    if user_id not in user_data:
        user_data[user_id] = {
            'score': 0,
            'level': 1,
            'last_coin_time': datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
            'last_periodic_prize_time': datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
            'coin_count': 0,
            'username': username
        }
        save_data()

    user_data[user_id]['username'] = username
    save_data()

    data = user_data[user_id]
    now = datetime.now(pytz.UTC)

    # --- لپ ---
    if message_text.lower() == "لپ":
        last = parse_time(data['last_coin_time'])
        if now >= last + COIN_GAIN_INTERVAL:
            data['score'] += COIN_GAIN_AMOUNT
            data['coin_count'] += 1
            data['last_coin_time'] = now.isoformat()
            save_data()
            new_level, new_rank = get_rank_and_level_info(data['score'])
            if new_level != data['level']:
                data['level'] = new_level
                save_data()
                return f"🎉 لِوِل آپ! 🏅 {new_rank}, سطح: {new_level}"
            return f"✔️ +{COIN_GAIN_AMOUNT} امتیاز دریافت شد!"
        else:
            remain = (last + COIN_GAIN_INTERVAL) - now
            return f"⌛ لطفاً {int(remain.total_seconds()//60)} دقیقه دیگر صبر کن."

    # --- وضعیت ---
    if message_text.lower() in ["فرزاد", "لپم"]:
        level, rank = get_rank_and_level_info(data['score'])
        return f"📊 وضعیت {username}: 💎 {data['score']} امتیاز, 🎯 سطح: {level}, 👑 {rank}"

    # --- برترین‌ها ---
    if message_text.lower() == "برترین ها":
        top = get_leaderboard_data()[:5]
        t = "🏆 برترین‌ها:\n"
        for i,u in enumerate(top):
            t += f"{i+1}. {u['username']} - {u['score']} امتیاز\n"
        return t

    return "📝 دستورات: لپ | فرزاد | لپم | برترین ها"

# ================== تلگرام ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def periodic_prize_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(pytz.UTC)
    for uid, data in user_data.items():
        last = parse_time(data['last_periodic_prize_time'])
        if now >= last + PERIODIC_PRIZE_INTERVAL:
            data['score'] += PERIODIC_PRIZE_AMOUNT
            data['last_periodic_prize_time'] = now.isoformat()
            save_data()
            try:
                await context.bot.send_message(chat_id=uid, text=f"🎉 جایزه دوره‌ای +{PERIODIC_PRIZE_AMOUNT} امتیاز!")
            except:
                pass

async def start_command(update, context):
    await update.message.reply_text("👋 سلام! تایپ کن: لپ")

async def handle_text(update, context):
    msg = update.message.text
    uid = update.effective_user.id
    username = update.effective_user.username or str(uid)
    ans = handle_message(msg, uid, username)
    await update.message.reply_text(ans)

def main():
    load_data()
    if not BOT_TOKEN:
        print("❌ لطفاً توکن ربات را به عنوان Environment Variable قرار دهید.")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.job_queue.run_repeating(periodic_prize_job, interval=PERIODIC_PRIZE_INTERVAL, first=5)
    print("🤖 ربات اجرا شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
