import hashlib
import jwt
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext

import models
import schemas
from database import engine, SessionLocal

# إنشاء الجداول إذا لم تكن موجودة
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mawasem Backend", version="1.0")

# إعداد CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# دالة الاتصال بقاعدة البيانات
# ==========================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==========================================
# إعدادات التشفير والمفاتيح
# ==========================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "mawasem_super_secret_key_2026" # مفتاح سري لتشفير التوكن
ALGORITHM = "HS256"

def get_password_hash(password: str):
    # 1. تحويل كلمة المرور مهما كان طولها إلى نص مشفر ثابت الطول
    sha256_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    # 2. نمررها لـ bcrypt
    return pwd_context.hash(sha256_password)

def verify_password(plain_password: str, hashed_password: str):
    # نمرر الباسوورد المدخل بنفس طريقة التشفير للمقارنة
    sha256_password = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return pwd_context.verify(sha256_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    # التوكن صالح لمدة 7 أيام
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ==========================================
# دالة حارس البوابة (للتحقق من هوية المستخدم)
# ==========================================
security = HTTPBearer()

# ==========================================
# دالة حارس البوابة (النسخة المحدثة)
# ==========================================
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    # مكتبة HTTPBearer تقوم تلقائياً بفصل كلمة Bearer وإعطائنا التوكن الصافي
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="توكن غير صالح")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="انتهت صلاحية الجلسة، يرجى تسجيل الدخول مجدداً")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="توكن غير صالح")
        
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise HTTPException(status_code=401, detail="المستخدم غير موجود")
        
    return user


# ==========================================
# دالة التحقق من صلاحيات الإدارة (حماية لوحة التحكم)
# ==========================================
def get_current_admin(current_user: models.User = Depends(get_current_user)):
    # ضع رقم هاتفك الذي سجلت به حسابك كمدير هنا
    ADMIN_PHONE = "0576394221" 
    
    if current_user.phone_number != ADMIN_PHONE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="غير مصرح لك بالوصول إلى لوحة التحكم"
        )
    return current_user

# ==========================================
# مسارات الواجهة البرمجية (API Routes)
# ==========================================

@app.get("/")
def read_root():
    return {"message": "مرحباً بك في خادم متجر مواسم (Backend Active)"}

@app.post("/api/register")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. التحقق مما إذا كان رقم الهاتف مسجلاً مسبقاً
    existing_user = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل بالفعل في النظام")
    
    # 2. تشفير كلمة المرور
    hashed_password = get_password_hash(user.password)
    
    # 3. إنشاء المستخدم الجديد وحفظه في قاعدة البيانات
    new_user = models.User(
        full_name=user.full_name,
        phone_number=user.phone_number,
        password_hash=hashed_password
    )
    
    db.add(new_user)
    db.commit() # تأكيد الحفظ
    db.refresh(new_user)
    
    return {"message": "تم إنشاء الحساب بنجاح!", "user_id": new_user.id}

@app.post("/api/login")
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    # 1. البحث عن المستخدم برقم الهاتف
    db_user = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
    
    # 2. التحقق من وجود المستخدم وصحة كلمة المرور
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="رقم الهاتف أو كلمة المرور غير صحيحة")
    
    # 3. إنشاء مفتاح الدخول (Token)
    access_token = create_access_token(data={"sub": str(db_user.id)})
    
    return {
        "message": "تم تسجيل الدخول بنجاح",
        "access_token": access_token,
        "token_type": "bearer",
        "user_name": db_user.full_name
    }

# ==========================================
# مسارات سلة المشتريات (محمية)
# ==========================================

