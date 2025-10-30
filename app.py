from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import os
import smtplib
import hashlib
import time
from datetime import timedelta
import random
import json
import requests
from email.mime.text import MIMEText
from email.header import Header

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(f'.env.development')
print("成功加载环境变量文件: .env.development")
print(f"应用环境: {os.environ.get('APP_ENV', 'development')}")

# 导入配置类
from config import DevelopmentConfig

# 创建Flask应用实例并应用配置
app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

# 显示数据库配置信息
print(f"数据库配置: {app.config['SQLALCHEMY_DATABASE_URI']}")

# 确保SECRET_KEY配置正确
app.secret_key = os.environ.get('SECRET_KEY', os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-for-development'))

# 邮件配置 - 生产环境应从环境变量获取
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.example.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your-email@example.com')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'your-email-password')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

# 微信配置 - 生产环境应从环境变量获取
WECHAT_APPID = os.environ.get('WECHAT_APPID', 'your-wechat-appid')
WECHAT_APPSECRET = os.environ.get('WECHAT_APPSECRET', 'your-wechat-appsecret')
WECHAT_CORP_ID = os.environ.get('WECHAT_CORP_ID', 'your-wechat-corp-id')
WECHAT_CORP_SECRET = os.environ.get('WECHAT_CORP_SECRET', 'your-wechat-corp-secret')

# 导入数据库操作函数
from app.models import get_users, save_users, get_verifications, save_verifications, get_wechat_sessions, save_wechat_sessions
from app.models.db import User, db, init_db

# 初始化数据库连接
init_db(app)

# 导入并注册auth蓝图
from app.routes.auth import bp as auth_bp
app.register_blueprint(auth_bp)

# 初始化用户数据（只在应用启动时执行一次）
with app.app_context():
    # 检查是否已有用户数据，如果没有则创建初始用户
    if User.query.count() == 0:
        # 创建初始管理员用户
        admin_user = User(
            username='admin',
            password=hashlib.sha256('password'.encode()).hexdigest(),
            email='admin@example.com'
        )
        # 创建初始普通用户
        user1 = User(
            username='user1',
            password=hashlib.sha256('user123'.encode()).hexdigest(),
            email='user1@example.com'
        )
        db.session.add_all([admin_user, user1])
        try:
            db.session.commit()
            print("初始用户数据创建成功")
        except Exception as e:
            print(f"创建初始用户失败: {e}")
            db.session.rollback()

# 生成随机验证码
def generate_verification_code():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

# 生成随机状态码用于微信登录
def generate_state():
    return hashlib.sha256(str(time.time() + random.random()).encode()).hexdigest()

# 发送验证码邮件（示例实现，实际需要配置真实的SMTP服务器）
def send_verification_email(email, code):
    try:
        # 创建邮件内容
        message = MIMEText(f'您的验证码是：{code}\n该验证码10分钟内有效，请尽快完成注册。', 'plain', 'utf-8')
        message['From'] = Header(MAIL_USERNAME, 'utf-8')
        message['To'] = Header(email, 'utf-8')
        message['Subject'] = Header('Hello World 应用 - 注册验证码', 'utf-8')
        
        # 连接SMTP服务器并发送邮件
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, [email], message.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"发送邮件失败: {e}")
        return False

# 验证验证码是否有效
def verify_code(email, code):
    verifications = get_verifications()
    if email not in verifications:
        return False
    
    verification = verifications[email]
    # 检查验证码是否正确且在有效期内（10分钟）
    if verification['code'] == code and time.time() - verification['timestamp'] < 600:
        # 验证成功后删除验证码
        del verifications[email]
        save_verifications(verifications)
        return True
    
    # 验证码过期或错误
    if time.time() - verification['timestamp'] >= 600:
        del verifications[email]
        save_verifications(verifications)
    
    return False

