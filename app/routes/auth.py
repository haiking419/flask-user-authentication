from flask import Blueprint, render_template_string, request, redirect, url_for, session, jsonify, Response
import hashlib
import time
import requests
import logging
from datetime import datetime
from app.models import get_users, save_users, get_verifications, save_verifications, get_wechat_sessions, save_wechat_sessions, LoginLog, db
from app.utils import generate_verification_code, generate_wechat_state, send_email, verify_code, generate_captcha
from app import WECHAT_CORP_ID, WECHAT_AGENT_ID, WECHAT_APP_SECRET, WECHAT_REDIRECT_URI

# 配置日志记录器
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('auth')

# 创建蓝图
bp = Blueprint('auth', __name__)

@bp.route('/')
def index():
    """首页"""
    if 'username' in session:
        return f"欢迎，{session['username']}！<a href='/logout'>退出登录</a>"
    return redirect(url_for('auth.login'))

@bp.route('/captcha')
def captcha():
    """生成图形验证码"""
    # 生成验证码
    code, img_io = generate_captcha()
    
    # 保存验证码到session
    session['captcha'] = code.upper()  # 保存大写形式
    session['captcha_timestamp'] = time.time()
    
    # 返回图片响应
    return Response(img_io.getvalue(), mimetype='image/png')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    # 如果用户已登录，重定向到首页
    if 'username' in session:
        logger.info(f"用户 {session['username']} 尝试再次登录，已重定向到首页")
        return redirect(url_for('auth.index'))
    
    error_message = None
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # 注意：不要记录密码
        captcha_input = request.form.get('captcha', '').upper()
        
        logger.info(f"登录尝试 - 用户名: {username}, IP: {request.remote_addr}")
        
        # 验证验证码
        if 'captcha' not in session or captcha_input != session.get('captcha', ''):
            error_message = '验证码错误'
            logger.warning(f"登录失败 - 验证码错误: {username}, IP: {request.remote_addr}")
            
            # 保存登录失败日志到数据库
            try:
                login_log = LoginLog(
                    username=username,
                    ip_address=request.remote_addr,
                    login_type='default',
                    success=False,
                    error_message='验证码错误'
                )
                db.session.add(login_log)
                db.session.commit()
            except Exception as e:
                logger.error(f"保存登录日志失败: {e}")
                try:
                    db.session.rollback()
                except:
                    pass
            # 清除会话中的验证码
            session.pop('captcha', None)
        else:
            # 清除会话中的验证码（无论登录成功与否）
            session.pop('captcha', None)
            
            # 获取用户数据
            users = get_users()
            
            # 验证用户凭据
            if isinstance(users, dict) and username in users:
                user = users[username]
                # 检查密码是否正确
                if user.get('password') == hashlib.sha256(password.encode()).hexdigest():
                    session['username'] = username
                    session['login_type'] = 'default'
                    logger.info(f"登录成功 - 用户名: {username}, IP: {request.remote_addr}")
                    
                    # 保存登录成功日志到数据库
                    try:
                        login_log = LoginLog(
                            username=username,
                            ip_address=request.remote_addr,
                            login_type='default',
                            success=True
                        )
                        db.session.add(login_log)
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"保存登录日志失败: {e}")
                        try:
                            db.session.rollback()
                        except:
                            pass
                    
                    return redirect('/')
                else:
                    logger.warning(f"登录失败 - 密码错误: {username}, IP: {request.remote_addr}")
                    
                    # 保存登录失败日志到数据库
                    try:
                        login_log = LoginLog(
                            username=username,
                            ip_address=request.remote_addr,
                            login_type='default',
                            success=False,
                            error_message='密码错误'
                        )
                        db.session.add(login_log)
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"保存登录日志失败: {e}")
                        try:
                            db.session.rollback()
                        except:
                            pass
            else:
                logger.warning(f"登录失败 - 用户不存在: {username}, IP: {request.remote_addr}")
                
                # 保存登录失败日志到数据库
                try:
                    login_log = LoginLog(
                        username=username,
                        ip_address=request.remote_addr,
                        login_type='default',
                        success=False,
                        error_message='用户不存在'
                    )
                    db.session.add(login_log)
                    db.session.commit()
                except Exception as e:
                    logger.error(f"保存登录日志失败: {e}")
                    try:
                        db.session.rollback()
                    except:
                        pass
            
            error_message = '用户名或密码错误'
    
    # 生成微信登录二维码URL
    state = generate_wechat_state()
    wechat_qrcode_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?corpid={WECHAT_CORP_ID}&agentid={WECHAT_AGENT_ID}&redirect_uri={WECHAT_REDIRECT_URI}&state={state}"
    
    # 保存微信状态码
    wechat_sessions = get_wechat_sessions()
    wechat_sessions[state] = {'timestamp': time.time()}
    save_wechat_sessions(wechat_sessions)
    
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
                    <i class="fa fa-user-circle text-2xl"></i>
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
                
                <div>
                    <label for="captcha" class="block text-sm font-medium text-gray-700 mb-1">图形验证码</label>
                    <div class="flex space-x-2">
                        <div class="relative flex-grow">
                            <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                                <i class="fa fa-shield"></i>
                            </div>
                            <input 
                                type="text" 
                                id="captcha" 
                                name="captcha" 
                                required
                                class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                                placeholder="请输入验证码"
                                maxlength="4"
                            >
                        </div>
                        <img 
                            src="{{ url_for('auth.captcha') }}" 
                            alt="验证码" 
                            class="w-32 h-12 border border-gray-300 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
                            onclick="this.src = '{{ url_for('auth.captcha') }}?' + Math.random()"
                            title="点击刷新验证码"
                        >
                    </div>
                </div>
                
                <button 
                    type="submit" 
                    class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                >
                    <i class="fa fa-sign-in mr-2"></i> 登录
                </button>
            </form>
            
            <div class="mt-6">
                <div class="relative flex items-center justify-center">
                    <div class="absolute inset-0 flex items-center">
                        <div class="w-full border-t border-gray-300"></div>
                    </div>
                    <div class="relative bg-white px-4 text-sm text-gray-500">
                        其他登录方式
                    </div>
                </div>
                
                <div class="mt-6">
                    <a href="{{ wechat_qrcode_url }}" class="w-full inline-flex justify-center items-center space-x-2 py-3 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 btn-hover">
                        <i class="fa fa-building text-blue-600 text-xl"></i>
                        <span>企业微信登录</span>
                    </a>
                </div>
            </div>
            
            <div class="mt-6 text-center">
                <p class="text-gray-600">
                    还没有账号？ <a href="{{ url_for('auth.register') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即注册</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
    ''', error_message=error_message, wechat_qrcode_url=wechat_qrcode_url)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    # 如果用户已登录，重定向到首页
    if 'username' in session:
        logger.info(f"用户 {session['username']} 尝试访问注册页面，已重定向到首页")
        return redirect(url_for('auth.index'))
    
    error_message = None
    username = ''
    email = ''
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        verification_code = request.form['verification_code']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 获取用户数据
        users = get_users()
        
        # 检查用户名是否已存在
        if username in users:
            error_message = '用户名已存在'
            return render_template_string(register_template, error_message=error_message, username=username, email=email)
        
        # 验证邮箱验证码
        if not verify_code(email, verification_code):
            error_message = '验证码无效或已过期，请重新获取验证码'
            return render_template_string(register_template, error_message=error_message, username=username, email=email)
        
        # 验证密码
        if password != confirm_password:
            error_message = '两次输入的密码不一致'
            return render_template_string(register_template, error_message=error_message, username=username, email=email)
        
        # 注册成功，添加用户到数据库
        users[username] = {
            'password': hashlib.sha256(password.encode()).hexdigest(),
            'email': email,
            'created_at': time.time(),
            'login_type': 'default'
        }
        save_users(users)
        
        # 自动登录
        session['username'] = username
        session['login_type'] = 'default'
        
        logger.info(f"用户注册成功 - 用户名: {username}, 邮箱: {email}, IP: {request.remote_addr}")
        
        return redirect(url_for('auth.index'))
    
    # 渲染注册页面
    return render_template_string(register_template, error_message=error_message, username=username, email=email)

@bp.route('/send_verification', methods=['POST'])
def send_verification():
    """发送验证码"""
    email = request.form.get('email')
    
    logger.info(f"[验证码发送] 请求发送验证码到邮箱: {email}, IP: {request.remote_addr}")
    
    # 验证邮箱不为空
    if not email:
        logger.warning(f"[验证码发送] 错误: 邮箱地址为空, IP: {request.remote_addr}")
        return jsonify({'success': False, 'message': '邮箱地址不能为空'})
    
    # 验证邮箱格式
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        logger.warning(f"[验证码发送] 错误: 邮箱格式不正确: {email}, IP: {request.remote_addr}")
        return jsonify({'success': False, 'message': '邮箱格式不正确'})
    
    # 检查邮箱是否已被注册
    users = get_users()
    for user in users.values():
        if user.get('email') == email:
            logger.warning(f"[验证码发送] 错误: 邮箱已被注册: {email}, IP: {request.remote_addr}")
            return jsonify({'success': False, 'message': '该邮箱已被注册'})
    
    # 生成验证码
    code = generate_verification_code()
    # 使用UTC时间戳，避免时区差异问题
    from datetime import datetime, timezone
    current_utc = datetime.now(timezone.utc)
    current_timestamp = current_utc.timestamp()
    
    logger.info(f"[验证码发送] 生成验证码: {code} UTC时间: {current_utc}, 时间戳: {current_timestamp}")
    
    # 保存验证码（有效期10分钟）
    verifications = get_verifications()
    
    # 检查是否已有该邮箱的验证码，如果有则更新
    if email in verifications:
        logger.info(f"[验证码发送] 更新已有验证码: 邮箱 {email}")
    
    # 使用UTC时间戳，确保时区一致性
    verifications[email] = {
        'code': code,
        'timestamp': current_timestamp
    }
    
    # 清除数据库中可能存在的旧记录，确保使用当前生成的验证码
    from app.models.db import db, Verification
    try:
        # 直接在数据库中删除该邮箱的旧验证码记录
        old_verifications = Verification.query.filter_by(email=email).all()
        for v in old_verifications:
            db.session.delete(v)
        db.session.commit()
        logger.info(f"[验证码发送] 已清理数据库中该邮箱的旧验证码记录")
    except Exception as e:
        logger.error(f"[验证码发送] 清理数据库旧记录时出错: {e}")
    
    # 确认保存
    save_result = save_verifications(verifications)
    logger.info(f"[验证码发送] 验证码保存状态: {'成功' if save_result is None else '失败'}")
    
    # 再次读取以确认保存成功
    verifications_after_save = get_verifications()
    if email in verifications_after_save:
        logger.info(f"[验证码发送] 验证码保存确认: 邮箱 {email} 的验证码已正确保存")
        stored_code = verifications_after_save[email]['code']
        stored_timestamp = verifications_after_save[email]['timestamp']
        logger.info(f"[验证码发送] 存储的验证码: {stored_code}, 时间戳: {stored_timestamp}")
    else:
        logger.warning(f"[验证码发送] 警告: 验证码保存后无法在存储中找到: 邮箱 {email}")
    
    # 发送验证码邮件
    subject = 'Hello World 注册验证码'
    content = f'''<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #3b82f6;">您的注册验证码</h2>
        <p>尊敬的用户：</p>
        <p>感谢您注册 Hello World 账号。您的验证码是：</p>
        <div style="font-size: 24px; font-weight: bold; color: #10b981; margin: 20px 0;">
            {code}
        </div>
        <p>验证码有效期为10分钟，请尽快完成注册。</p>
        <p>如非您本人操作，请忽略此邮件。</p>
        <p>祝好，<br>Hello World 团队</p>
    </div>'''
    
    # 记录验证码到日志，方便测试（仅在开发环境）
    logger.info(f"[测试信息] 邮箱 {email} 的验证码是: {code} (有效期10分钟)")
    
    # 发送邮件
    if send_email(email, subject, content):
        return jsonify({'success': True, 'message': '验证码已发送'})
    else:
        return jsonify({'success': False, 'message': '发送验证码失败，请稍后重试'})

# 企业微信登录回调函数在文件后面定义

@bp.route('/wechat_corp_login')
def wechat_corp_login():
    """企业微信登录页面"""
    state = generate_wechat_state()
    
    # 生成企业微信扫码登录URL
    wechat_qrcode_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?corpid={WECHAT_CORP_ID}&agentid={WECHAT_AGENT_ID}&redirect_uri={WECHAT_REDIRECT_URI}&state={state}"
    
    # 保存微信状态码到数据库
    wechat_sessions = get_wechat_sessions()
    wechat_sessions[state] = {'timestamp': time.time()}
    save_wechat_sessions(wechat_sessions)
    
    return render_template_string('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>企业微信登录 - Hello World</title>
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
        <div class="bg-white rounded-2xl p-8 card-shadow text-center">
            <div class="inline-flex items-center justify-center w-20 h-20 bg-wechat_corp/10 text-wechat_corp rounded-full mb-6">
                <i class="fa fa-building text-4xl"></i>
            </div>
            <h1 class="text-2xl font-bold text-gray-800 mb-4">企业微信登录</h1>
            <p class="text-gray-600 mb-8">请使用企业微信扫码登录</p>
            
            <div class="flex justify-center mb-8">
                <div class="w-64 h-64 border-2 border-gray-200 rounded-lg bg-white overflow-hidden">
                    <img src="{{ qrcode_url }}" alt="企业微信登录二维码" class="w-full h-full object-contain">
                </div>
            </div>
            
            <div class="text-sm text-gray-500">
                <p>请在 60 秒内完成扫码</p>
                <div id="countdown" class="text-primary font-medium mt-2">60</div>
            </div>
            
            <!-- 测试账号提示 -->
            <div class="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                <p class="text-blue-700 text-sm">
                    <i class="fa fa-lightbulb-o mr-2"></i>
                    测试功能：点击下方按钮模拟企业微信扫码登录成功
                </p>
                <form action="{{ url_for('auth.wechat_callback') }}" method="get" class="mt-4">
                    <input type="hidden" name="code" value="test_corp_code_{{ state }}">
                    <input type="hidden" name="state" value="{{ state }}">
                    <button type="submit" class="bg-blue-100 hover:bg-blue-200 text-blue-700 py-2 px-4 rounded-lg text-sm transition-colors">
                        模拟登录成功
                    </button>
                </form>
            </div>
        </div>
    </div>
    
    <script>
        let countdown = 60;
        const countdownElement = document.getElementById('countdown');
        
        const timer = setInterval(() => {
            countdown--;
            countdownElement.textContent = countdown;
            
            if (countdown <= 0) {
                clearInterval(timer);
                countdownElement.textContent = '已过期';
                countdownElement.classList.remove('text-primary');
                countdownElement.classList.add('text-red-500');
                // 可以在这里添加刷新二维码的逻辑
            }
        }, 1000);
    </script>
</body>
</html>
    ''', state=state, qrcode_url=wechat_qrcode_url)

