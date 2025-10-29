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

app = Flask(__name__)

# 从环境变量获取配置，增强安全性
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-for-development')

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

# 从配置中导入常量
from app import app
from app.models.db import User, db

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

# 已从app.models导入save_wechat_sessions，不再需要本地实现

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

# 登录页面
@app.route('/', methods=['GET', 'POST'])
def login():
    # 检查用户是否已经登录
    if 'username' in session:
        return redirect(url_for('hello'))
    
    # 处理登录表单提交
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form
        
        # 获取用户数据
        users = get_users()
        
        # 验证用户凭据
        if username in users:
            # 验证密码 - 支持正常密码和微信登录生成的密码
            if users[username]['password'] == hashlib.sha256(password.encode()).hexdigest() or \
               (users[username]['login_type'] in ['wechat', 'wechat_corp'] and users[username]['password'] == password):
                session['username'] = username
                session['login_type'] = users[username]['login_type']
                
                # 如果勾选了记住我，可以设置会话的持久化
                if remember:
                    # 设置会话永不过期（在实际应用中应设置合理的过期时间）
                    app.permanent_session_lifetime = timedelta(days=30)
                    session.permanent = True
                    
                return redirect(url_for('hello'))
        else:
            return render_template_string('''
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>登录 - Hello World</title>
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
                                        wechat: '#07C160',
                                        wechat_corp: '#1296DB',
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
                            .input-focus {
                                @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                            }
                            .btn-hover {
                                @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                            }
                        }
                    </style>
                </head>
                <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
                    <div class="w-full max-w-md">
                        <div class="bg-white rounded-2xl p-8 card-shadow">
                            <div class="text-center mb-8">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                                    <i class="fa fa-lock text-2xl"></i>
                                </div>
                                <h1 class="text-3xl font-bold text-gray-800">欢迎回来</h1>
                                <p class="text-gray-500 mt-2">请登录您的账号</p>
                            </div>
                            
                            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                                <p class="text-red-600 text-sm flex items-center">
                                    <i class="fa fa-exclamation-circle mr-2"></i>
                                    用户名或密码错误，请重试
                                </p>
                            </div>
                            
                            <form method="post" class="space-y-4">
                                <div>
                                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                                    <div class="relative">
                                        <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
                                            <i class="fa fa-user"></i>
                                        </span>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required 
                                            class="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white focus:outline-none input-focus transition-all"
                                            placeholder="请输入用户名"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
                                            <i class="fa fa-lock"></i>
                                        </span>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required 
                                            class="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white focus:outline-none input-focus transition-all"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center">
                                        <input 
                                            type="checkbox" 
                                            id="remember" 
                                            name="remember" 
                                            class="h-4 w-4 text-primary border-gray-300 rounded focus:ring-primary"
                                        >
                                        <label for="remember" class="ml-2 block text-sm text-gray-700">
                                            记住我
                                        </label>
                                    </div>
                                    <a href="#" class="text-sm font-medium text-primary hover:text-primary/80 transition-colors">
                                        忘记密码?
                                    </a>
                                </div>
                                
                                <div>
                                    <button 
                                        type="submit" 
                                        class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover"
                                    >
                                        登录
                                    </button>
                                </div>
                            </form>
                            
                            <!-- 分隔线 -->
                            <div class="relative my-6">
                                <div class="absolute inset-0 flex items-center">
                                    <div class="w-full border-t border-gray-300"></div>
                                </div>
                                <div class="relative flex justify-center text-sm">
                                    <span class="px-2 bg-white text-gray-500">
                                        或使用以下方式登录
                                    </span>
                                </div>
                            </div>
                            
                            <!-- 微信登录按钮 -->
                            <div class="space-y-3">
                                <a href="{{ url_for('wechat_login') }}" class="flex items-center justify-center w-full bg-wechat hover:bg-wechat/90 text-white font-medium py-3 px-4 rounded-lg btn-hover">
                                    <i class="fa fa-weixin text-xl mr-2"></i>
                                    使用个人微信登录
                                </a>
                                
                                <a href="{{ url_for('wechat_corp_login') }}" class="flex items-center justify-center w-full bg-wechat_corp hover:bg-wechat_corp/90 text-white font-medium py-3 px-4 rounded-lg btn-hover">
                            <i class="fa fa-building text-xl mr-2"></i>
                            使用企业微信登录
                        </a>
                            </div>
                            
                            <!-- 注册链接 -->
                            <div class="mt-6 text-center">
                                <p class="text-gray-600 text-sm">
                                    还没有账号? 
                                    <a href="{{ url_for('register') }}" class="font-medium text-primary hover:text-primary/80 transition-colors">
                                        立即注册
                                    </a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
            ''')
    
    # 渲染登录页面
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>登录 - Hello World</title>
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
                                wechat: '#07C160',
                                wechat_corp: '#1296DB',
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
                    .input-focus {
                        @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                    }
                    .btn-hover {
                        @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                    }
                }
            </style>
        </head>
        <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
            <div class="w-full max-w-md">
                <div class="bg-white rounded-2xl p-8 card-shadow">
                    <div class="text-center mb-8">
                        <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                            <i class="fa fa-lock text-2xl"></i>
                        </div>
                        <h1 class="text-3xl font-bold text-gray-800">欢迎回来</h1>
                        <p class="text-gray-500 mt-2">请登录您的账号</p>
                    </div>
                    
                    <form method="post" class="space-y-4">
                                <div>
                                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                                    <div class="relative">
                                        <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
                                            <i class="fa fa-user"></i>
                                        </span>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required 
                                            class="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white focus:outline-none input-focus transition-all"
                                            placeholder="请输入用户名"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <span class="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
                                            <i class="fa fa-lock"></i>
                                        </span>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required 
                                            class="w-full pl-10 pr-4 py-3 rounded-lg border border-gray-300 text-gray-700 bg-white focus:outline-none input-focus transition-all"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <div class="flex items-center justify-between">
                                    <div class="flex items-center">
                                        <input 
                                            type="checkbox" 
                                            id="remember" 
                                            name="remember" 
                                            class="h-4 w-4 text-primary border-gray-300 rounded focus:ring-primary"
                                        >
                                        <label for="remember" class="ml-2 block text-sm text-gray-700">
                                            记住我
                                        </label>
                                    </div>
                                    <a href="#" class="text-sm font-medium text-primary hover:text-primary/80 transition-colors">
                                        忘记密码?
                                    </a>
                                </div>
                                
                                <div>
                                    <button 
                                        type="submit" 
                                        class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover"
                                    >
                                        登录
                                    </button>
                                </div>
                            </form>
                            
                            <!-- 分隔线 -->
                            <div class="relative my-6">
                                <div class="absolute inset-0 flex items-center">
                                    <div class="w-full border-t border-gray-300"></div>
                                </div>
                                <div class="relative flex justify-center text-sm">
                                    <span class="px-2 bg-white text-gray-500">
                                        或使用以下方式登录
                                    </span>
                                </div>
                            </div>
                            
                            <!-- 微信登录按钮 -->
                            <div class="space-y-3">
                                <a href="{{ url_for('wechat_login') }}" class="flex items-center justify-center w-full bg-wechat hover:bg-wechat/90 text-white font-medium py-3 px-4 rounded-lg btn-hover">
                                    <i class="fa fa-weixin text-xl mr-2"></i>
                                    使用个人微信登录
                                </a>
                                
                                <a href="{{ url_for('wechat_corp_login') }}" class="flex items-center justify-center w-full bg-wechat_corp hover:bg-wechat_corp/90 text-white font-medium py-3 px-4 rounded-lg btn-hover">
                                    <i class="fa fa-building text-xl mr-2"></i>
                                    使用企业微信登录
                                </a>
                            </div>
                            
                            <!-- 注册链接 -->
                            <div class="mt-6 text-center">
                                <p class="text-gray-600 text-sm">
                                    还没有账号? 
                                    <a href="{{ url_for('register') }}" class="font-medium text-primary hover:text-primary/80 transition-colors">
                                        立即注册
                                    </a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
                                        </div>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入用户名"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-key"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <button 
                                    type="submit" 
                                    class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg transition duration-200 flex items-center justify-center"
                                >
                                    <i class="fa fa-sign-in mr-2"></i> 登录
                                </button>
                            </form>
                            
                            <div class="mt-6 text-center">
                                <p class="text-gray-600">
                                    还没有账号？ <a href="{{ url_for('register') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即注册</a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                </html>
            ''')
    
    # 显示登录表单
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>登录 - Hello World</title>
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
                                wechat: '#07c160',
                                wechat_corp: '#0084ff',
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
                    .input-focus {
                        @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                    }
                    .btn-hover {
                        @apply hover:shadow-lg transform hover:-translate-y-0.5 transition-all duration-200;
                    }
                }
            </style>
        </head>
        <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
            <div class="w-full max-w-md">
                <div class="bg-white rounded-2xl p-8 card-shadow">
                    <div class="text-center mb-8">
                        <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                            <i class="fa fa-lock text-2xl"></i>
                        </div>
                        <h1 class="text-3xl font-bold text-gray-800">欢迎回来</h1>
                        <p class="text-gray-500 mt-2">请登录您的账号</p>
                    </div>
                    
                    {% if error_message %}
                    <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                        <p class="text-red-600 text-sm flex items-center">
                            <i class="fa fa-exclamation-circle mr-2"></i>
                            {{ error_message }}
                        </p>
                    </div>
                    {% endif %}
                    
                    <form method="post" class="space-y-4">
                        <div>
                            <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                            <div class="relative">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                    <i class="fa fa-user"></i>
                                </div>
                                <input 
                                    type="text" 
                                    id="username" 
                                    name="username" 
                                    required
                                    class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                    placeholder="请输入用户名"
                                >
                            </div>
                        </div>
                        
                        <div>
                            <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                            <div class="relative">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                    <i class="fa fa-key"></i>
                                </div>
                                <input 
                                    type="password" 
                                    id="password" 
                                    name="password" 
                                    required
                                    class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                    placeholder="请输入密码"
                                >
                            </div>
                        </div>
                        
                        <div class="flex items-center justify-between">
                            <div class="flex items-center">
                                <input 
                                    type="checkbox" 
                                    id="remember" 
                                    name="remember" 
                                    class="h-4 w-4 text-primary border-gray-300 rounded focus:ring-primary"
                                >
                                <label for="remember" class="ml-2 block text-sm text-gray-700">
                                    记住我
                                </label>
                            </div>
                            <a href="#" class="text-sm font-medium text-primary hover:text-primary/80 transition-colors">
                                忘记密码?
                            </a>
                        </div>
                        
                        <button 
                            type="submit" 
                            class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                        >
                            <i class="fa fa-sign-in mr-2"></i> 登录
                        </button>
                    </form>
                    
                    <!-- 分隔线 -->
                    <div class="relative my-6">
                        <div class="absolute inset-0 flex items-center">
                            <div class="w-full border-t border-gray-300"></div>
                        </div>
                        <div class="relative flex justify-center text-sm">
                            <span class="px-2 bg-white text-gray-500">
                                或使用以下方式登录
                            </span>
                        </div>
                    </div>
                    
                    <!-- 微信登录按钮 -->
                    <div class="space-y-3">
                        <a href="{{ url_for('wechat_login') }}" class="flex items-center justify-center w-full bg-wechat hover:bg-wechat/90 text-white font-medium py-3 px-4 rounded-lg btn-hover">
                            <i class="fa fa-weixin text-xl mr-2"></i>
                            使用个人微信登录
                        </a>
                        
                        <a href="{{ url_for('wechat_corp_login') }}" class="flex items-center justify-center w-full bg-wechat_corp hover:bg-wechat_corp/90 text-white font-medium py-3 px-4 rounded-lg btn-hover">
                            <i class="fa fa-building text-xl mr-2"></i>
                            使用企业微信登录
                        </a>
                    </div>
                    
                    <!-- 注册链接 -->
                    <div class="mt-6 text-center">
                        <p class="text-gray-600 text-sm">
                            还没有账号? 
                            <a href="{{ url_for('register') }}" class="font-medium text-primary hover:text-primary/80 transition-colors">
                                立即注册
                            </a>
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
    ''')

