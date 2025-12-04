from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes
import json, asyncio, os

scores = {}
reward_active = False
SCORE_FILE = "scores.json"

def save_scores():
    try:
        with open(SCORE_FILE, "w") as f:
            json.dump(scores, f)
    except Exception as e:
        print(f"Error saving scores: {e}")

def load_scores():
    global scores
    try:
        with open(SCORE_FILE) as f:
            scores = json.load(f)
        print(f"Scores loaded successfully. {len(scores)} users found.")
    except FileNotFoundError:
        print("Scores file not found. Starting with empty scores.")
        scores = {}
    except Exception as e:
        print(f"Error loading scores: {e}. Starting fresh.")
        scores = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global reward_active
    user = update.effective_user
    if not user: return
    
    text = update.message.text.lower().strip()
    uid = str(user.id)
    
    if uid not in scores:
        scores[uid] = {"count": 0, "points": 0, "level": 1, "name": user.first_name or f"User{uid}"}

    # --- اگر "لپ" گفت ---
    if text == "لپ":
        if reward_active:
            reward_active = False
            scores[uid]["points"] += 15
            save_scores()
            await update.message.reply_text(
                f"🎉 {user.first_name} برنده جایزه لپ شد! 🎁 ۱۵ امتیاز اضافه شد.\n"
                f"امتیاز کل: {scores[uid]['points']}"
            )
        else:
            scores[uid]["count"] += 1
            scores[uid]["points"] += 1

            if scores[uid]["count"] % 10 == 0:
                scores[uid]["level"] += 1
                await update.message.reply_text(
                    f"💪 تبریک {user.first_name}! به لول {scores[uid]['level']} رسیدی! 🔥"
                )

            save_scores()
            await update.message.reply_text(
                f"✅ {user.first_name} یک امتیاز گرفت! امتیاز کل: {scores[uid]['points']}"
            )

    # --- اگر گفت "لپ هام" ---
    elif "لپ هام" in text:
        data = scores[uid]
        await update.message.reply_text(
            f"📊 {user.first_name} عزیز!\n"
            f"🔸 تعداد لپ‌ها: {data['count']}\n"
            f"🔸 امتیاز کل: {data['points']}\n"
            f"🔸 سطح فعلی: {data['level']}\n"
            f"🎈 ادامه بده تا لول بعدی رو بگیری!"
        )

    # --- اگر گفت "جدول لپ" ---
    elif "جدول لپ" in text:
        await show_top(update)

async def show_top(update: Update):
    if not scores:
        await update.message.reply_text("📭 هنوز هیچ‌کس لپ نگفته 😅")
        return

    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)
    top_text = "🏆 جدول برترین لپ‌گوها:\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, user_data in enumerate(sorted_users[:5]):
        medal = medals[i] if i < len(medals) else f"{i+1}️⃣"
        top_text += f"{medal} {user_data['name']} — لول {user_data['level']} — امتیاز {user_data['points']}\n"

    await update.message.reply_text(top_text)

# **تغییر کلیدی در اینجا اعمال شده است**
async def reward_job(context: ContextTypes.DEFAULT_TYPE):
    global reward_active
    
    # اگر chat_id مشخص نبود، این Job اجرا نخواهد شد تا از Crash جلوگیری شود.
    if not context.job or not context.job.chat_id:
        print("Reward Job skipped: No valid chat_id found in job context.")
        return

    reward_active = True
    
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="🎁 شروع جایزه لپ!\nاولین کسی که «لپ» بگه ۱۵ امتیاز می‌گیره! 😍"
    )
    
    await asyncio.sleep(60)
    reward_active = False

async def main():
    load_scores()
    
    TOKEN_FROM_ENV = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if TOKEN_FROM_ENV:
        bot_token = TOKEN_FROM_ENV
        print("Using token from Environment Variable.")
    else:
        bot_token = "8525090600:AAE9Kqzytg__7P29GnmEX5y4CooRvTLhYeY"
        print("Warning: Using hardcoded token. Set TELEGRAM_BOT_TOKEN in Render.")
        
    app = ApplicationBuilder().token(bot_token).build()
    job_queue = app.job_queue

    # **تغییر در نحوه اجرای Job**
    # ما نمی‌توانیم یک Job تکرارشونده در run_repeating برای همه چت‌ها تنظیم کنیم.
    # بهترین راه این است که ربات از طریق اولین پیام کاربر (یا دستور /start) چت‌ها را یاد بگیرد.
    # برای اجرای اولیه، باید به طور موقت Job را حذف کنیم تا ربات بالا بیاید و منتظر پیام باشد.
    
    # حذف خطوط مربوط به run_repeating تا زمانی که یک چت مشخص شود.
    # job_queue.run_repeating(reward_job, interval=43200, first=5, name="reward_timer") 
    # اگر این خط باعث خطا می‌شود، آن را موقتاً حذف می‌کنیم.
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("top", show_top))
    
    # **راه جایگزین برای اجرای زمان‌بندی:**
    # یک تابع جدید برای اجرای زمان‌بندی پس از دریافت اولین پیام (مثلاً با دستور /start) ایجاد کنید.
    
    print("Starting polling...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