# 发送验证码路由
@app.route('/send_verification', methods=['POST'])
def send_verification():
    email = request.form.get('email')
    
    if not email:
        return jsonify({'success': False, 'message': '邮箱不能为空'})
    
    # 检查邮箱格式（简单验证）
    if '@' not in email:
        return jsonify({'success': False, 'message': '邮箱格式不正确'})
    
    # 检查邮箱是否已被注册
    users = get_users()
    for username, user_info in users.items():
        if user_info.get('email') == email:
            return jsonify({'success': False, 'message': '该邮箱已被注册'})
    
    # 生成验证码
    code = generate_verification_code()
    
    # 存储验证码（包含时间戳）
    verifications = get_verifications()
    verifications[email] = {
        'code': code,
        'timestamp': time.time()
    }
    save_verifications(verifications)
    
    # 发送验证码邮件
    # 打印验证码到控制台，方便测试
    print(f"[测试信息] 邮箱验证码: {code} (有效期10分钟)")
    
    # 实际部署时使用下面的代码发送邮件
    # send_success = send_verification_email(email, code)
    # if not send_success:
    #     return jsonify({'success': False, 'message': '发送验证码失败，请稍后重试'})
    
    return jsonify({'success': True, 'message': '验证码已发送，请注意查收'})

# 根路径重定向到登录页面
@app.route('/')
def index():
    # 重定向到auth蓝图中的登录页面
    return redirect(url_for('auth.login'))

# 注册页面已移至auth蓝图，此处保留重定向以确保兼容性
@app.route('/register', methods=['GET', 'POST'])
def register():
    # 重定向到auth蓝图中的注册页面
    return redirect(url_for('auth.register'))

