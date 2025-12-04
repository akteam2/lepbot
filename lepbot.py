import logging
import os
import time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# کتابخانه‌های دیتابیس (نیاز به نصب در requirements.txt)
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

# --- تنظیمات اولیه و پیکربندی ---

# 1. خواندن توکن و URL اتصال از متغیرهای محیطی
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8525090600:AAE9Kqzytg__7P29GnmEX5y4CooRvTLhYeY') # Fallback
DATABASE_URL = os.getenv('DATABASE_URL') # این URL باید توسط Render برای سرویس 'lepbot-db' فراهم شود.

REWARD_INTERVAL_SECONDS = 43200  # 12 ساعت
DEFAULT_SCORE = 100

# تنظیمات لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- تنظیمات دیتابیس SQLAlchemy ---
Base = declarative_base()

class Score(Base):
    """مدل دیتابیس برای ذخیره امتیازات."""
    __tablename__ = 'scores'
    chat_id = Column(Integer, primary_key=True)
    username = Column(String)
    score = Column(Integer, default=DEFAULT_SCORE)
    last_reward_time = Column(Float, default=time.time())

    def __repr__(self):
        return f"<Score(chat_id={self.chat_id}, score={self.score})>"

# اتصال به دیتابیس
if not DATABASE_URL:
    logger.error("FATAL: DATABASE_URL environment variable is not set. Using in-memory SQLite for testing only!")
    # اگر URL تنظیم نشده باشد، برای جلوگیری از کرش، از SQLite موقت استفاده می‌کنیم.
    engine = create_engine("sqlite:///:memory:")
else:
    # استفاده از URL دریافتی از Render برای PostgreSQL
    engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

def initialize_db():
    """ایجاد جداول در PostgreSQL (اگر وجود ندارند)"""
    try:
        # این خط باعث ایجاد جداول تعریف شده در Base می‌شود
        Base.metadata.create_all(engine)
        logger.info("Database tables ensured (PostgreSQL/SQLite).")
    except SQLAlchemyError as e:
        logger.error(f"Error ensuring database tables: {e}")

def get_session():
    """برگرداندن یک سشن دیتابیس."""
    return Session()

# --- مدیریت Job Queue (پاداش دوره‌ای) ---

async def reward_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """تابعی که به صورت دوره‌ای اجرا می‌شود و امتیاز می‌دهد."""
    chat_id = context.job.chat_id
    
    if chat_id is None:
        logger.warning("Reward job executed without a chat_id. Skipping.")
        return

    session = get_session()
    try:
        # یافتن کاربر
        user = session.query(Score).filter_by(chat_id=chat_id).first()
        
        if not user:
            logger.warning(f"Chat ID {chat_id} not found in DB for reward job. Skipping.")
            return

        # به‌روزرسانی امتیاز
        user.score += 5
        user.last_reward_time = time.time()
        session.commit()

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"🎁 پاداش 12 ساعته شما: 5 امتیاز اضافه شد!\nامتیاز جدید شما: {user.score}"
        )
        logger.info(f"Reward sent to {chat_id}. New score: {user.score}")

    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"Error during reward job for {chat_id}: {e}")
    finally:
        session.close()


# --- مدیریت پیام‌ها (Handlers) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر دستور /start"""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.first_name
    
    session = get_session()
    try:
        user = session.query(Score).filter_by(chat_id=chat_id).first()
        
        if not user:
            # کاربر جدید: درج در دیتابیس با امتیاز پیش‌فرض
            new_user = Score(chat_id=chat_id, username=username, score=DEFAULT_SCORE, last_reward_time=time.time())
            session.add(new_user)
            session.commit()
            message = (
                f"سلام {username} عزیز! به ربات امتیازدهی خوش آمدید.\n"
                f"شما با امتیاز پایه {DEFAULT_SCORE} شروع کردید.\n"
                f"برای دریافت امتیاز، کافیست در چت‌های گروهی این ربات را تگ کنید."
            )
        else:
            # کاربر قبلی: بارگذاری امتیاز موجود
            message = (
                f"خوش آمدید مجدد {username}!\n"
                f"امتیاز فعلی شما: {user.score}"
            )

        await update.message.reply_text(message)

        # تنظیم Job Queue برای پاداش دوره‌ای
        current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
        if not current_jobs:
            context.job_queue.run_repeating(
                reward_job, 
                interval=timedelta(seconds=REWARD_INTERVAL_SECONDS), 
                first=timedelta(seconds=REWARD_INTERVAL_SECONDS),
                name=str(chat_id), 
                chat_id=chat_id
            )
            logger.info(f"Reward job started for chat_id: {chat_id} with interval {REWARD_INTERVAL_SECONDS}s")

    except SQLAlchemyError as e:
        session.rollback()
        await update.message.reply_text("خطا در دسترسی به دیتابیس هنگام اجرای /start.")
        logger.error(f"Error in start handler: {e}")
    finally:
        session.close()


async def score_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر برای شمارش امتیاز در پیام‌ها."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.first_name
    
    if context.bot.username.lower() in update.message.text.lower():
        points_to_add = 1
        session = get_session()
        try:
            user = session.query(Score).filter_by(chat_id=chat_id).first()
            
            if user:
                user.score += points_to_add
                user.last_reward_time = time.time()
                session.commit()
                
                await update.message.reply_text(
                    f"✅ {username} عزیز، یک امتیاز دریافت کردید!\nامتیاز جدید شما: {user.score}",
                    quote=True
                )
                logger.info(f"Score awarded to {username} ({chat_id}). New Score: {user.score}")
            else:
                await update.message.reply_text("خطا: امتیاز شما در سیستم یافت نشد. لطفاً دوباره دستور /start را بزنید.")

        except SQLAlchemyError as e:
            session.rollback()
            await update.message.reply_text("خطا در به‌روزرسانی امتیاز در دیتابیس.")
            logger.error(f"Error in score handler: {e}")
        finally:
            session.close()


async def get_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر دستور /score برای نمایش امتیاز فعلی."""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or update.effective_user.first_name
    
    session = get_session()
    try:
        user = session.query(Score).filter_by(chat_id=chat_id).first()
        
        if user:
            await update.message.reply_text(f"امتیاز فعلی شما ({username}): {user.score}")
        else:
            await update.message.reply_text("شما هنوز در سیستم ثبت نشده‌اید. لطفاً دستور /start را بزنید.")
    except SQLAlchemyError as e:
        await update.message.reply_text("خطا در بازیابی امتیاز از دیتابیس.")
        logger.error(f"Error in get_score handler: {e}")
    finally:
        session.close()


def main() -> None:
    """نقطه ورود اصلی ربات."""
    
    # 1. اطمینان از آماده بودن دیتابیس (جداول)
    initialize_db()
    
    # 2. ساخت Application با توکن
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == '8525090600:AAE9Kqzytg__7P29GnmEX5y4CooRvTLhYeY':
        logger.error("FATAL: Telegram Bot Token is missing or using fallback!")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 3. ثبت هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("score", get_score))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, score_handler)
    )

    # 4. شروع پولینگ (اجرای ربات)
    logger.info("Starting bot polling with PostgreSQL configuration...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
