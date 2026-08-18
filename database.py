import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# جلب رابط قاعدة البيانات السحابية من إعدادات Render
# (وإذا لم يجده، سيستخدم SQLite للتجارب المحلية على جهازك)
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mawasem.db")

# تصحيح بسيط: SQLAlchemy يفضل أن يبدأ الرابط بـ postgresql:// وليس postgres://
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# إعداد محرك الاتصال بناءً على نوع القاعدة
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # إعدادات خاصة بـ SQLite فقط
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # إعدادات PostgreSQL السحابية
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()