@app.post("/api/cart/add")
def add_to_cart(item: schemas.CartItemCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # التحقق مما إذا كان المنتج موجوداً مسبقاً في سلة هذا المستخدم
    existing_item = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == item.product_id
    ).first()

    if existing_item:
        # إذا كان موجوداً، نزيد الكمية فقط
        existing_item.quantity += item.quantity
    else:
        # إذا كان جديداً، نضيفه كعنصر جديد في القاعدة
        new_item = models.CartItem(
            user_id=current_user.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        db.add(new_item)
    
    db.commit()
    return {"message": "تمت إضافة المنتج للسلة بنجاح"}

@app.get("/api/cart")
def view_cart(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    # جلب جميع المنتجات الموجودة في سلة هذا المستخدم تحديداً
    cart_items = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    return {"cart": cart_items}

# ==========================================
# مسار حذف منتج من السلة
# ==========================================
@app.delete("/api/cart/remove/{product_id}")
def remove_from_cart(product_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # البحث عن المنتج داخل سلة المستخدم الحالي
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="المنتج غير موجود في السلة")
        
    # حذف المنتج وحفظ التغييرات
    db.delete(cart_item)
    db.commit()
    
    return {"message": "تم حذف المنتج من السلة بنجاح"}

# ==========================================
# مسار تحديث كمية المنتج في السلة
# ==========================================
@app.put("/api/cart/update/{product_id}")
def update_cart_quantity(product_id: str, quantity: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # البحث عن المنتج داخل سلة المستخدم
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="المنتج غير موجود في السلة")
        
    # إذا كانت الكمية 0 أو أقل، نحذف المنتج
    if quantity <= 0:
        db.delete(cart_item)
    else:
        # تحديث الكمية
        cart_item.quantity = quantity
        
    db.commit()
    return {"message": "تم تحديث الكمية بنجاح"}

@app.get("/api/settings/delivery")
def get_delivery_fee(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    fee = setting.value if setting else "0"
    return {"delivery_fee": fee}

@app.put("/api/admin/settings/delivery")
def update_delivery_fee(fee: str, db: Session = Depends(get_db)):
    setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    if not setting:
        setting = models.Setting(key="delivery_fee", value=fee)
        db.add(setting)
    else:
        setting.value = fee
    db.commit()
    return {"message": "تم تحديث رسوم التوصيل بنجاح"}

@app.get("/api/settings/delivery")
def get_delivery_fee(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    fee = setting.value if setting else "مجاني"
    return {"delivery_fee": fee}

@app.put("/api/admin/settings/delivery")
def update_delivery_fee(fee: str, db: Session = Depends(get_db)):
    setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    if not setting:
        setting = models.Setting(key="delivery_fee", value=fee)
        db.add(setting)
    else:
        setting.value = fee
    db.commit()
    return {"message": "تم تحديث رسوم التوصيل بنجاح"}



import csv
from fastapi.responses import StreamingResponse
import io

@app.get("/api/admin/export-users")
def export_users_to_excel(db: Session = Depends(get_db)):
    users = db.query(models.User.full_name, models.User.phone_number).all()
    if not users:
        raise HTTPException(status_code=404, detail="لا يوجد مستخدمون مسجلون")
    
    # إنشاء ملف CSV في الذاكرة الحية (يمكّن فتحه ببرنامج الإكسل مباشرة)
    output = io.StringIO()
    # كتابة علامة البايت BOM لدعم اللغة العربية بشكل صحيح في برامج الأوفيس
    output.write('\ufeff')
    
    writer = csv.writer(output)
    # كتابة رأس الجدول
    writer.writerow(['الاسم', 'رقم الهاتف'])
    
    # كتابة بيانات العملاء
    for u in users:
        writer.writerow([u.full_name, u.phone_number])
    
    output.seek(0)
    
    # إرسال الملف للتحميل المباشر
    response = StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv; charset=utf-8"
    )
    response.headers["Content-Disposition"] = "attachment; filename=mawasem_customers.csv"
    return response


# لاحظ إضافة admin: models.User = Depends(get_current_admin)
@app.post("/api/admin/settings/delivery")
def update_delivery_fee(new_fee: str, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    # تم تغيير Setting إلى models.Setting في الاستعلام
    fee_setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    
    if fee_setting:
        fee_setting.value = new_fee
    else:
        # تم التغيير هنا أيضاً عند إنشاء إعداد جديد
        new_setting = models.Setting(key="delivery_fee", value=new_fee)
        db.add(new_setting)
        
    db.commit()
    return {"message": "تم تحديث رسوم التوصيل بنجاح"}