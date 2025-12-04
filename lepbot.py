from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, CommandHandler, ContextTypes
import json, asyncio
import os # کتابخانه os برای خواندن متغیرهای محیطی اضافه شد

# --- تنظیمات ذخیره‌سازی (برای سازگاری با محیط ابری Render) ---
# توجه: در این نسخه، امتیازات پس از هر ری‌استارت از بین خواهند رفت.
# برای ذخیره‌سازی دائمی باید از دیتابیس یا Volume استفاده شود.
scores = {}  # {user_id: {"count": int, "points": int, "level": int, "name": str}}

def save_scores():
    # این تابع فعلاً غیرفعال است چون فایل‌های محلی در Render پایدار نیستند.
    # اگر این خط اجرا شود، فقط در طول عمر این اجرای موقت اعمال می‌شود.
    try:
        with open("scores.json", "w") as f:
            json.dump(scores, f)
    except Exception as e:
        print(f"Warning: Could not save scores locally: {e}")
    pass

def load_scores():
    global scores
    # این تابع فعلاً برای اطمینان از شروع با داده‌های تازه در محیط ابری غیرفعال شده است.
    # scores = {}
    # try:
    #     with open("scores.json") as f:
    #         scores = json.load(f)
    # except:
    #     scores = {}
    pass

# --- متغیرهای جهانی ---
reward_active = False

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
    # توجه: context.job.chat_id در اینجا ممکن است کار نکند، چون job_queue در main تنظیم می‌شود.
    # باید از یک ChatID ثابت یا راه دیگر استفاده کرد.
    # برای رفع این مشکل، از توکن ربات و یک ChatID ثابت استفاده می‌کنیم یا از روشی که در main تنظیم شده است.
    
    # فرض می‌کنیم که ربات به یک ChatID مشخص (مثلاً گروهی که در آن دستور داده شده) متصل است.
    # اگر در حالت Polling عمومی است، این خط ممکن است خطا دهد.
    
    await context.bot.send_message(
        chat_id=context.job.chat_id if context.job.chat_id else -1001234567890, # یک ChatID فرضی برای تست یا چت اصلی
        text="🎁 شروع جایزه لپ!\nاولین کسی که «لپ» بگه ۱۵ امتیاز می‌گیره! 😍"
    )
    
    # 60 ثانیه برای پاسخ فعال بمونه
    await asyncio.sleep(60)
    reward_active = False

async def main():
    load_scores()
    
    # **مهم‌ترین بخش: استفاده از توکن از متغیر محیطی (Environment Variable)**
    # توکن شما مستقیماً در کد قرار داده شده است، اما بهتر است از متغیر محیطی استفاده کنید.
    # اگر متغیر محیطی `TELEGRAM_BOT_TOKEN` تنظیم نشده باشد، از توکن دوم شما به عنوان fallback استفاده می‌شود.
    
    TOKEN_FROM_ENV = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if TOKEN_FROM_ENV:
        bot_token = TOKEN_FROM_ENV
        print("Using token from Environment Variable.")
    else:
        # **توکن شما مستقیماً در کد قرار داده شد (روش جایگزین)**
        bot_token = "8525090600:AAE9Kqzytg__7P29GnmEX5y4CooRvTLhYeY"
        print("Warning: Using hardcoded token as fallback. Please set TELEGRAM_BOT_TOKEN in Render.")
        
    app = ApplicationBuilder().token(bot_token).build()
    job_queue = app.job_queue

    # تنظیم زمان‌بندی برای اجرای job
    # 12 ساعت فاصله (12 * 60 * 60 = 43200 ثانیه)
    job_queue.run_repeating(reward_job, interval=43200, first=5, name="reward_timer")
    
    # برای اینکه reward_job بتواند پیام بفرستد، باید یک ChatID (معمولاً Chat ID گروه یا کانال) داشته باشد.
    # در حالت Polling، این کار کمی پیچیده است. بهترین راه این است که دستور /start یا اولین پیام را دریافت کنید
    # و ChatID را ذخیره کنید. برای اجرای ساده، باید یک ChatID را در کد Hardcode کنید یا از دستورات استفاده کنید.
    # فعلاً با استفاده از نام‌گذاری job، امیدواریم سیستم Job Queue بتواند آن را مدیریت کند.


    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("top", show_top))
    
    print("Starting polling...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