@bp.route('/wechat_callback')
def wechat_callback():
    """企业微信登录回调处理"""
    state = request.args.get('state')
    code = request.args.get('code')
    
    logger.info(f"企业微信登录回调 - state: {state}, code存在: {bool(code)}, IP: {request.remote_addr}")
    
    # 测试环境中直接模拟成功场景，返回重定向
    # 将用户信息存储到会话中
    session['username'] = 'wx_corp_test_user'
    session['login_type'] = 'wechat_corp'  # 记录登录方式
    session.permanent = True  # 设置会话持久化
    
    logger.info(f"企业微信登录成功 - 用户名: wx_corp_test_user, IP: {request.remote_addr}")
    
    # 跳转到首页
    return redirect('/')

@bp.route('/logout')
def logout():
    """退出登录"""
    username = session.pop('username', '未知用户')
    login_type = session.pop('login_type', '未知类型')
    
    logger.info(f"用户退出登录 - 用户名: {username}, 登录类型: {login_type}, IP: {request.remote_addr}")
    
    return redirect(url_for('auth.login'))

# 注册页面模板
register_template = '''
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
                <div class="inline-flex items-center justify-center w-16 h-16 bg-secondary/10 text-secondary rounded-full mb-4">
                    <i class="fa fa-user-plus text-2xl"></i>
                </div>
                <h1 class="text-3xl font-bold text-gray-800">创建账号</h1>
                <p class="text-gray-500 mt-2">加入我们的平台</p>
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
                    已有账号？ <a href="{{ url_for('auth.login') }}" class="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
                </p>
            </div>
        </div>
    </div>
    
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
            const formData = new FormData();
            formData.append('email', email);
            
            fetch('/send_verification', {
                method: 'POST',
                body: formData
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
</body>
</html>
'''