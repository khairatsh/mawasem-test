from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# مسار ملف قاعدة بيانات SQLite الذي سيتم إنشاؤه
SQLALCHEMY_DATABASE_URL = "sqlite:///./mawasem.db"

# إنشاء محرك الاتصال (engine)
# check_same_thread=False مطلوب فقط مع SQLite لتفادي مشاكل الاتصال المتعدد
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# إنشاء "جلسة" للتحدث مع قاعدة البيانات
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# الصنف الأساسي الذي سنبني عليه جداولنا
Base = declarative_base()