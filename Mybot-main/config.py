import os
from dotenv import load_dotenv

load_dotenv()

# === Telegram Bot ===
TOKEN = os.getenv('TOKEN')
DEVELOPER_ID = int(os.getenv('DEVELOPER_ID', '0'))

# === Pyrogram (اختياري) ===
API_ID = int(os.getenv('API_ID', '0')) if os.getenv('API_ID') else None
API_HASH = os.getenv('API_HASH')

# === Database Configuration ===
# KataBump يدعم MySQL - استخدم المتغيرات التالية
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'telegram_bot')

# بناء رابط الاتصال
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# === KataBump Specific ===
# المسار للملفات المؤقتة (KataBump يعطي /app كمسار رئيسي)
DATA_DIR = os.getenv('DATA_DIR', '/app/data')

# === Validation ===
def validate_config():
    errors = []
    
    if not TOKEN:
        errors.append("❌ TOKEN غير موجود!")
    if not DEVELOPER_ID:
        errors.append("❌ DEVELOPER_ID غير موجود!")
    if not DB_PASSWORD:
        errors.append("❌ DB_PASSWORD غير موجود!")
    
    if errors:
        raise ValueError("\n".join(errors))
    
    print("✅ All configurations loaded successfully!")
    print(f"🗄️  Database Host: {DB_HOST}")
    print(f"📁 Data Directory: {DATA_DIR}")

# تشغيل التحقق عند الاستيراد
validate_config()