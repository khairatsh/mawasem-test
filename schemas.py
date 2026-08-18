from pydantic import BaseModel

# هذا الكلاس يمثل البيانات التي سيرسلها المستخدم عند التسجيل
class UserCreate(BaseModel):
    full_name: str
    phone_number: str
    password: str

    
# هذا الكلاس يمثل البيانات المطلوبة لتسجيل الدخول
class UserLogin(BaseModel):
    phone_number: str
    password: str

# ==========================================
# بيانات سلة المشتريات
# ==========================================
class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = 1

class CartItemResponse(BaseModel):
    id: int
    product_id: str
    quantity: int
    
    class Config:
        from_attributes = True