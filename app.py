# app.py - الملف الرئيسي للخادم المحسن

from flask import Flask, request, jsonify, session, send_from_directory # أضفنا send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets
import os
import json

# إنشاء التطبيق
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tailoring_shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# إعداد قاعدة البيانات والـ CORS
# تأكد من تفعيل supports_credentials للسماح بإرسال الكوكيز (الجلسات)
CORS(app, supports_credentials=True)
db = SQLAlchemy(app)

# ========== النماذج (Models) ==========

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(200))
    address = db.Column(db.Text)
    city = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'city': self.city,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'image_url': self.image_url,
            'product_count': len([p for p in self.products if p.is_active])
        }

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    discount_price = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    category = db.relationship('Category', backref='products')
    image_url = db.Column(db.String(200))
    additional_images = db.Column(db.Text)  # JSON string of image URLs
    in_stock = db.Column(db.Boolean, default=True)
    stock_quantity = db.Column(db.Integer, default=0)
    is_featured = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    sizes = db.Column(db.Text)  # JSON string of available sizes
    colors = db.Column(db.Text)  # JSON string of available colors
    material = db.Column(db.String(100))
    care_instructions = db.Column(db.Text)
    delivery_time = db.Column(db.String(50))  # مدة التسليم
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'discount_price': self.discount_price,
            'final_price': self.discount_price if self.discount_price else self.price,
            'has_discount': bool(self.discount_price),
            'category': self.category.name if self.category else None,
            'category_id': self.category_id,
            'image': self.image_url or f"https://via.placeholder.com/300x250?text={self.name}",
            'additional_images': json.loads(self.additional_images) if self.additional_images else [],
            'in_stock': self.in_stock,
            'stock_quantity': self.stock_quantity,
            'is_featured': self.is_featured,
            'sizes': json.loads(self.sizes) if self.sizes else [],
            'colors': json.loads(self.colors) if self.colors else [],
            'material': self.material,
            'care_instructions': self.care_instructions,
            'delivery_time': self.delivery_time,
            'views_count': self.views_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, default=1)
    selected_size = db.Column(db.String(20))
    selected_color = db.Column(db.String(30))
    notes = db.Column(db.Text)  # ملاحظات خاصة للتفصيل
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='cart_items')
    product = db.relationship('Product', backref='cart_items')
    
    def to_dict(self):
        product_dict = self.product.to_dict()
        return {
            'id': self.id,
            'product': product_dict,
            'quantity': self.quantity,
            'selected_size': self.selected_size,
            'selected_color': self.selected_color,
            'notes': self.notes,
            'unit_price': product_dict['final_price'],
            'total_price': product_dict['final_price'] * self.quantity
        }

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, in_progress, ready, delivered, cancelled
    payment_status = db.Column(db.String(20), default='pending')  # pending, partial, paid
    payment_method = db.Column(db.String(30))
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    customer_address = db.Column(db.Text)
    delivery_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    admin_notes = db.Column(db.Text)  # ملاحظات إدارية
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='orders')
    
    def to_dict(self):
        return {
            'id': self.id,
            'order_number': self.order_number,
            'user_id': self.user_id,
            'total_amount': self.total_amount,
            'status': self.status,
            'status_text': self.get_status_text(),
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_address': self.customer_address,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'notes': self.notes,
            'admin_notes': self.admin_notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'items': [item.to_dict() for item in self.order_items]
        }
    
    def get_status_text(self):
        status_map = {
            'pending': 'في الانتظار',
            'confirmed': 'مؤكد',
            'in_progress': 'قيد التنفيذ',
            'ready': 'جاهز للاستلام',
            'delivered': 'مُسلم',
            'cancelled': 'ملغي'
        }
        return status_map.get(self.status, self.status)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)  # سعر المنتج وقت الطلب
    selected_size = db.Column(db.String(20))
    selected_color = db.Column(db.String(30))
    notes = db.Column(db.Text)
    
    order = db.relationship('Order', backref='order_items')
    product = db.relationship('Product')
    
    def to_dict(self):
        return {
            'id': self.id,
            'product': self.product.to_dict() if self.product else None,
            'quantity': self.quantity,
            'price': self.price,
            'selected_size': self.selected_size,
            'selected_color': self.selected_color,
            'notes': self.notes,
            'total': self.price * self.quantity
        }

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    replied = db.Column(db.Boolean, default=False)
    reply_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'subject': self.subject,
            'message': self.message,
            'is_read': self.is_read,
            'replied': self.replied,
            'reply_message': self.reply_message,
            'created_at': self.created_at.isoformat()
        }

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    title = db.Column(db.String(200))
    comment = db.Column(db.Text)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='reviews')
    product = db.relationship('Product', backref='reviews')
    order = db.relationship('Order', backref='reviews')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_name': self.user.name if self.user else 'مستخدم',
            'rating': self.rating,
            'title': self.title,
            'comment': self.comment,
            'created_at': self.created_at.isoformat()
        }