# Hello World页面（需要登录才能访问）
@app.route('/hello')
def hello():
    # 检查用户是否已登录
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Hello World - 欢迎</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
            <script>
                tailwind.config = {
                    theme: {
                        extend: {
                            colors: {
                                primary: '#3b82f6',
                                secondary: '#10b981',
                                accent: '#8b5cf6',
                            },
                            fontFamily: {
                                sans: ['Inter', 'system-ui', 'sans-serif'],
                            },
                        }
                    }
                }
            </script>
            <style type="text/tailwindcss">
                @layer utilities {
                    .content-auto {
                        content-visibility: auto;
                    }
                    .card-shadow {
                        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
                    }
                    .bg-glass {
                        background: rgba(255, 255, 255, 0.8);
                        backdrop-filter: blur(10px);
                    }
                }
            </style>
        </head>
        <body class="bg-gradient-to-br from-blue-100 via-indigo-50 to-purple-100 min-h-screen">
            <!-- 导航栏 -->
            <header class="bg-glass sticky top-0 z-10 border-b border-gray-200/50">
                <div class="container mx-auto px-4 py-3 flex justify-between items-center">
                    <div class="flex items-center space-x-2">
                        <div class="w-10 h-10 bg-gradient-to-br from-primary to-accent rounded-full flex items-center justify-center">
                            <i class="fa fa-star text-white text-xl"></i>
                        </div>
                        <span class="font-bold text-xl text-gray-800">HelloWorld</span>
                    </div>
                    <div class="flex items-center space-x-4">
                        <div class="flex items-center space-x-2">
                            <img 
                                src="https://picsum.photos/200/200?random={{ username|hash }}" 
                                alt="用户头像" 
                                class="w-8 h-8 rounded-full object-cover border-2 border-primary/20"
                            >
                            <span class="text-gray-700 font-medium">{{ username }}</span>
                        </div>
                        <a 
                            href="{{ url_for('logout') }}" 
                            class="text-gray-600 hover:text-red-500 transition duration-200 p-2 rounded-full hover:bg-gray-100"
                            title="退出登录"
                        >
                            <i class="fa fa-sign-out"></i>
                        </a>
                    </div>
                </div>
            </header>
            
            <!-- 主内容 -->
            <main class="container mx-auto px-4 py-12 flex flex-col items-center justify-center">
                <div class="text-center mb-12">
                    <h1 class="text-5xl md:text-7xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent mb-6">
                        Hello World!
                    </h1>
                    <p class="text-xl text-gray-600 mb-8">
                        欢迎回来，<span class="text-primary font-semibold">{{ username }}</span>！很高兴再次见到你！
                    </p>
                    <div class="inline-block p-1 bg-gradient-to-r from-primary to-accent rounded-full">
                        <div class="bg-white rounded-full p-1">
                            <div class="w-16 h-16 mx-auto bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                                <i class="fa fa-heart text-white text-2xl animate-pulse"></i>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="w-full max-w-2xl bg-white rounded-2xl p-8 card-shadow">
                    <div class="flex flex-col md:flex-row items-center justify-between mb-8">
                        <div class="flex items-center mb-4 md:mb-0">
                            <img 
                                src="https://picsum.photos/200/200?random={{ username|hash }}" 
                                alt="用户头像" 
                                class="w-14 h-14 rounded-full object-cover border-3 border-primary/20 mr-4"
                            >
                            <div>
                                <h2 class="text-2xl font-bold text-gray-800">{{ username }}</h2>
                                <p class="text-gray-500">已成功登录</p>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="inline-flex items-center justify-center w-12 h-12 bg-green-100 text-green-500 rounded-full mb-2">
                                <i class="fa fa-check text-xl"></i>
                            </div>
                            <p class="text-gray-500 text-sm">登录状态正常</p>
                        </div>
                    </div>
                    
                    <div class="space-y-6">
                        <div class="p-4 bg-blue-50 rounded-xl border border-blue-100">
                            <div class="flex items-start">
                                <div class="mt-1 mr-4 text-blue-500">
                                    <i class="fa fa-info-circle text-xl"></i>
                                </div>
                                <div>
                                    <h3 class="font-semibold text-gray-800 mb-1">这是一个简单的Hello World示例</h3>
                                    <p class="text-gray-600">这是一个使用Flask框架构建的Web应用，包含用户注册、登录和基本的会话管理功能。</p>
                                </div>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div class="p-5 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl border border-gray-200">
                                <div class="flex items-center mb-3">
                                    <div class="w-10 h-10 rounded-full bg-indigo-100 flex items-center justify-center mr-3">
                                        <i class="fa fa-users text-indigo-500"></i>
                                    </div>
                                    <h3 class="font-semibold text-gray-800">用户功能</h3>
                                </div>
                                <ul class="space-y-2 text-gray-600">
                                    <li class="flex items-center">
                                        <i class="fa fa-check text-green-500 mr-2"></i>
                                        用户注册
                                    </li>
                                    <li class="flex items-center">
                                        <i class="fa fa-check text-green-500 mr-2"></i>
                                        用户登录
                                    </li>
                                    <li class="flex items-center">
                                        <i class="fa fa-check text-green-500 mr-2"></i>
                                        会话管理
                                    </li>
                                </ul>
                            </div>
                            
                            <div class="p-5 bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl border border-gray-200">
                                <div class="flex items-center mb-3">
                                    <div class="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center mr-3">
                                        <i class="fa fa-cogs text-purple-500"></i>
                                    </div>
                                    <h3 class="font-semibold text-gray-800">技术栈</h3>
                                </div>
                                <ul class="space-y-2 text-gray-600">
                                    <li class="flex items-center">
                                        <i class="fa fa-check text-green-500 mr-2"></i>
                                        Python Flask
                                    </li>
                                    <li class="flex items-center">
                                        <i class="fa fa-check text-green-500 mr-2"></i>
                                        Tailwind CSS
                                    </li>
                                    <li class="flex items-center">
                                        <i class="fa fa-check text-green-500 mr-2"></i>
                                        Font Awesome
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-8 text-center">
                        <a 
                            href="{{ url_for('logout') }}" 
                            class="inline-flex items-center justify-center px-6 py-3 bg-red-50 hover:bg-red-100 text-red-600 font-medium rounded-lg transition duration-200"
                        >
                            <i class="fa fa-sign-out mr-2"></i> 退出登录
                        </a>
                    </div>
                </div>
            </main>
            
            <!-- 页脚 -->
            <footer class="mt-16 py-8 bg-white border-t border-gray-200">
                <div class="container mx-auto px-4 text-center text-gray-500">
                    <p>© 2024 Hello World 应用 | 使用 Flask 和 Tailwind CSS 构建</p>
                </div>
            </footer>
        </body>
        </html>
    ''', username=session['username'])

# 微信登录路由（个人微信）已移至auth蓝图，此处保留重定向以确保兼容性
@app.route('/wechat_login')
def wechat_login():
    # 重定向到auth蓝图中的企业微信登录页面
    return redirect(url_for('auth.wechat_corp_login'))

# 企业微信登录路由已移至auth蓝图，此处保留重定向以确保兼容性
@app.route('/wechat_corp_login')
def wechat_corp_login():
    # 重定向到auth蓝图中的企业微信登录页面
    return redirect(url_for('auth.wechat_corp_login'))

# 登出功能
@app.route('/logout')
def logout():
    # 移除会话中的用户名和登录方式
    session.pop('username', None)
    session.pop('login_type', None)
    return redirect(url_for('auth.login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')