import logging
import asyncio
from sqlalchemy import text
from telegram.ext import (
    Updater,  # ✅ استخدم Updater بدلاً من Application
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ChatMemberHandler
)
import pyrogram
import config
import database as db
import utils
from handlers import start, buttons, messages, events, channel_monitor

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# إعداد Pyrogram Client (اختياري)
try:
    app_client = pyrogram.Client(
        "bot_account",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.TOKEN
    )
    pyrogram_available = True
except AttributeError:
    app_client = None
    pyrogram_available = False
    print("تنبية api id و api hash غير موجودين ")

def main():
    # ✅ تعديل 1: إضافة try-except لإنشاء الجداول مع معالجة أخطاء MySQL
    try:
        db.Base.metadata.create_all(db.engine)
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise
    
    # ✅ تعديل 2: اختبار الاتصال بقاعدة البيانات قبل تشغيل البوت
    try:
        with db.get_db_session() as session:
            session.execute(text("SELECT 1"))
        logger.info("Database connection test successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

    # ✅ استخدم Updater بدلاً من Application
    updater = Updater(token=config.TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # --- تسجيل المعالجات ---

    # 1. معالج الأوامر (مثل /start)
    dispatcher.add_handler(CommandHandler("start", start.start))

    # 2. معالج الأزرار (CallbackQuery)
    dispatcher.add_handler(CallbackQueryHandler(buttons.button_handler))
    
    # 3. معالج الرسائل في الخاص
    dispatcher.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.TEXT | filters.Document.MimeType("text/plain") | filters.Sticker.ALL), 
        messages.message_handler
    ))

    # 4. معالج كلمة "تفعيل" في المجموعات
    dispatcher.add_handler(MessageHandler(
        filters.Regex("^تفعيل$") & filters.ChatType.GROUPS, 
        messages.message_handler
    ))
    
    # 5. معالج مراقبة القنوات للملصق التفاعلي
    dispatcher.add_handler(MessageHandler(
        filters.ChatType.CHANNEL & (filters.TEXT | filters.PHOTO), 
        channel_monitor.channel_monitor
    ))

    # 6. أحداث العضوية (المغادرة)
    dispatcher.add_handler(
        ChatMemberHandler(events.chat_member_handler, ChatMemberHandler.CHAT_MEMBER)
    )

    # تشغيل النشر التلقائي
    job_queue = updater.job_queue
    job_queue.run_repeating(utils.post_job, interval=60, first=10)

    print("Bot is running...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    if hasattr(config, 'API_ID') and hasattr(config, 'API_HASH'):
        if config.API_ID and config.API_HASH:
            try:
                app_client.start()
            except Exception as e:
                print(f"Warning: Pyrogram failed to start: {e}")
    
    main()