# ========== المساعدات (Helper Functions) ==========

def generate_order_number():
    """توليد رقم طلب فريد"""
    import random
    import string
    while True:
        number = ''.join(random.choices(string.digits, k=8))
        if not Order.query.filter_by(order_number=number).first():
            return number

def init_sample_data():
    """إضافة بيانات تجريبية محسنة"""
    if Category.query.count() == 0:
        categories = [
            Category(name='فساتين سهرة', description='فساتين أنيقة للمناسبات الخاصة والحفلات', 
                    image_url='https://via.placeholder.com/200x150?text=فساتين+سهرة'),
            Category(name='ملابس تراثية', description='ملابس تراثية أصيلة ومطرزة بالطريقة التقليدية', 
                    image_url='https://via.placeholder.com/200x150?text=ملابس+تراثية'),
            Category(name='ملابس أطفال', description='ملابس مريحة وجميلة للأطفال من جميع الأعمار', 
                    image_url='https://via.placeholder.com/200x150?text=ملابس+أطفال'),
            Category(name='عبايات', description='عبايات عصرية وكلاسيكية بتصاميم راقية', 
                    image_url='https://via.placeholder.com/200x150?text=عبايات'),
            Category(name='فساتين زفاف', description='فساتين زفاف فاخرة لليلة العمر', 
                    image_url='https://via.placeholder.com/200x150?text=فساتين+زفاف'),
            Category(name='ملابس محجبات', description='أزياء عصرية مناسبة للمحجبات', 
                    image_url='https://via.placeholder.com/200x150?text=ملابس+محجبات')
        ]
        
        for category in categories:
            db.session.add(category)
        
        db.session.commit()
        print("تم إضافة الفئات بنجاح")
    
    if Product.query.count() == 0:
        products = [
            Product(
                name="فستان سهرة راقي مطرز",
                description="فستان سهرة أنيق مصنوع من الساتان الفاخر مع تطريز يدوي راقي، مناسب للمناسبات الخاصة والحفلات الراقية",
                price=1200,
                discount_price=950,
                category_id=1,
                image_url="https://via.placeholder.com/400x500?text=فستان+سهرة+راقي",
                in_stock=True,
                stock_quantity=5,
                is_featured=True,
                sizes='["S", "M", "L", "XL"]',
                colors='["أحمر", "أسود", "أزرق ملكي", "ذهبي"]',
                material="ساتان فاخر مع تطريز يدوي",
                care_instructions="تنظيف جاف فقط",
                delivery_time="7-10 أيام عمل"
            ),
            Product(
                name="جلباب تراثي مطرز بالخيوط الذهبية",
                description="جلباب تراثي أصيل مطرز بالخيوط الذهبية والفضية، يجمع بين الأصالة والعصرية في تصميم راقي",
                price=800,
                category_id=2,
                image_url="https://via.placeholder.com/400x500?text=جلباب+تراثي",
                in_stock=True,
                stock_quantity=8,
                is_featured=True,
                sizes='["S", "M", "L", "XL", "XXL"]',
                colors='["أسود", "كحلي", "بني", "أخضر داكن"]',
                material="قطن مخلوط مع تطريز ذهبي",
                care_instructions="غسيل يدوي بماء بارد",
                delivery_time="5-7 أيام عمل"
            ),
            Product(
                name="فستان أطفال ملون بتصميم الأميرات",
                description="فستان أطفال بألوان زاهية ومرحة مع تصميم الأميرات، مصنوع من القطن الطبيعي المريح والآمن للأطفال",
                price=350,
                discount_price=280,
                category_id=3,
                image_url="https://via.placeholder.com/400x500?text=فستان+أطفال",
                in_stock=True,
                stock_quantity=12,
                is_featured=False,
                sizes='["2-3 سنوات", "4-5 سنوات", "6-7 سنوات", "8-9 سنوات"]',
                colors='["وردي", "أزرق فاتح", "أصفر", "بنفسجي"]',
                material="قطن طبيعي 100%",
                care_instructions="غسيل عادي في الغسالة",
                delivery_time="3-5 أيام عمل"
            ),
            Product(
                name="عباية عصرية بقصة مودرن",
                description="عباية عصرية بتصميم مودرن وأنيق مع تفاصيل راقية، مناسبة لجميع المناسبات اليومية والرسمية",
                price=550,
                category_id=4,
                image_url="https://via.placeholder.com/400x500?text=عباية+عصرية",
                in_stock=True,
                stock_quantity=15,
                is_featured=True,
                sizes='["S", "M", "L", "XL", "XXL"]',
                colors='["أسود", "كحلي", "رمادي", "بيج"]',
                material="كريب مطاطي عالي الجودة",
                care_instructions="غسيل عادي أو تنظيف جاف",
                delivery_time="3-5 أيام عمل"
            ),
            Product(
                name="فستان زفاف فاخر بتطريز اللؤلؤ",
                description="فستان زفاف حالم بتصميم كلاسيكي فاخر، مطرز بالخرز واللؤلؤ الطبيعي مع ذيل طويل أنيق",
                price=3500,
                discount_price=2800,
                category_id=5,
                image_url="https://via.placeholder.com/400x500?text=فستان+زفاف",
                in_stock=True,
                stock_quantity=3,
                is_featured=True,
                sizes='["XS", "S", "M", "L", "XL"]',
                colors='["أبيض", "أبيض مكسور", "شامبين"]',
                material="ساتان وتول مع تطريز لؤلؤ طبيعي",
                care_instructions="تنظيف جاف متخصص فقط",
                delivery_time="14-21 يوم عمل"
            ),
            Product(
                name="فستان محجبات أنيق وعملي",
                description="فستان طويل مناسب للمحجبات، بتصميم عصري ومريح مع أكمام طويلة وقصة مناسبة",
                price=480,
                category_id=6,
                image_url="https://via.placeholder.com/400x500?text=فستان+محجبات",
                in_stock=True,
                stock_quantity=20,
                is_featured=False,
                sizes='["S", "M", "L", "XL", "XXL"]',
                colors='["كحلي", "بني", "أخضر", "بنفسجي", "رمادي"]',
                material="جيرسي قطني مريح",
                care_instructions="غسيل عادي في الغسالة",
                delivery_time="3-5 أيام عمل"
            )
        ]
        
        for product in products:
            db.session.add(product)
        
        db.session.commit()
        print("تم إضافة المنتجات بنجاح")
    
    # إضافة مستخدم إداري
    if not User.query.filter_by(email='admin@ummohamed.com').first():
        admin = User(
            name='إدارة أم محمد',
            email='admin@ummohamed.com',
            phone='0123456789',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("تم إضافة المستخدم الإداري")

# ========== المسارات (Routes) ==========

# المسار لخدمة ملف index.html
@app.route('/')
def serve_index():
    # سيتم البحث عن index.html داخل مجلد 'static'
    return send_from_directory('static', 'index.html')

@app.route('/api/categories', methods=['GET'])
def get_categories():
    categories = Category.query.filter_by(is_active=True).order_by(Category.sort_order).all()
    return jsonify([cat.to_dict() for cat in categories])

@app.route('/api/products', methods=['GET'])
def get_products():
    category_id = request.args.get('category_id')
    featured_only = request.args.get('featured') == 'true'
    search_query = request.args.get('search', '').strip()
    
    query = Product.query.filter_by(is_active=True)
    
    if category_id:
        query = query.filter_by(category_id=category_id)
    
    if featured_only:
        query = query.filter_by(is_featured=True)
    
    if search_query:
        query = query.filter(Product.name.contains(search_query) | Product.description.contains(search_query))
    
    products = query.order_by(Product.created_at.desc()).all()
    return jsonify([product.to_dict() for product in products])

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product:
        return jsonify({'error': 'المنتج غير موجود'}), 404
    
    # زيادة عدد المشاهدات
    product.views_count += 1
    db.session.commit()
    
    # جلب التقييمات
    reviews = Review.query.filter_by(product_id=product_id, is_approved=True).order_by(Review.created_at.desc()).all()
    
    product_data = product.to_dict()
    product_data['reviews'] = [review.to_dict() for review in reviews]
    product_data['average_rating'] = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
    
    return jsonify(product_data)

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # التحقق من البيانات المطلوبة
    required_fields = ['name', 'email', 'phone', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'حقل {field} مطلوب'}), 400
    
    # التحقق من وجود المستخدم
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'البريد الإلكتروني مستخدم بالفعل'}), 400
    
    # إنشاء مستخدم جديد
    user = User(
        name=data['name'],
        email=data['email'],
        phone=data['phone'],
        address=data.get('address', ''),
        city=data.get('city', '')
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'تم إنشاء الحساب بنجاح',
        'user': user.to_dict()
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'البريد الإلكتروني وكلمة المرور مطلوبان'}), 400
    
    user = User.query.filter_by(email=email, is_active=True).first()
    
    if not user or not user.check_password(password):
        return jsonify({'error': 'البريد الإلكتروني أو كلمة المرور غير صحيحة'}), 401
    
    # تحديث آخر تسجيل دخول
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # حفظ معلومات المستخدم في الجلسة
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['is_admin'] = user.is_admin
    
    print(f"User {user.name} logged in. Session user_id: {session.get('user_id')}") # إضافة لغرض التصحيح
    
    return jsonify({
        'message': 'تم تسجيل الدخول بنجاح',
        'user': user.to_dict()
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    print("User logged out. Session cleared.") # إضافة لغرض التصحيح
    return jsonify({'message': 'تم تسجيل الخروج بنجاح'})

@app.route('/api/cart', methods=['GET'])
def get_cart():
    user_id = session.get('user_id')
    print(f"Getting cart for user_id: {user_id}") # إضافة لغرض التصحيح
    if not user_id:
        return jsonify({'items': [], 'total': 0, 'count': 0}), 200 # Return 200 for empty cart when not logged in
    
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    items = [item.to_dict() for item in cart_items]
    total = sum(item['total_price'] for item in items)
    
    return jsonify({
        'items': items,
        'total': total,
        'count': len(items)
    })

@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    user_id = session.get('user_id')
    print(f"Adding to cart for user_id: {user_id}") # إضافة لغرض التصحيح
    if not user_id:
        return jsonify({'error': 'يجب تسجيل الدخول أولاً لإضافة منتجات إلى السلة'}), 401
    
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    selected_size = data.get('selected_size')
    selected_color = data.get('selected_color')
    notes = data.get('notes', '')
    
    if not product_id:
        return jsonify({'error': 'معرف المنتج مطلوب'}), 400
    
    product = Product.query.filter_by(id=product_id, is_active=True).first()
    if not product:
        return jsonify({'error': 'المنتج غير موجود'}), 404
    
    if not product.in_stock or product.stock_quantity < quantity:
        return jsonify({'error': 'المنتج غير متوفر بالكمية المطلوبة حالياً'}), 400
    
    # البحث عن العنصر في السلة بنفس الخصائص
    existing_item = CartItem.query.filter_by(
        user_id=user_id,
        product_id=product_id,
        selected_size=selected_size,
        selected_color=selected_color
    ).first()
    
    if existing_item:
        existing_item.quantity += quantity
    else:
        cart_item = CartItem(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            selected_size=selected_size,
            selected_color=selected_color,
            notes=notes
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    return jsonify({
        'message': 'تم إضافة المنتج إلى السلة بنجاح',
        'cart': get_cart().json # Return updated cart data
    }), 200

@app.route('/api/cart/update/<int:item_id>', methods=['PUT'])
def update_cart_item(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'يرجى تسجيل الدخول لتعديل السلة'}), 401
    
    data = request.get_json()
    quantity = data.get('quantity')
    selected_size = data.get('selected_size')
    selected_color = data.get('selected_color')
    notes = data.get('notes', '')

    cart_item = CartItem.query.filter_by(id=item_id, user_id=user_id).first()

    if not cart_item:
        return jsonify({'error': 'عنصر السلة غير موجود'}), 404
    
    product = Product.query.get(cart_item.product_id)
    if not product:
        return jsonify({'error': 'المنتج المرتبط بعنصر السلة غير موجود'}), 404

    if quantity is not None:
        if quantity <= 0:
            db.session.delete(cart_item)
            db.session.commit()
            return jsonify({'message': 'تم حذف المنتج من السلة', 'cart': get_cart().json}), 200
        
        if product.stock_quantity < quantity:
            return jsonify({'error': 'الكمية المطلوبة غير متوفرة'}), 400
        cart_item.quantity = quantity
    
    if selected_size is not None:
        cart_item.selected_size = selected_size
    if selected_color is not None:
        cart_item.selected_color = selected_color
    if notes is not None:
        cart_item.notes = notes

    db.session.commit()
    return jsonify({
        'message': 'تم تحديث السلة بنجاح',
        'cart': get_cart().json
    })

@app.route('/api/cart/remove/<int:item_id>', methods=['DELETE'])
def remove_from_cart(item_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'يرجى تسجيل الدخول لحذف عناصر من السلة'}), 401
    
    cart_item = CartItem.query.filter_by(id=item_id, user_id=user_id).first()
    
    if not cart_item:
        return jsonify({'error': 'عنصر السلة غير موجود'}), 404
    
    db.session.delete(cart_item)
    db.session.commit()
    
    return jsonify({
        'message': 'تم حذف المنتج من السلة بنجاح',
        'cart': get_cart().json
    }), 200

@app.route('/api/cart/clear', methods=['POST'])
def clear_cart():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'يرجى تسجيل الدخول لإفراغ السلة'}), 401
    
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    
    return jsonify({
        'message': 'تم إفراغ السلة بنجاح',
        'cart': get_cart().json
    }), 200

