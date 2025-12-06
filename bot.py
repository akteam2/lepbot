import os
import json
import pytz
from datetime import datetime, timedelta
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ================== تنظیمات ==================
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

# ================== ماینر ==================
MINER_LEVELS = []
base_score = 1
base_capacity = 30
base_cost = 45
for i in range(20):
    level = i + 1
    score = base_score * (2 ** i)
    capacity = base_capacity * (2 ** i)
    cost = int(base_cost * (2.2 ** i))
    MINER_LEVELS.append({
        "level": level,
        "score_per_30min": score,
        "capacity": capacity,
        "upgrade_cost": cost
    })

DATA_FILE = "users.json"
user_data = {}

# ================== ذخیره و لود کاربران ==================
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

def parse_time(s):
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt

# ================== منطق بازی ==================
def get_rank_and_level_info(score):
    level = 1 + (score // 500)
    level = min(level, MAX_LEVEL)
    rank_index = min((level - 1)//5, len(RANKS)-1)
    return level, RANKS[rank_index]

def handle_message(message_text, user_id, username, reply_to: Message = None):
    if user_id not in user_data:
        user_data[user_id] = {
            "score":0,
            "level":1,
            "last_coin_time": datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
            "last_periodic_prize_time": datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
            "coin_count":0,
            "miner_level":1,
            "miner_storage":0,
            "miner_last_time": datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
            "username":username
        }
        save_data()

    data = user_data[user_id]
    data["username"] = username
    now = datetime.now(pytz.UTC)

    # --- لپ ---
    if message_text.lower() == "لپ":
        last = parse_time(data['last_coin_time'])
        if now >= last + COIN_GAIN_INTERVAL:
            data['score'] += COIN_GAIN_AMOUNT
            data['coin_count'] += 1
            data['last_coin_time'] = now.isoformat()
            save_data()
            level, rank = get_rank_and_level_info(data['score'])
            return f"✔️ {COIN_GAIN_AMOUNT} امتیاز دریافت شد! لول: {level}, مقام: {rank}"
        else:
            remain = (last + COIN_GAIN_INTERVAL) - now
            return f"⌛ لطفاً {int(remain.total_seconds()//60)} دقیقه دیگر صبر کن."

    # --- وضعیت ---
    if message_text.lower() in ["فرزاد", "لپم"]:
        level, rank = get_rank_and_level_info(data['score'])
        miner_lvl = data["miner_level"]
        miner_info = MINER_LEVELS[miner_lvl-1]
        return (
            f"📊 {username}:\n"
            f"امتیاز: {data['score']}\n"
            f"لول: {level}\n"
            f"مقام: {rank}\n"
            f"ماینر سطح {miner_lvl}: {data['miner_storage']}/{miner_info['capacity']} امتیاز ذخیره"
        )

    # --- برترین‌ها ---
    if message_text.lower() == "برترین ها":
        top = sorted(
            [{"username":d["username"], "score":d["score"]} for d in user_data.values()],
            key=lambda x:x["score"], reverse=True
        )[:5]
        text = "🏆 برترین‌ها:\n"
        for i,u in enumerate(top):
            text += f"{i+1}. {u['username']} - {u['score']} امتیاز\n"
        return text

    # --- ماینر ---
    if message_text.lower() == "ماینر":
        lvl = data["miner_level"]
        miner = MINER_LEVELS[lvl-1]
        last = parse_time(data["miner_last_time"])
        elapsed = now - last
        generated = miner["score_per_30min"] * (elapsed.total_seconds()//1800)
        stored = min(data["miner_storage"] + generated, miner["capacity"])
        data["miner_storage"] = stored
        data["miner_last_time"] = now.isoformat()
        save_data()

        keyboard = [
            [InlineKeyboardButton("برداشت پوینت‌ها", callback_data="withdraw_miner")],
            [InlineKeyboardButton("ارتقا ماینر", callback_data="upgrade_miner")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        return f"⛏️ ماینر سطح {lvl}: {int(data['miner_storage'])}/{miner['capacity']} امتیاز ذخیره دارد.", reply_markup

    # --- انتقال امتیاز با ریپلای ---
    if message_text.lower().startswith("لپمو بگیر") and reply_to:
        try:
            parts = message_text.split()
            amount = int(parts[-1])
            if amount <= 0:
                return "❌ مقدار باید مثبت باشد."
            if data["score"] < amount:
                return f"❌ موجودی کافی نیست! فقط {data['score']} امتیاز دارید."
            target_id = reply_to.from_user.id
            target_name = reply_to.from_user.username or str(target_id)
            if target_id not in user_data:
                user_data[target_id] = {
                    "score":0,
                    "level":1,
                    "last_coin_time": datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
                    "last_periodic_prize_time": datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
                    "coin_count":0,
                    "miner_level":1,
                    "miner_storage":0,
                    "miner_last_time": datetime(1970,1,1,tzinfo=pytz.UTC).isoformat(),
                    "username":target_name
                }
            data["score"] -= amount
            user_data[target_id]["score"] += amount
            save_data()
            return f"✅ {amount} امتیاز به {target_name} منتقل شد."
        except:
            return "❌ فرمت اشتباه است. مثال: لپمو بگیر ۱۰ (ریپلای روی پیام فرد مورد نظر)"

    # --- نمایش دستورات فقط با 'دستورات' ---
    if message_text.lower() == "دستورات":
        return (
            "📜 دستورات:\n"
            "🔹 لپ\n"
            "🔹 فرزاد / لپم\n"
            "🔹 برترین ها\n"
            "🔹 ماینر\n"
            "🔹 ارتقا ماینر (دکمه در ماینر)\n"
            "🔹 انتقال امتیاز با ریپلای: لپمو بگیر [عدد]"
        )

    # برای سایر ورودی‌ها هیچ پیامی ارسال نشود
    return None

# ================== JobQueue ==================
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

# ================== Callback دکمه‌ها ==================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = user_data[user_id]
    now = datetime.now(pytz.UTC)

    if query.data == "withdraw_miner":
        lvl = data["miner_level"]
        miner = MINER_LEVELS[lvl-1]
        points = int(data["miner_storage"])
        if points == 0:
            await query.edit_message_text("❌ هیچ پوینتی برای برداشت موجود نیست.")
        else:
            data["score"] += points
            data["miner_storage"] = 0
            save_data()
            await query.edit_message_text(f"✅ {points} امتیاز ماینر به امتیاز اصلی اضافه شد!")

    elif query.data == "upgrade_miner":
        lvl = data["miner_level"]
        if lvl >= 20:
            await query.edit_message_text("🔝 شما در بالاترین سطح ماینر هستید.")
        else:
            next_miner = MINER_LEVELS[lvl]
            if data["score"] >= next_miner["upgrade_cost"]:
                data["score"] -= next_miner["upgrade_cost"]
                data["miner_level"] += 1
                save_data()
                await query.edit_message_text(f"✅ ماینر به سطح {lvl+1} ارتقا یافت!")
            else:
                await query.edit_message_text(f"❌ امتیاز کافی نیست. برای ارتقا نیاز به {next_miner['upgrade_cost']} امتیاز دارید.")

# ================== تلگرام ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 سلام! برای دیدن دستورات تایپ کن: دستورات")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    uid = update.effective_user.id
    username = update.effective_user.username or str(uid)
    reply_msg = update.message.reply_to_message
    ans = handle_message(msg, uid, username, reply_msg)
    if ans:
        if isinstance(ans, tuple):
            text, reply_markup = ans
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(ans)

def main():
    load_data()
    if not BOT_TOKEN:
        print("❌ لطفاً BOT_TOKEN را در Environment Variable قرار دهید.")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.job_queue.run_repeating(periodic_prize_job, interval=PERIODIC_PRIZE_INTERVAL, first=5)
    print("🤖 ربات اجرا شد!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
