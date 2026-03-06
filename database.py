import os
import sys
from contextlib import contextmanager

# --- إعدادات MySQL ---
# يمكنك استخدام متغيرات البيئة أو تعيين القيم مباشرة
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot_db')

# بناء رابط الاتصال (Connection String)
# صيغة: mysql+pymysql://username:password@host:port/database
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print(f"Connecting to MySQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")
# ---------------------------------------------------

from sqlalchemy import create_engine, Column, BigInteger, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
import random

# إعداد قاعدة البيانات باستخدام MySQL
# pool_recycle=3600: إعادة تدوير الاتصالات كل ساعة (لمنع انقطاع MySQL التلقائي) [^2^]
# pool_pre_ping=True: التحقق من صحة الاتصال قبل الاستخدام [^2^]
# connect_args: إعدادات ترميز UTF-8 للعربية
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_recycle=3600,        # إعادة تدوير الاتصال كل ساعة
    pool_pre_ping=True,       # التحقق من الاتصال قبل الاستخدام
    connect_args={
        'charset': 'utf8mb4',  # دعم الإيموجي والعربية
        'connect_timeout': 10
    }
)

Base = declarative_base()
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# --- تعريف الجداول (مع تعديل الأنواع لـ MySQL) ---

class User(Base):
    __tablename__ = 'users'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    is_admin = Column(Boolean, default=False)

class Channel(Base):
    __tablename__ = 'channels'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    added_by = Column(BigInteger, nullable=True, index=True)
    category = Column(String(100), default="اقتباسات عامة")
    msg_format = Column(String(50), default="normal")
    time_type = Column(String(50), default="default")
    time_value = Column(String(50), nullable=True)
    last_post_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # خصائص الملصق التفاعلي
    sticker_file_id = Column(String(255), nullable=True)
    sticker_interval = Column(Integer, default=0)
    msg_counter = Column(Integer, default=0)
    sticker_sender_id = Column(BigInteger, nullable=True)

class BotSettings(Base):
    __tablename__ = 'settings'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)

class FileContent(Base):
    __tablename__ = 'files_content'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    category = Column(String(100), index=True, nullable=False)
    content = Column(Text, nullable=False)

# إنشاء الجداول (إذا لم تكن موجودة)
Base.metadata.create_all(engine)

# --- إدارة الجلسات بشكل آمن (Context Manager) ---

@contextmanager
def get_db_session():
    """سياق آمن لإدارة جلسات قاعدة البيانات"""
    session = Session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

# --- دوال مساعدة محسنة ---

def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مشرفاً"""
    with get_db_session() as session:
        user = session.query(User).filter_by(user_id=user_id).first()
        return user.is_admin if user else False

def add_channel(ch_id: int, title: str, added_by: int, cat: str, fmt: str, 
                t_type: str = 'default', t_val: str = None) -> bool:
    """إضافة قناة جديدة"""
    with get_db_session() as session:
        try:
            # التحقق من عدم وجود القناة مسبقاً
            existing = session.query(Channel).filter_by(channel_id=ch_id).first()
            if existing:
                return False
            
            new_ch = Channel(
                channel_id=ch_id,
                title=title,
                added_by=added_by,
                category=cat,
                msg_format=fmt,
                time_type=t_type,
                time_value=t_val
            )
            session.add(new_ch)
            return True
        except Exception as e:
            print(f"Error adding channel: {e}")
            return False

def remove_channel_db(ch_id: int) -> bool:
    """حذف قناة من قاعدة البيانات"""
    with get_db_session() as session:
        try:
            ch = session.query(Channel).filter_by(channel_id=ch_id).first()
            if ch:
                session.delete(ch)
                return True
            return False
        except Exception as e:
            print(f"Error removing channel: {e}")
            return False

def add_file_content(category: str, content_list: list) -> int:
    """إضافة محتوى من ملف نصي"""
    if not content_list:
        return 0
        
    with get_db_session() as session:
        count = 0
        
        if category == 'ابيات شعرية':
            poems = []
            current_poem = []
            
            for line in content_list:
                text = line.strip()
                
                if '-----' in text:
                    if current_poem:
                        poems.append("\n".join(current_poem))
                        current_poem = []
                elif text and not text.startswith('الشاعر:'):
                    current_poem.append(text)
            
            if current_poem:
                poems.append("\n".join(current_poem))
            
            for poem in poems:
                session.add(FileContent(category=category, content=poem))
                count += 1
        else:
            for text in content_list:
                if text.strip():
                    session.add(FileContent(category=category, content=text.strip()))
                    count += 1
        
        return count

def get_next_content(category: str) -> str:
    """الحصول على محتوى عشوائي من الفئة"""
    with get_db_session() as session:
        # استخدام func.rand() لـ MySQL بدلاً من random
        from sqlalchemy import func
        content = session.query(FileContent).filter_by(category=category).order_by(func.rand()).first()
        return content.content if content else None

def get_stats() -> str:
    """الحصول على إحصائيات البوت"""
    with get_db_session() as session:
        users_count = session.query(User).count()
        channels_count = session.query(Channel).count()
        posts_count = session.query(FileContent).count()
        
        return (f"📊 <b>إحصائيات البوت:</b>\n"
                f"👥 المستخدمين: {users_count}\n"
                f"📢 القنوات: {channels_count}\n"
                f"📝 الرسائل المخزنة: {posts_count}")

# --- دوال إضافية مفيدة ---

def init_admin(user_id: int, username: str = None):
    """تهيئة أول مشرف للبوت"""
    with get_db_session() as session:
        existing = session.query(User).filter_by(user_id=user_id).first()
        if not existing:
            admin = User(user_id=user_id, username=username, is_admin=True)
            session.add(admin)
            print(f"Admin initialized: {user_id}")

def get_all_channels():
    """جلب جميع القنوات النشطة"""
    with get_db_session() as session:
        return session.query(Channel).filter_by(is_active=True).all()

def update_channel_last_post(channel_id: int):
    """تحديث وقت آخر نشر للقناة"""
    with get_db_session() as session:
        ch = session.query(Channel).filter_by(channel_id=channel_id).first()
        if ch:
            ch.last_post_at = datetime.now()