@app.route('/api/orders', methods=['POST'])
def create_order():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'يجب تسجيل الدخول لإتمام الطلب'}), 401
    
    data = request.get_json()
    customer_name = data.get('customer_name')
    customer_phone = data.get('customer_phone')
    customer_address = data.get('customer_address')
    payment_method = data.get('payment_method', 'Cash on Delivery')
    notes = data.get('notes', '')

    if not customer_name or not customer_phone or not customer_address:
        return jsonify({'error': 'الاسم ورقم الهاتف والعنوان مطلوبون لإتمام الطلب'}), 400
    
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    if not cart_items:
        return jsonify({'error': 'السلة فارغة لا يمكن إنشاء طلب'}), 400
    
    total_amount = sum(item.product.final_price * item.quantity for item in cart_items)
    
    order = Order(
        order_number=generate_order_number(),
        user_id=user_id,
        total_amount=total_amount,
        status='pending',
        payment_status='pending',
        payment_method=payment_method,
        customer_name=customer_name,
        customer_phone=customer_phone,
        customer_address=customer_address,
        notes=notes
    )
    db.session.add(order)
    db.session.commit() # Commit to get order.id

    for item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=item.product.final_price,
            selected_size=item.selected_size,
            selected_color=item.selected_color,
            notes=item.notes
        )
        db.session.add(order_item)
        # Optionally reduce stock quantity here
        # product = Product.query.get(item.product_id)
        # if product:
        #    product.stock_quantity -= item.quantity
    
    db.session.commit()
    
    # Clear cart after creating order
    CartItem.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    
    return jsonify({
        'message': 'تم إنشاء طلبك بنجاح',
        'order': order.to_dict()
    }), 201

