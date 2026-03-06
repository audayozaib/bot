# استخدام Python 3.11 كأساس
FROM python:3.11-slim

# تعيين مجلد العمل
WORKDIR /app

# تثبيت المتطلبات الأساسية
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# إنشاء مجلد للبيانات (اختياري للملفات المؤقتة)
RUN mkdir -p /app/data

# تشغيل البوت
CMD ["python", "Mybot-main/main.py"]
