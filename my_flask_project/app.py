from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets
import os

# تنظیمات
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-12345-change-this'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///new_messaging_app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

# مدل‌های پایگاه داده
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, unique=True)
    user_id = db.Column(db.String(10), unique=True, nullable=False)
    registration_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.String(10), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    receiver_id = db.Column(db.String(10), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

# ایجاد پایگاه داده جدید
def create_new_database():
    with app.app_context():
        # حذف تمام جداول
        db.drop_all()
        # ایجاد جداول جدید
        db.create_all()
        print("✅ پایگاه داده جدید ایجاد شد!")
        
        # نمایش ساختار
        print("📊 ساختار پایگاه داده:")
        print("- جدول users: id, name, phone, user_id, registration_date")
        print("- جدول private_message: id, sender_id, sender_name, receiver_id, message, timestamp, read")

# صفحه اصلی - ثبت نام و احراز هویت
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        
        # بررسی اینکه کاربر قبلاً ثبت نام نکرده باشد
        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            session['user_id'] = existing_user.user_id
            session['name'] = existing_user.name
            return redirect(url_for('dashboard'))
        
        # ایجاد شناسه کاربری منحصر به فرد
        user_id = secrets.token_hex(5).upper()
        
        # ذخیره کاربر در پایگاه داده
        user = User(name=name, phone=phone, user_id=user_id)
        db.session.add(user)
        db.session.commit()
        
        # ذخیره اطلاعات در session
        session['user_id'] = user_id
        session['name'] = name
        
        return redirect(url_for('dashboard'))
    
    return render_template('index.html')

# صفحه اصلی کاربر
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    name = session['name']
    
    # دریافت پیام‌های دریافتی
    received_messages = PrivateMessage.query.filter_by(receiver_id=user_id).order_by(PrivateMessage.timestamp.desc()).all()
    
    # دریافت پیام‌های ارسالی
    sent_messages = PrivateMessage.query.filter_by(sender_id=user_id).order_by(PrivateMessage.timestamp.desc()).all()
    
    # علامت‌گذاری پیام‌ها به عنوان خوانده شده
    for message in received_messages:
        if not message.read:
            message.read = True
    db.session.commit()
    
    return render_template('dashboard.html', 
                         name=name,
                         user_id=user_id,
                         received_messages=received_messages,
                         sent_messages=sent_messages)

# صفحه ارسال پیام خصوصی
@app.route('/send_message', methods=['GET', 'POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        receiver_id = request.form['receiver_id']
        message_text = request.form['message']
        sender_id = session['user_id']
        sender_name = session['name']
        
        # بررسی وجود کاربر دریافت‌کننده
        receiver = User.query.filter_by(user_id=receiver_id).first()
        if not receiver:
            return render_template('send_message.html', error="کاربری با این شناسه یافت نشد")
        
        # ذخیره پیام خصوصی
        private_message = PrivateMessage(
            sender_id=sender_id,
            sender_name=sender_name,
            receiver_id=receiver_id,
            message=message_text
        )
        db.session.add(private_message)
        db.session.commit()
        
        return render_template('send_message.html', success=f"پیام شما با موفقیت برای کاربر {receiver_id} ارسال شد")
    
    return render_template('send_message.html')

# API برای دریافت پیام‌های جدید
@app.route('/get_new_messages')
def get_new_messages():
    if 'user_id' not in session:
        return jsonify({'error': 'لطفاً ابتدا وارد شوید'})
    
    user_id = session['user_id']
    
    # دریافت پیام‌های خوانده نشده
    new_messages = PrivateMessage.query.filter_by(
        receiver_id=user_id, 
        read=False
    ).order_by(PrivateMessage.timestamp.desc()).all()
    
    # علامت‌گذاری به عنوان خوانده شده
    for message in new_messages:
        message.read = True
    db.session.commit()
    
    messages_data = []
    for msg in new_messages:
        messages_data.append({
            'id': msg.id,
            'sender_name': msg.sender_name,
            'sender_id': msg.sender_id,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime('%Y/%m/%d %H:%M')
        })
    
    return jsonify({'messages': messages_data})

# صفحه پنل مدیریت
@app.route('/admin')
def admin():
    # دریافت تمام کاربران
    users = User.query.order_by(User.registration_date.desc()).all()
    
    # دریافت تمام پیام‌های خصوصی
    private_messages = PrivateMessage.query.order_by(PrivateMessage.timestamp.desc()).all()
    
    return render_template('admin.html', 
                          users=users, 
                          private_messages=private_messages)

# ریست کامل پایگاه داده
@app.route('/reset')
def reset_database():
    create_new_database()
    session.clear()
    return '''
    <html dir="rtl">
    <head>
        <title>ریست پایگاه داده</title>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Tahoma; text-align: center; padding: 50px; background: #f0f0f0;">
        <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;">
            <h2 style="color: green;">✅ پایگاه داده با موفقیت ریست شد!</h2>
            <p>ساختار جدید پایگاه داده ایجاد شد.</p>
            <p><a href="/" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 20px;">بازگشت به صفحه اصلی</a></p>
        </div>
    </body>
    </html>
    '''

# خروج از سیستم
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # ایجاد پایگاه داده در اولین اجرا
    create_new_database()
    print("🌐 سرور در حال اجرا است: http://localhost:5000")
    print("🔧 برای ریست پایگاه داده: http://localhost:5000/reset")
    app.run(debug=True)