@app.route('/api/orders', methods=['GET'])
def get_user_orders():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'يرجى تسجيل الدخول لعرض الطلبات'}), 401
    
    orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
    return jsonify([order.to_dict() for order in orders])

@app.route('/api/contact', methods=['POST'])
def submit_contact_message():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    subject = data.get('subject', 'استفسار عام')
    message = data.get('message')

    if not name or not message:
        return jsonify({'error': 'الاسم والرسالة مطلوبان'}), 400
    
    contact_message = ContactMessage(
        name=name,
        email=email,
        phone=phone,
        subject=subject,
        message=message
    )
    db.session.add(contact_message)
    db.session.commit()

    return jsonify({'message': 'تم إرسال رسالتك بنجاح!'}), 201

@app.route('/api/reviews', methods=['POST'])
def add_review():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'يجب تسجيل الدخول لإضافة تقييم'}), 401
    
    data = request.get_json()
    product_id = data.get('product_id')
    rating = data.get('rating')
    title = data.get('title')
    comment = data.get('comment')
    order_id = data.get('order_id') # Optional, for linking review to a specific order

    if not product_id or not rating:
        return jsonify({'error': 'معرف المنتج والتقييم مطلوبان'}), 400
    
    if not (1 <= rating <= 5):
        return jsonify({'error': 'يجب أن يكون التقييم بين 1 و 5'}), 400
    
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'المنتج غير موجود'}), 404

    review = Review(
        user_id=user_id,
        product_id=product_id,
        order_id=order_id,
        rating=rating,
        title=title,
        comment=comment,
        is_approved=False # Admin needs to approve reviews
    )
    db.session.add(review)
    db.session.commit()

    return jsonify({'message': 'تم إرسال تقييمك بنجاح، سيظهر بعد المراجعة.'}), 201

@app.route('/api/user', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None}), 200
    
    user = User.query.get(user_id)
    if user:
        return jsonify({'user': user.to_dict()}), 200
    return jsonify({'user': None}), 200


# إنشاء الجداول عند تشغيل التطبيق لأول مرة
with app.app_context():
    db.create_all()
    init_sample_data()

if __name__ == '__main__':
    app.run(debug=True)