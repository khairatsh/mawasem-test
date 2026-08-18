from sqlalchemy import Column, Integer, String, ForeignKey
from database import Base

# ==========================================
# 1. جدول المستخدمين (Users Table)
# ==========================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    phone_number = Column(String, unique=True, index=True) # رقم الهاتف فريد لا يتكرر
    password_hash = Column(String) # الباسوورد المشفر

# ==========================================
# 2. جدول سلة المشتريات (Cart Items Table)
# ==========================================
class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id")) # ربط السلة بالمستخدم
    product_id = Column(String, index=True) # كود المنتج الجاي من الجافاسكريبت
    quantity = Column(Integer, default=1) # الكمية

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True) # مثال: delivery_fee
    value = Column(String) # القيمة: 0 تعني مجاني، أو رقم مثل 25