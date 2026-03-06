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
# Railway يعطي DATABASE_URL تلقائياً عند إضافة MySQL
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # تحويل mysql:// إلى mysql+pymysql://
    if DATABASE_URL.startswith('mysql://'):
        DATABASE_URL = DATABASE_URL.replace('mysql://', 'mysql+pymysql://', 1)
    print(f"✅ Using Railway DATABASE_URL")
else:
    # Fallback للتطوير المحلي فقط
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'telegram_bot')
    
    if DB_PASSWORD:
        DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        DATABASE_URL = None

# === Validation ===
def validate_config():
    errors = []
    
    if not TOKEN:
        errors.append("❌ TOKEN غير موجود!")
    if not DEVELOPER_ID:
        errors.append("❌ DEVELOPER_ID غير موجود!")
    if not DATABASE_URL:
        errors.append("❌ DATABASE_URL غير موجود! أضف MySQL في Railway.")
    
    if errors:
        raise ValueError("\n".join(errors))
    
    print("✅ All configurations loaded successfully!")
    print(f"🗄️  Database: Railway MySQL")

# تشغيل التحقق
validate_config()
