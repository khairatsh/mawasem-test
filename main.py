import hashlib
import jwt
from datetime import datetime, timedelta, timezone
import csv
import io

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
SECRET_KEY = "mawasem_super_secret_key_2026" 
ALGORITHM = "HS256"

def get_password_hash(password: str):
    sha256_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return pwd_context.hash(sha256_password)

def verify_password(plain_password: str, hashed_password: str):
    sha256_password = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return pwd_context.verify(sha256_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ==========================================
# دالة حارس البوابة (للتحقق من هوية المستخدم)
# ==========================================
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
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
    existing_user = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="رقم الهاتف مسجل بالفعل في النظام")
    
    hashed_password = get_password_hash(user.password)
    
    new_user = models.User(
        full_name=user.full_name,
        phone_number=user.phone_number,
        password_hash=hashed_password
    )
    
    db.add(new_user)
    db.commit() 
    db.refresh(new_user)
    
    return {"message": "تم إنشاء الحساب بنجاح!", "user_id": new_user.id}

@app.post("/api/login")
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
    
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="رقم الهاتف أو كلمة المرور غير صحيحة")
    
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
    existing_item = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == item.product_id
    ).first()

    if existing_item:
        existing_item.quantity += item.quantity
    else:
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
    cart_items = db.query(models.CartItem).filter(models.CartItem.user_id == current_user.id).all()
    return {"cart": cart_items}

@app.delete("/api/cart/remove/{product_id}")
def remove_from_cart(product_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="المنتج غير موجود في السلة")
        
    db.delete(cart_item)
    db.commit()
    return {"message": "تم حذف المنتج من السلة بنجاح"}

@app.put("/api/cart/update/{product_id}")
def update_cart_quantity(product_id: str, quantity: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cart_item = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.product_id == product_id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="المنتج غير موجود في السلة")
        
    if quantity <= 0:
        db.delete(cart_item)
    else:
        cart_item.quantity = quantity
        
    db.commit()
    return {"message": "تم تحديث الكمية بنجاح"}

# ==========================================
# مسارات الإعدادات ولوحة التحكم
# ==========================================

@app.get("/api/settings/delivery")
def get_delivery_fee(db: Session = Depends(get_db)):
    setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    fee = setting.value if setting else "مجاني"
    return {"delivery_fee": fee}

# المسار الإداري المحمي الوحيد لتحديث التوصيل
@app.post("/api/admin/settings/delivery")
def update_delivery_fee(new_fee: str, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    fee_setting = db.query(models.Setting).filter(models.Setting.key == "delivery_fee").first()
    
    if fee_setting:
        fee_setting.value = new_fee
    else:
        new_setting = models.Setting(key="delivery_fee", value=new_fee)
        db.add(new_setting)
        
    db.commit()
    return {"message": "تم تحديث رسوم التوصيل بنجاح"}

@app.get("/api/admin/export-users")
def export_users_to_excel(db: Session = Depends(get_db)):
    users = db.query(models.User.full_name, models.User.phone_number).all()
    if not users:
        raise HTTPException(status_code=404, detail="لا يوجد مستخدمون مسجلون")
    
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['الاسم', 'رقم الهاتف'])
    
    for u in users:
        writer.writerow([u.full_name, u.phone_number])
    
    output.seek(0)
    response = StreamingResponse(
        iter([output.getvalue()]), 
        media_type="text/csv; charset=utf-8"
    )
    response.headers["Content-Disposition"] = "attachment; filename=mawasem_customers.csv"
    return response