# 用户注册页面
@app.route('/register', methods=['GET', 'POST'])
def register():
    # 检查用户是否已经登录
    if 'username' in session:
        return redirect(url_for('hello'))
    
    # 处理注册表单提交
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        email = request.form['email']
        verification_code = request.form['verification_code']
        
        # 获取用户数据
        users = get_users()
        
        # 验证用户名是否已存在
        if username in users:
            return render_template_string('''
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>注册 - Hello World</title>
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
                            .input-focus {
                                @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                            }
                            .btn-hover {
                                @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                            }
                        }
                    </style>
                </head>
                <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
                    <div class="w-full max-w-md">
                        <div class="bg-white rounded-2xl p-8 card-shadow">
                            <div class="text-center mb-8">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                                    <i class="fa fa-user-plus text-2xl"></i>
                                </div>
                                <h1 class="text-3xl font-bold text-gray-800">创建账号</h1>
                                <p class="text-gray-500 mt-2">加入我们的平台</p>
                            </div>
                            
                            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                                <p class="text-red-600 text-sm flex items-center">
                                    <i class="fa fa-exclamation-circle mr-2"></i>
                                    用户名已存在，请选择其他用户名
                                </p>
                            </div>
                            
                            <form method="post" class="space-y-4">
                                <div>
                                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-user"></i>
                                        </div>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入用户名"
                                            value="{{ username }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="email" class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-envelope"></i>
                                        </div>
                                        <input 
                                            type="email" 
                                            id="email" 
                                            name="email" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入邮箱"
                                            value="{{ email }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="verification_code" class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
                                    <div class="flex space-x-2">
                                        <div class="relative flex-grow">
                                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                                <i class="fa fa-shield"></i>
                                            </div>
                                            <input 
                                                type="text" 
                                                id="verification_code" 
                                                name="verification_code" 
                                                required
                                                class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                                placeholder="请输入验证码"
                                            >
                                        </div>
                                        <button 
                                            type="button" 
                                            id="send-code-btn" 
                                            onclick="sendVerificationCode()"
                                            class="bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover whitespace-nowrap"
                                        >
                                            发送验证码
                                        </button>
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-key"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="confirm_password" class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-check-circle"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="confirm_password" 
                                            name="confirm_password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请再次输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <button 
                                    type="submit" 
                                    class="w-full bg-secondary hover:bg-secondary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                                >
                                    <i class="fa fa-user-plus mr-2"></i> 注册
                                </button>
                            </form>
                            
                            <div class="mt-6 text-center">
                                <p class="text-gray-600">
                                    已有账号？ <a href="{{ url_for('login') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                <script>
                    function sendVerificationCode() {
                        const email = document.getElementById('email').value;
                        if (!email) {
                            alert('请先输入邮箱地址');
                            return;
                        }
                        
                        // 显示倒计时
                        const btn = document.getElementById('send-code-btn');
                        btn.disabled = true;
                        let countdown = 60;
                        btn.textContent = `${countdown}秒后重试`;
                        
                        const timer = setInterval(() => {
                            countdown--;
                            btn.textContent = `${countdown}秒后重试`;
                            if (countdown <= 0) {
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            }
                        }, 1000);
                        
                        // 发送请求获取验证码
                        fetch('/send_verification', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded'
                            },
                            body: 'email=' + encodeURIComponent(email)
                        })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    alert('验证码已发送，请查收邮箱');
                                } else {
                                    alert('发送失败：' + data.message);
                                    clearInterval(timer);
                                    btn.disabled = false;
                                    btn.textContent = '发送验证码';
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                alert('发送失败，请稍后重试');
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            });
                    }
                </script>
                </html>
            ''', username=username, email=email)
        
        # 验证验证码是否有效
        if not verify_code(email, verification_code):
            return render_template_string('''
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>注册 - Hello World</title>
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
                            .input-focus {
                                @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                            }
                            .btn-hover {
                                @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                            }
                        }
                    </style>
                </head>
                <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
                    <div class="w-full max-w-md">
                        <div class="bg-white rounded-2xl p-8 card-shadow">
                            <div class="text-center mb-8">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                                    <i class="fa fa-user-plus text-2xl"></i>
                                </div>
                                <h1 class="text-3xl font-bold text-gray-800">创建账号</h1>
                                <p class="text-gray-500 mt-2">加入我们的平台</p>
                            </div>
                            
                            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                                <p class="text-red-600 text-sm flex items-center">
                                    <i class="fa fa-exclamation-circle mr-2"></i>
                                    验证码错误或已过期，请重新获取验证码
                                </p>
                            </div>
                            
                            <form method="post" class="space-y-4">
                                <div>
                                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-user"></i>
                                        </div>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入用户名"
                                            value="{{ username }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="email" class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-envelope"></i>
                                        </div>
                                        <input 
                                            type="email" 
                                            id="email" 
                                            name="email" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入邮箱"
                                            value="{{ email }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="verification_code" class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
                                    <div class="flex space-x-2">
                                        <div class="relative flex-grow">
                                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                                <i class="fa fa-shield"></i>
                                            </div>
                                            <input 
                                                type="text" 
                                                id="verification_code" 
                                                name="verification_code" 
                                                required
                                                class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                                placeholder="请输入验证码"
                                            >
                                        </div>
                                        <button 
                                            type="button" 
                                            id="send-code-btn" 
                                            onclick="sendVerificationCode()"
                                            class="bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover whitespace-nowrap"
                                        >
                                            发送验证码
                                        </button>
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-key"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="confirm_password" class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-check-circle"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="confirm_password" 
                                            name="confirm_password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请再次输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <button 
                                    type="submit" 
                                    class="w-full bg-secondary hover:bg-secondary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                                >
                                    <i class="fa fa-user-plus mr-2"></i> 注册
                                </button>
                            </form>
                            
                            <div class="mt-6 text-center">
                                <p class="text-gray-600">
                                    已有账号？ <a href="{{ url_for('login') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                <script>
                    function sendVerificationCode() {
                        const email = document.getElementById('email').value;
                        if (!email) {
                            alert('请先输入邮箱地址');
                            return;
                        }
                        
                        // 显示倒计时
                        const btn = document.getElementById('send-code-btn');
                        btn.disabled = true;
                        let countdown = 60;
                        btn.textContent = `${countdown}秒后重试`;
                        
                        const timer = setInterval(() => {
                            countdown--;
                            btn.textContent = `${countdown}秒后重试`;
                            if (countdown <= 0) {
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            }
                        }, 1000);
                        
                        // 发送请求获取验证码
                        fetch('/send_verification', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/x-www-form-urlencoded'
                            },
                            body: 'email=' + encodeURIComponent(email)
                        })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    alert('验证码已发送，请查收邮箱');
                                } else {
                                    alert('发送失败：' + data.message);
                                    clearInterval(timer);
                                    btn.disabled = false;
                                    btn.textContent = '发送验证码';
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                alert('发送失败，请稍后重试');
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            });
                    }
                </script>
                </html>
            ''', username=username, email=email)
        
        # 验证密码是否匹配
        if password != confirm_password:
            return render_template_string('''
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>注册 - Hello World</title>
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
                            .input-focus {
                                @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                            }
                            .btn-hover {
                                @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                            }
                        }
                    </style>
                </head>
                <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
                    <div class="w-full max-w-md">
                        <div class="bg-white rounded-2xl p-8 card-shadow">
                            <div class="text-center mb-8">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                                    <i class="fa fa-user-plus text-2xl"></i>
                                </div>
                                <h1 class="text-3xl font-bold text-gray-800">创建账号</h1>
                                <p class="text-gray-500 mt-2">加入我们的平台</p>
                            </div>
                            
                            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                                <p class="text-red-600 text-sm flex items-center">
                                    <i class="fa fa-exclamation-circle mr-2"></i>
                                    两次输入的密码不一致，请重新输入
                                </p>
                            </div>
                            
                            <form method="post" class="space-y-4">
                                <div>
                                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-user"></i>
                                        </div>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入用户名"
                                            value="{{ username }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="email" class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-envelope"></i>
                                        </div>
                                        <input 
                                            type="email" 
                                            id="email" 
                                            name="email" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入邮箱"
                                            value="{{ email }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="verification_code" class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
                                    <div class="flex space-x-2">
                                        <div class="relative flex-grow">
                                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                                <i class="fa fa-shield"></i>
                                            </div>
                                            <input 
                                                type="text" 
                                                id="verification_code" 
                                                name="verification_code" 
                                                required
                                                class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                                placeholder="请输入验证码"
                                            >
                                        </div>
                                        <button 
                                            type="button" 
                                            id="send-code-btn" 
                                            onclick="sendVerificationCode()"
                                            class="bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover whitespace-nowrap"
                                        >
                                            发送验证码
                                        </button>
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-key"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="confirm_password" class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-check-circle"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="confirm_password" 
                                            name="confirm_password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请再次输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <button 
                                    type="submit" 
                                    class="w-full bg-secondary hover:bg-secondary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                                >
                                    <i class="fa fa-user-plus mr-2"></i> 注册
                                </button>
                            </form>
                            
                            <div class="mt-6 text-center">
                                <p class="text-gray-600">
                                    已有账号？ <a href="{{ url_for('login') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                <script>
                    function sendVerificationCode() {
                        const email = document.getElementById('email').value;
                        if (!email) {
                            alert('请先输入邮箱地址');
                            return;
                        }
                        
                        // 显示倒计时
                        const btn = document.getElementById('send-code-btn');
                        btn.disabled = true;
                        let countdown = 60;
                        btn.textContent = `${countdown}秒后重试`;
                        
                        const timer = setInterval(() => {
                            countdown--;
                            btn.textContent = `${countdown}秒后重试`;
                            if (countdown <= 0) {
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            }
                        }, 1000);
                        
                        // 发送请求获取验证码
                        fetch('/send_verification_code?email=' + encodeURIComponent(email))
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    alert('验证码已发送，请查收邮箱');
                                } else {
                                    alert('发送失败：' + data.message);
                                    clearInterval(timer);
                                    btn.disabled = false;
                                    btn.textContent = '发送验证码';
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                alert('发送失败，请稍后重试');
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            });
                    }
                </script>
                </html>
            ''', username=username, email=email)
        
        # 验证邮箱验证码
        if not verify_code(email, verification_code):
            return render_template_string('''
                <!DOCTYPE html>
                <html lang="zh-CN">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>注册 - Hello World</title>
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
                            .input-focus {
                                @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                            }
                            .btn-hover {
                                @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                            }
                        }
                    </style>
                </head>
                <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
                    <div class="w-full max-w-md">
                        <div class="bg-white rounded-2xl p-8 card-shadow">
                            <div class="text-center mb-8">
                                <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                                    <i class="fa fa-user-plus text-2xl"></i>
                                </div>
                                <h1 class="text-3xl font-bold text-gray-800">创建账号</h1>
                                <p class="text-gray-500 mt-2">加入我们的平台</p>
                            </div>
                            
                            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                                <p class="text-red-600 text-sm flex items-center">
                                    <i class="fa fa-exclamation-circle mr-2"></i>
                                    验证码无效或已过期，请重新获取验证码
                                </p>
                            </div>
                            
                            <form method="post" class="space-y-4">
                                <div>
                                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-user"></i>
                                        </div>
                                        <input 
                                            type="text" 
                                            id="username" 
                                            name="username" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入用户名"
                                            value="{{ username }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="email" class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-envelope"></i>
                                        </div>
                                        <input 
                                            type="email" 
                                            id="email" 
                                            name="email" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入邮箱"
                                            value="{{ email }}"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="verification_code" class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
                                    <div class="flex space-x-2">
                                        <div class="relative flex-grow">
                                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                                <i class="fa fa-shield"></i>
                                            </div>
                                            <input 
                                                type="text" 
                                                id="verification_code" 
                                                name="verification_code" 
                                                required
                                                class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                                placeholder="请输入验证码"
                                            >
                                        </div>
                                        <button 
                                            type="button" 
                                            id="send-code-btn" 
                                            onclick="sendVerificationCode()"
                                            class="bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover whitespace-nowrap"
                                        >
                                            发送验证码
                                        </button>
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-key"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="password" 
                                            name="password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <div>
                                    <label for="confirm_password" class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
                                    <div class="relative">
                                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                            <i class="fa fa-check-circle"></i>
                                        </div>
                                        <input 
                                            type="password" 
                                            id="confirm_password" 
                                            name="confirm_password" 
                                            required
                                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                            placeholder="请再次输入密码"
                                        >
                                    </div>
                                </div>
                                
                                <button 
                                    type="submit" 
                                    class="w-full bg-secondary hover:bg-secondary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                                >
                                    <i class="fa fa-user-plus mr-2"></i> 注册
                                </button>
                            </form>
                            
                            <div class="mt-6 text-center">
                                <p class="text-gray-600">
                                    已有账号？ <a href="{{ url_for('login') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
                                </p>
                            </div>
                        </div>
                    </div>
                </body>
                <script>
                    function sendVerificationCode() {
                        const email = document.getElementById('email').value;
                        if (!email) {
                            alert('请先输入邮箱地址');
                            return;
                        }
                        
                        // 显示倒计时
                        const btn = document.getElementById('send-code-btn');
                        btn.disabled = true;
                        let countdown = 60;
                        btn.textContent = `${countdown}秒后重试`;
                        
                        const timer = setInterval(() => {
                            countdown--;
                            btn.textContent = `${countdown}秒后重试`;
                            if (countdown <= 0) {
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            }
                        }, 1000);
                        
                        // 发送请求获取验证码
                        fetch('/send_verification_code?email=' + encodeURIComponent(email))
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    alert('验证码已发送，请查收邮箱');
                                } else {
                                    alert('发送失败：' + data.message);
                                    clearInterval(timer);
                                    btn.disabled = false;
                                    btn.textContent = '发送验证码';
                                }
                            })
                            .catch(error => {
                                console.error('Error:', error);
                                alert('发送失败，请稍后重试');
                                clearInterval(timer);
                                btn.disabled = false;
                                btn.textContent = '发送验证码';
                            });
                    }
                </script>
                </html>
            ''', username=username, email=email)
        
        # 注册成功，添加用户到数据库
        users[username] = {
            'password': hashlib.sha256(password.encode()).hexdigest(),
            'email': email,
            'created_at': time.time(),
            'login_type': 'default'
        }
        save_users(users)
        
        # 自动登录新注册的用户
        session['username'] = username
        session['login_type'] = 'default'
        return redirect(url_for('hello'))
    
    # 显示注册表单
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>注册 - Hello World</title>
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
                    .input-focus {
                        @apply focus:ring-2 focus:ring-primary/50 focus:border-primary;
                    }
                    .btn-hover {
                        @apply transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98];
                    }
                }
            </style>
        </head>
        <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
            <div class="w-full max-w-md">
                <div class="bg-white rounded-2xl p-8 card-shadow">
                    <div class="text-center mb-8">
                        <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
                            <i class="fa fa-user-plus text-2xl"></i>
                        </div>
                        <h1 class="text-3xl font-bold text-gray-800">创建账号</h1>
                        <p class="text-gray-500 mt-2">加入我们的平台</p>
                    </div>
                    
                    <form method="post" class="space-y-4">
                        <div>
                            <label for="username" class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
                            <div class="relative">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                    <i class="fa fa-user"></i>
                                </div>
                                <input 
                                    type="text" 
                                    id="username" 
                                    name="username" 
                                    required
                                    class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                    placeholder="请输入用户名"
                                >
                            </div>
                        </div>
                        
                        <div>
                            <label for="email" class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
                            <div class="relative">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                    <i class="fa fa-envelope"></i>
                                </div>
                                <input 
                                    type="email" 
                                    id="email" 
                                    name="email" 
                                    required
                                    class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                    placeholder="请输入邮箱"
                                >
                            </div>
                        </div>
                        
                        <div>
                            <label for="verification_code" class="block text-sm font-medium text-gray-700 mb-1">验证码</label>
                            <div class="flex space-x-2">
                                <div class="relative flex-grow">
                                    <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                        <i class="fa fa-shield"></i>
                                    </div>
                                    <input 
                                        type="text" 
                                        id="verification_code" 
                                        name="verification_code" 
                                        required
                                        class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                        placeholder="请输入验证码"
                                    >
                                </div>
                                <button 
                                    type="button" 
                                    id="send-code-btn" 
                                    onclick="sendVerificationCode()"
                                    class="bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover whitespace-nowrap"
                                >
                                    发送验证码
                                </button>
                            </div>
                        </div>
                        
                        <div>
                            <label for="password" class="block text-sm font-medium text-gray-700 mb-1">密码</label>
                            <div class="relative">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                    <i class="fa fa-key"></i>
                                </div>
                                <input 
                                    type="password" 
                                    id="password" 
                                    name="password" 
                                    required
                                    class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                    placeholder="请输入密码"
                                >
                            </div>
                        </div>
                        
                        <div>
                            <label for="confirm_password" class="block text-sm font-medium text-gray-700 mb-1">确认密码</label>
                            <div class="relative">
                                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                    <i class="fa fa-check-circle"></i>
                                </div>
                                <input 
                                    type="password" 
                                    id="confirm_password" 
                                    name="confirm_password" 
                                    required
                                    class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                    placeholder="请再次输入密码"
                                >
                            </div>
                        </div>
                        
                        <button 
                            type="submit" 
                            class="w-full bg-secondary hover:bg-secondary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                        >
                            <i class="fa fa-user-plus mr-2"></i> 注册
                        </button>
                    </form>
                    
                    <div class="mt-6 text-center">
                        <p class="text-gray-600">
                            已有账号？ <a href="{{ url_for('login') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
                        </p>
                    </div>
                </div>
            </div>
        </body>
        <script>
            function sendVerificationCode() {
                const email = document.getElementById('email').value;
                if (!email) {
                    alert('请先输入邮箱地址');
                    return;
                }
                
                // 显示倒计时
                const btn = document.getElementById('send-code-btn');
                btn.disabled = true;
                let countdown = 60;
                btn.textContent = `${countdown}秒后重试`;
                
                const timer = setInterval(() => {
                    countdown--;
                    btn.textContent = `${countdown}秒后重试`;
                    if (countdown <= 0) {
                        clearInterval(timer);
                        btn.disabled = false;
                        btn.textContent = '发送验证码';
                    }
                }, 1000);
                
                // 发送请求获取验证码
                fetch('/send_verification_code?email=' + encodeURIComponent(email))
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('验证码已发送，请查收邮箱');
                        } else {
                            alert('发送失败：' + data.message);
                            clearInterval(timer);
                            btn.disabled = false;
                            btn.textContent = '发送验证码';
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('发送失败，请稍后重试');
                        clearInterval(timer);
                        btn.disabled = false;
                        btn.textContent = '发送验证码';
                    });
            }
        </script>
        </html>
    ''')

# Hello World页面（需要登录才能访问）
@app.route('/hello')
def hello():
    # 检查用户是否已登录
    if 'username' not in session:
        return redirect(url_for('login'))
    
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

# 微信登录路由（个人微信）
@app.route('/wechat_login')
def wechat_login():
    # 生成模拟的微信扫码登录页面
    # 实际应用中应该跳转到微信官方的授权页面
    state = generate_wechat_state()
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>微信扫码登录</title>
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
                                wechat: '#07c160',
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
                }
            </style>
        </head>
        <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
            <div class="w-full max-w-md">
                <div class="bg-white rounded-2xl p-8 card-shadow">
                    <div class="text-center mb-8">
                        <div class="inline-flex items-center justify-center w-16 h-16 bg-wechat/10 text-wechat rounded-full mb-4">
                            <i class="fa fa-weixin text-2xl"></i>
                        </div>
                        <h1 class="text-2xl font-bold text-gray-800">微信扫码登录</h1>
                        <p class="text-gray-500 mt-2">请使用微信扫描下方二维码</p>
                    </div>
                    
                    <!-- 模拟二维码 -->
                    <div class="flex justify-center mb-6">
                        <div class="w-56 h-56 bg-gray-100 flex items-center justify-center border border-gray-200 rounded-lg">
                            <div class="text-6xl text-wechat">
                                <i class="fa fa-weixin"></i>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 模拟扫码倒计时和状态 -->
                    <div class="text-center">
                        <p class="text-gray-600 mb-4">
                            <span class="text-primary font-medium">60</span> 秒后二维码失效
                        </p>
                        <div class="w-full bg-gray-200 rounded-full h-2 mb-6">
                            <div class="bg-primary h-2 rounded-full" style="width: 100%"></div>
                        </div>
                        <p class="text-gray-500 text-sm">
                            <i class="fa fa-info-circle mr-1"></i> 请在微信中点击确认登录
                        </p>
                    </div>
                    
                    <!-- 测试账号提示 -->
                    <div class="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                        <p class="text-blue-700 text-sm">
                            <i class="fa fa-lightbulb-o mr-2"></i>
                            测试功能：点击下方按钮模拟微信扫码登录成功
                        </p>
                        <form action="{{ url_for('wechat_login_callback') }}" method="get" class="mt-4">
                            <input type="hidden" name="code" value="test_code_{{ state }}">
                            <input type="hidden" name="state" value="{{ state }}">
                            <button 
                                type="submit" 
                                class="w-full bg-wechat hover:bg-wechat/90 text-white font-medium py-2 px-4 rounded-lg transition duration-200 flex items-center justify-center"
                            >
                                <i class="fa fa-check-circle mr-2"></i> 模拟微信扫码成功
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            
            <script>
                // 模拟倒计时
                let seconds = 60;
                const countdownElement = document.querySelector('.text-primary');
                const progressBar = document.querySelector('.bg-primary');
                
                const timer = setInterval(() => {
                    seconds--;
                    countdownElement.textContent = seconds;
                    progressBar.style.width = (seconds / 60 * 100) + '%';
                    
                    if (seconds <= 0) {
                        clearInterval(timer);
                        countdownElement.textContent = '已失效';
                        countdownElement.classList.remove('text-primary');
                        countdownElement.classList.add('text-red-500');
                    }
                }, 1000);
            </script>
        </body>
        </html>
    ''', state=state)

