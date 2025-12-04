from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes
import json, asyncio

scores = {}  # {user_id: {"count": int, "points": int, "level": int, "name": str}}
reward_active = False

def save_scores():
    with open("scores.json", "w") as f:
        json.dump(scores, f)

def load_scores():
    global scores
    try:
        with open("scores.json") as f:
            scores = json.load(f)
    except:
        scores = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global reward_active
    user = update.effective_user
    text = update.message.text.lower().strip()

    uid = str(user.id)
    if uid not in scores:
        scores[uid] = {"count": 0, "points": 0, "level": 1, "name": user.first_name}

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

            # بررسی ارتقای سطح
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

    # مرتب‌سازی بر اساس امتیاز
    sorted_users = sorted(scores.values(), key=lambda x: x["points"], reverse=True)
    top_text = "🏆 جدول برترین لپ‌گوها:\n\n"

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, user_data in enumerate(sorted_users[:5]):
        medal = medals[i] if i < len(medals) else f"{i+1}️⃣"
        top_text += f"{medal} {user_data['name']} — لول {user_data['level']} — امتیاز {user_data['points']}\n"

    await update.message.reply_text(top_text)

async def reward_job(context: ContextTypes.DEFAULT_TYPE):
    global reward_active
    reward_active = True
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="🎁 شروع جایزه لپ!\nاولین کسی که «لپ» بگه ۱۵ امتیاز می‌گیره! 😍"
    )
    # 60 ثانیه برای پاسخ فعال بمونه
    await asyncio.sleep(60)
    reward_active = False

async def main():
    load_scores()
    app = ApplicationBuilder().token("8525090600:AAE9Kqzytg__7P29GnmEX5y4CooRvTLhYeY").build()
    job_queue = app.job_queue

    job_queue.run_repeating(reward_job, interval=12*60, first=5)

    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("top", show_top))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