# 企业微信登录路由
@app.route('/wechat_corp_login')
def wechat_corp_login():
    # 生成模拟的企业微信扫码登录页面
    state = generate_wechat_state()
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>企业微信扫码登录</title>
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
                                wechat_corp: '#0084ff',
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
                }
            </style>
        </head>
        <body class="bg-gradient-to-br from-blue-50 to-indigo-50 min-h-screen flex items-center justify-center p-4">
            <div class="w-full max-w-md">
                <div class="bg-white rounded-2xl p-8 card-shadow">
                    <div class="text-center mb-8">
                        <div class="inline-flex items-center justify-center w-16 h-16 bg-wechat_corp/10 text-wechat_corp rounded-full mb-4">
                            <i class="fa fa-building-o text-2xl"></i>
                        </div>
                        <h1 class="text-2xl font-bold text-gray-800">企业微信扫码登录</h1>
                        <p class="text-gray-500 mt-2">请使用企业微信扫描下方二维码</p>
                    </div>
                    
                    <!-- 模拟二维码 -->
                    <div class="flex justify-center mb-6">
                        <div class="w-56 h-56 bg-gray-100 flex items-center justify-center border border-gray-200 rounded-lg">
                            <div class="text-6xl text-wechat_corp">
                                <i class="fa fa-building-o"></i>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 模拟扫码倒计时和状态 -->
                    <div class="text-center">
                        <p class="text-gray-600 mb-4">
                            <span class="text-primary font-medium">60</span> 秒后二维码失效
                        </p>
                        <div class="w-full bg-gray-200 rounded-full h-2 mb-6">
                            <div class="bg-primary h-2 rounded-full" style="width: 100%"></div>
                        </div>
                        <p class="text-gray-500 text-sm">
                            <i class="fa fa-info-circle mr-1"></i> 请在企业微信中点击确认登录
                        </p>
                    </div>
                    
                    <!-- 测试账号提示 -->
                    <div class="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                        <p class="text-blue-700 text-sm">
                            <i class="fa fa-lightbulb-o mr-2"></i>
                            测试功能：点击下方按钮模拟企业微信扫码登录成功
                        </p>
                        <form action="{{ url_for('wechat_corp_login_callback') }}" method="get" class="mt-4">
                            <input type="hidden" name="code" value="test_corp_code_{{ state }}">
                            <input type="hidden" name="state" value="{{ state }}">
                            <button 
                                type="submit" 
                                class="w-full bg-wechat_corp hover:bg-wechat_corp/90 text-white font-medium py-2 px-4 rounded-lg transition duration-200 flex items-center justify-center"
                            >
                                <i class="fa fa-check-circle mr-2"></i> 模拟企业微信扫码成功
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            
            <script>
                // 模拟倒计时
                let seconds = 60;
                const countdownElement = document.querySelector('.text-primary');
                const progressBar = document.querySelector('.bg-primary');
                
                const timer = setInterval(() => {
                    seconds--;
                    countdownElement.textContent = seconds;
                    progressBar.style.width = (seconds / 60 * 100) + '%';
                    
                    if (seconds <= 0) {
                        clearInterval(timer);
                        countdownElement.textContent = '已失效';
                        countdownElement.classList.remove('text-primary');
                        countdownElement.classList.add('text-red-500');
                    }
                }, 1000);
            </script>
        </body>
        </html>
    ''', state=state)

# 微信登录回调
@app.route('/wechat_login_callback')
def wechat_login_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    # 实际应用中，这里应该调用微信API获取用户信息
    # 这里我们模拟微信登录成功，自动为用户创建账号并登录
    if code and state:
        # 生成基于code的唯一用户名
        username = f"wx_{code[:10]}"
        
        # 检查用户是否已存在，不存在则创建
        if username not in users:
            users[username] = f"wechat_{code}_password"  # 模拟密码
            save_users(users)
        
        # 登录用户
        session['username'] = username
        session['login_type'] = 'wechat'  # 记录登录方式
        
        # 跳转到首页
        return redirect('/')
    
    # 登录失败，返回登录页面
    return redirect(url_for('login'))

# 企业微信登录回调
@app.route('/wechat_corp_login_callback')
def wechat_corp_login_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    # 实际应用中，这里应该调用企业微信API获取用户信息
    # 这里我们模拟企业微信登录成功，自动为用户创建账号并登录
    if code and state:
        # 生成基于code的唯一用户名
        username = f"wx_corp_{code[:10]}"
        
        # 检查用户是否已存在，不存在则创建
        if username not in users:
            users[username] = f"wechat_corp_{code}_password"  # 模拟密码
            save_users(users)
        
        # 登录用户
        session['username'] = username
        session['login_type'] = 'wechat_corp'  # 记录登录方式
        
        # 跳转到Hello World页面
        return redirect(url_for('hello'))
    
    # 登录失败，返回登录页面
    return redirect(url_for('login'))

# 登出功能
@app.route('/logout')
def logout():
    # 移除会话中的用户名和登录方式
    session.pop('username', None)
    session.pop('login_type', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)