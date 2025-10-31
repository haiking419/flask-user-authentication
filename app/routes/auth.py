from flask import Blueprint, render_template_string, request, redirect, url_for, session, jsonify, Response
import hashlib
import time
import requests
import logging
import re
import json
from urllib.parse import quote
from datetime import datetime, timezone
from app.utils.time_utils import format_datetime_with_timezone, format_datetime_for_frontend
from sqlalchemy.exc import IntegrityError, DatabaseError
from app.models import get_users, save_users, get_verifications, save_verifications, get_wechat_sessions, save_wechat_sessions, User, LoginLog, db, Verification
from app.utils import generate_verification_code, generate_wechat_state, send_email, verify_code, generate_captcha

# 导入配置管理器
from app.utils.config_manager import get_config_manager
config_manager = get_config_manager()

# 企业微信配置（从配置管理器获取）
WECHAT_CORP_ID = config_manager.get('WECHAT_CORP_ID')
WECHAT_AGENT_ID = config_manager.get('WECHAT_AGENT_ID')
WECHAT_APP_SECRET = config_manager.get('WECHAT_APP_SECRET')
WECHAT_REDIRECT_URI = config_manager.get('WECHAT_REDIRECT_URI')

# 应用环境判断
IS_PRODUCTION = config_manager.is_production()

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
        return redirect(url_for('auth.user_center'))
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
        # 记录请求开始时间
        start_time = time.time()
        
        # 提取用户代理信息
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # 简单解析用户代理
        browser = 'Unknown'
        platform = 'Unknown'
        
        # 尝试识别浏览器
        if 'Chrome' in user_agent:
            browser = 'Chrome'
        elif 'Firefox' in user_agent:
            browser = 'Firefox'
        elif 'Safari' in user_agent and 'Chrome' not in user_agent:
            browser = 'Safari'
        elif 'Edge' in user_agent:
            browser = 'Edge'
        elif 'MSIE' in user_agent or 'Trident/' in user_agent:
            browser = 'Internet Explorer'
        
        # 尝试识别平台
        if 'Windows' in user_agent:
            platform = 'Windows'
        elif 'Macintosh' in user_agent:
            platform = 'MacOS'
        elif 'Linux' in user_agent:
            platform = 'Linux'
        elif 'iPhone' in user_agent:
            platform = 'iOS'
        elif 'Android' in user_agent:
            platform = 'Android'
        
        username = request.form['username']
        password = request.form['password']
        captcha_input = request.form.get('captcha', '').upper()
        
        # 开发调试阶段记录详细信息
        if not IS_PRODUCTION:
            logger.info(f"[调试] 登录尝试 - 用户名: {username}, IP: {request.remote_addr}, 浏览器: {browser}, 平台: {platform}, User-Agent: {user_agent}")
        else:
            logger.info(f"登录尝试 - 用户名: {username}, IP: {request.remote_addr}")
        
        # 验证验证码
        if 'captcha' not in session or captcha_input != session.get('captcha', ''):
            error_message = '验证码错误'
            logger.warning(f"登录失败 - 验证码错误: {username}, IP: {request.remote_addr}")
            
            # 保存登录失败日志到数据库
            try:
                response_time = time.time() - start_time
                # 构建请求参数信息（过滤掉敏感字段）
                request_params = {k: v for k, v in request.form.items() if k != 'password'}
                
                # 对于验证码错误，用户可能不存在，所以user_id为None
                login_log = LoginLog(
                    user_id=None,  # 验证码错误时用户未验证，无用户ID
                    username=username,
                    ip_address=request.remote_addr,
                    browser=browser,
                    user_agent=user_agent,
                    platform=platform,
                    login_type='default',
                    success=False,
                    error_message='验证码错误',
                    request_params=str(request_params),
                    response_time=response_time
                )
                
                # 开发调试阶段记录密码哈希
                if not IS_PRODUCTION and password:
                    input_hash = hashlib.sha256(password.encode()).hexdigest()
                    login_log.password_hash_debug = input_hash
                
                db.session.add(login_log)
                db.session.commit()
            except Exception as e:
                # 异常处理
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
            
            try:
                # 计算输入密码的哈希值
                input_hash = hashlib.sha256(password.encode()).hexdigest()
                logger.info(f"输入密码哈希长度: {len(input_hash)}, 前10字符: {input_hash[:10]}")
                
                # 从数据库查询用户（MySQL是唯一数据库）
                user = User.query.filter_by(username=username).first()
                logger.info(f"数据库查询用户: {username}, 结果: {user is not None}")
                
                if user:
                    logger.info(f"用户在数据库中存在，密码哈希长度: {len(user.password)}")
                    # 验证用户凭据
                    if user.password == input_hash:
                        # 认证成功
                        session['username'] = username
                        session['login_type'] = 'default'
                        logger.info(f"登录成功 - 用户名: {username}, IP: {request.remote_addr}")
                        
                        # 保存登录成功日志到数据库
                        try:
                            response_time = time.time() - start_time
                            # 构建请求参数信息（过滤掉敏感字段）
                            request_params = {k: v for k, v in request.form.items() if k != 'password'}
                            
                            # 获取用户唯一ID
                            user_id = user.id if user else None
                            
                            login_log = LoginLog(
                                user_id=user_id,  # 记录用户唯一ID
                                username=username,
                                ip_address=request.remote_addr,
                                browser=browser,
                                user_agent=user_agent,
                                platform=platform,
                                login_type='default',
                                success=True,
                                request_params=str(request_params),
                                response_time=response_time
                            )
                            
                            # 开发调试阶段记录密码哈希
                            if not IS_PRODUCTION:
                                login_log.password_hash_debug = input_hash
                            
                            db.session.add(login_log)
                            db.session.commit()
                        except Exception as e:
                            logger.error(f"保存登录日志失败: {e}")
                            try:
                                db.session.rollback()
                            except:
                                pass
                        
                        return redirect(url_for('auth.user_center'))

                # 处理登录失败情况
                error_type = '密码错误' if user else '用户不存在'
                logger.warning(f"登录失败 - {error_type}: {username}, IP: {request.remote_addr}")
                
                # 保存登录失败日志到数据库
                try:
                    response_time = time.time() - start_time
                    # 构建请求参数信息（过滤掉敏感字段）
                    request_params = {k: v for k, v in request.form.items() if k != 'password'}
                    
                    # 获取用户唯一ID（如果用户存在）
                    user_id = user.id if user else None
                    
                    login_log = LoginLog(
                        user_id=user_id,  # 记录用户唯一ID
                        username=username,
                        ip_address=request.remote_addr,
                        browser=browser,
                        user_agent=user_agent,
                        platform=platform,
                        login_type='default',
                        success=False,
                        error_message=error_type,
                        request_params=str(request_params),
                        response_time=response_time
                    )
                    
                    # 开发调试阶段记录密码哈希
                    if not IS_PRODUCTION:
                        login_log.password_hash_debug = input_hash
                    
                    db.session.add(login_log)
                    db.session.commit()
                except Exception as e:
                    logger.error(f"保存登录日志失败: {e}")
                    try:
                        db.session.rollback()
                    except:
                        pass
                
                error_message = '用户名或密码错误'
            except Exception as e:
                logger.error(f"登录验证过程中发生错误: {e}")
                error_message = '系统错误，请稍后重试'
    
    # 生成微信登录二维码URL
    state = generate_wechat_state(action='login')
    # 编码redirect_uri
    encoded_redirect_uri = quote(WECHAT_REDIRECT_URI)
    # 使用官方更新的格式，将corpid改为appid
    wechat_qrcode_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={WECHAT_CORP_ID}&agentid={WECHAT_AGENT_ID}&redirect_uri={encoded_redirect_uri}&state={state}"
    
    # 保存微信状态码
    wechat_sessions = get_wechat_sessions()
    wechat_sessions[state] = {'timestamp': time.time()}
    save_wechat_sessions(wechat_sessions)
    
    # 渲染登录页面
    # 将格式化函数传递到模板上下文中
    # 将格式化函数传递到模板上下文中
    # 将格式化函数传递到模板上下文中
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
    display_name = ''
    email = ''
    
    if request.method == 'POST':
        username = request.form['username']  # 登录账号
        display_name = request.form.get('display_name', username)  # 系统用户名，默认为登录账号
        email = request.form['email']
        verification_code = request.form['verification_code']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # 获取用户数据
        users = get_users()
        
        # 检查登录账号是否已存在
        if username in users:
            error_message = '登录账号已存在'
            return render_template_string(register_template, error_message=error_message, username=username, display_name=display_name, email=email)
        
        # 验证邮箱验证码
        if not verify_code(email, verification_code):
            error_message = '验证码无效或已过期，请重新获取验证码'
            return render_template_string(register_template, error_message=error_message, username=username, display_name=display_name, email=email)
        
        # 验证密码
        if password != confirm_password:
            error_message = '两次输入的密码不一致'
            return render_template_string(register_template, error_message=error_message, username=username, display_name=display_name, email=email)
        
        # 注册成功，添加用户到数据库
        users[username] = {
            'password': hashlib.sha256(password.encode()).hexdigest(),
            'email': email,
            'display_name': display_name,  # 系统用户名
            'created_at': time.time(),
            'login_type': 'default'
        }
        save_users(users)
        
        # 自动登录
        session['username'] = username
        session['login_type'] = 'default'
        
        logger.info(f"用户注册成功 - 登录账号: {username}, 系统用户名: {display_name}, 邮箱: {email}, IP: {request.remote_addr}")
        
        return redirect(url_for('auth.index'))
    
    # 渲染注册页面
    return render_template_string(register_template, error_message=error_message, username=username, display_name=display_name, email=email)

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
    """企业微信扫码登录"""
    # 获取查询参数
    ip_address = request.remote_addr
    mode = request.args.get('mode', 'production')  # 支持测试模式
    
    # 生成state参数，用于防止CSRF攻击，明确指定action为login
    state = generate_wechat_state(action='login')
    
    # 保存state到数据库，用于后续验证
    try:
        wechat_sessions = get_wechat_sessions()
        wechat_sessions[state] = {
            'timestamp': time.time(),
            'ip_address': ip_address,
            'mode': mode,
            'action': 'login'  # 操作类型：login
        }
        save_wechat_sessions(wechat_sessions)
    except Exception as e:
        logger.error(f"保存企业微信登录state失败: {e}, IP: {ip_address}")
        return "生成登录二维码失败，请稍后重试", 500
    
    logger.info(f"生成企业微信登录二维码 - state: {state}, 模式: {mode}, IP: {ip_address}")
    
    # 测试模式处理
    if mode == 'test':
        # 构造测试环境的模拟扫码URL
        qr_code_url = f"/wechat_callback?state={state}&code=test_corp_code_{int(time.time())}"
        test_info = {
            'state': state,
            'test_mode': True,
            'test_callback_url': qr_code_url,
            'test_hint': '测试模式：点击下方链接模拟扫码成功'
        }
        logger.info(f"测试模式企业微信登录 - 生成测试回调链接: {qr_code_url}, IP: {ip_address}")
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
            <h1 class="text-2xl font-bold text-gray-800 mb-4">企业微信登录（测试模式）</h1>
            <p class="text-gray-600 mb-8">测试环境：点击链接模拟扫码</p>
            
            <div class="flex justify-center mb-8">
                <a href="{{ test_info.test_callback_url }}" class="bg-blue-100 hover:bg-blue-200 text-blue-700 py-3 px-6 rounded-lg transition-colors">
                    {{ test_info.test_hint }}
                </a>
            </div>
            
            <div class="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                <p class="text-blue-700 text-sm">
                    <i class="fa fa-info-circle mr-2"></i>
                    测试状态: {{ test_info.state }}
                </p>
            </div>
        </div>
    </div>
</body>
</html>
    ''', state=state, qrcode_url=qr_code_url, test_info=test_info)
    
    # 生产环境：构造企业微信扫码登录URL
    try:
        # 直接打印到标准输出，确保能看到
        import sys
        print(f"[调试] 企业微信配置参数 - CORP_ID: {WECHAT_CORP_ID}, AGENT_ID: {WECHAT_AGENT_ID}, REDIRECT_URI: {WECHAT_REDIRECT_URI}", file=sys.stderr)
        
        # 对redirect_uri进行完整的URL编码（包括所有特殊字符）
        import urllib.parse
        encoded_redirect_uri = urllib.parse.quote(WECHAT_REDIRECT_URI, safe='')
        print(f"[调试] 编码后的redirect_uri: {encoded_redirect_uri}", file=sys.stderr)
        
        # 验证必要的配置参数
        if not WECHAT_CORP_ID or WECHAT_CORP_ID == 'wx1234567890abcdef':
            logger.warning(f"企业微信CORP_ID未配置或使用默认值 - IP: {ip_address}")
        if not WECHAT_AGENT_ID or WECHAT_AGENT_ID == '1000001':
            logger.warning(f"企业微信AGENT_ID未配置或使用默认值 - IP: {ip_address}")
        if not WECHAT_APP_SECRET or WECHAT_APP_SECRET == 'abcdef1234567890abcdef1234567890':
            logger.warning(f"企业微信APP_SECRET未配置或使用默认值 - IP: {ip_address}")
        if not WECHAT_REDIRECT_URI or WECHAT_REDIRECT_URI == 'http://localhost:5000/wechat_callback':
            logger.warning(f"企业微信REDIRECT_URI未配置或使用默认值 - IP: {ip_address}")
        
        # 确保agentid是字符串类型
        agent_id_str = str(WECHAT_AGENT_ID)
        print(f"[调试] 转换后的agentid: {agent_id_str}", file=sys.stderr)
        
        # 使用官方更新的API格式，将corpid改为appid
        qr_code_url = "https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={}&agentid={}&redirect_uri={}&state={}".format(
            str(WECHAT_CORP_ID), str(WECHAT_AGENT_ID), encoded_redirect_uri, state
        )
        
        print(f"[调试] 完整生成的URL: {qr_code_url}", file=sys.stderr)
        logger.info(f"生产环境企业微信登录二维码生成成功 - state: {state}, URL: {qr_code_url[:100]}..., IP: {ip_address}")
        
        # 渲染登录页面，显示二维码
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
                        warning: '#f59e0b',
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
            
            <!-- 二维码区域 -->
            <div class="flex justify-center mb-8">
                <div class="w-64 h-64 border-2 border-gray-200 rounded-lg bg-white overflow-hidden">
                    <!-- 使用QR码生成服务 -->
                    <img src="https://api.qrserver.com/v1/create-qr-code/?size=256x256&data={{ qrcode_url|urlencode }}" alt="企业微信登录二维码" class="w-full h-full object-contain">
                </div>
            </div>
            <p class="text-sm text-gray-500 mt-2">请使用企业微信扫码登录</p>
            
            <!-- 配置检查提示 -->
            <div class="mb-6 p-3 bg-yellow-50 border border-yellow-100 rounded-lg">
                <p class="text-yellow-700 text-sm">
                    <i class="fa fa-exclamation-circle mr-2"></i>
                    如果扫码时显示"参数错误"，请确认企业微信应用配置已正确设置
                </p>
            </div>
            
            <div class="text-sm text-gray-500">
                <p>请在 60 秒内完成扫码</p>
                <div id="countdown" class="text-primary font-medium mt-2">60</div>
            </div>
            
            <!-- 二维码刷新按钮 -->
            <button id="refresh-btn" class="mt-4 text-sm text-primary hover:text-primary/80 transition-colors">
                <i class="fa fa-refresh mr-1"></i> 刷新二维码
            </button>
        </div>
    </div>
    
    <script>
        let countdown = 60;
        const countdownElement = document.getElementById('countdown');
        const refreshButton = document.getElementById('refresh-btn');
        
        // 倒计时逻辑
        const timer = setInterval(() => {
            countdown--;
            countdownElement.textContent = countdown;
            
            if (countdown <= 0) {
                clearInterval(timer);
                clearInterval(pollingTimer);
                countdownElement.textContent = '已过期';
                countdownElement.classList.remove('text-primary');
                countdownElement.classList.add('text-red-500');
                refreshButton.classList.remove('opacity-50', 'cursor-not-allowed');
                refreshButton.disabled = false;
            }
        }, 1000);
        
        // 轮询检查扫码状态
        const pollingTimer = setInterval(() => {
            fetch(`/check_wechat_scan_status?state={{ state }}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'scanned') {
                        // 用户已扫码，显示提示
                        document.querySelector('.card-shadow').innerHTML = `
                            <div class="inline-flex items-center justify-center w-20 h-20 bg-green-100 text-green-500 rounded-full mb-6">
                                <i class="fa fa-check text-4xl"></i>
                            </div>
                            <h1 class="text-2xl font-bold text-gray-800 mb-4">已扫码，请确认</h1>
                            <p class="text-gray-600 mb-8">请在企业微信中点击确认绑定</p>
                        `;
                    } else if (data.status === 'confirmed') {
                        // 用户已确认，跳转到用户中心
                        clearInterval(pollingTimer);
                        clearInterval(timer);
                        window.location.href = '/user_center';
                    } else if (data.status === 'expired') {
                        // 二维码已过期
                        clearInterval(pollingTimer);
                        clearInterval(timer);
                        countdownElement.textContent = '已过期';
                        countdownElement.classList.remove('text-primary');
                        countdownElement.classList.add('text-red-500');
                        refreshButton.classList.remove('opacity-50', 'cursor-not-allowed');
                        refreshButton.disabled = false;
                    }
                })
                .catch(error => {
                    console.error('检查扫码状态失败:', error);
                });
        }, 2000); // 每2秒检查一次
        
        // 刷新二维码功能
        refreshButton.addEventListener('click', () => {
            window.location.reload();
        });
        
        // 页面卸载时清理定时器
        window.addEventListener('beforeunload', () => {
            clearInterval(timer);
            clearInterval(pollingTimer);
        });
    </script>
</body>
</html>
    ''', state=state, qrcode_url=qr_code_url)
    except Exception as e:
        logger.error(f"生成企业微信登录URL失败: {e}, IP: {ip_address}")
        return "生成登录二维码失败，请稍后重试", 500

@bp.route('/bind_wechat_corp')
def bind_wechat_corp():
    """企业微信绑定入口函数"""
    # 检查用户是否已登录
    if 'username' not in session:
        logger.warning(f"未登录用户尝试访问企业微信绑定 - IP: {request.remote_addr}")
        return redirect(url_for('auth.login'))
    
    # 获取基本信息
    ip_address = request.remote_addr
    current_username = session['username']
    mode = request.args.get('mode', 'production')
    
    logger.info(f"用户请求企业微信绑定 - 用户名: {current_username}, 模式: {mode}, IP: {ip_address}")
    
    # 生成安全的state参数，明确指定action为bind
    try:
        state = generate_wechat_state(action='bind')
    except Exception as e:
        logger.error(f"生成企业微信state失败: {e}, 用户名: {current_username}")
        session['error_message'] = '生成绑定请求失败，请稍后重试'
        return redirect(url_for('auth.user_center'))
    
    # 保存state和相关信息到会话存储
    try:
        wechat_sessions = get_wechat_sessions()
        # 规范化会话数据结构，确保与回调函数兼容
        wechat_sessions[state] = {
            'timestamp': time.time(),
            'ip_address': ip_address,
            'mode': mode,
            'action': 'bind',  # 明确标识为绑定操作
            'username': current_username,
            'scan_status': 'pending',
            'callback_count': 0  # 记录回调次数，防止重复处理
        }
        save_wechat_sessions(wechat_sessions)
        logger.info(f"企业微信绑定会话保存成功 - state: {state}, 用户名: {current_username}")
    except Exception as e:
        logger.error(f"保存企业微信绑定会话失败: {e}, 用户名: {current_username}")
        session['error_message'] = '绑定请求创建失败，请稍后重试'
        return redirect(url_for('auth.user_center'))
    
    # 根据模式处理
    if mode == 'test':
        return handle_wechat_bind_test_mode(state, current_username, ip_address)
    else:
        return handle_wechat_bind_production_mode(state, current_username, ip_address)

def handle_wechat_bind_test_mode(state, username, ip_address):
    """处理测试模式下的企业微信绑定"""
    try:
        # 构造测试环境的模拟扫码URL
        qr_code_url = url_for('auth.wechat_callback', _external=True, state=state, code=f'test_corp_code_{int(time.time())}')
        test_info = {
            'state': state,
            'test_mode': True,
            'test_callback_url': qr_code_url,
            'test_hint': '测试模式：点击下方链接模拟扫码成功'
        }
        logger.info(f"测试模式企业微信绑定 - 生成测试回调链接, 用户名: {username}, IP: {ip_address}")
        
        # 返回测试模式页面
        return render_template_string('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绑定企业微信 - Hello World</title>
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
            <h1 class="text-2xl font-bold text-gray-800 mb-4">绑定企业微信（测试模式）</h1>
            <p class="text-gray-600 mb-8">测试环境：点击链接模拟扫码</p>
            
            <div class="flex justify-center mb-8">
                <a href="{{ qrcode_url }}" class="bg-blue-100 hover:bg-blue-200 text-blue-700 py-3 px-6 rounded-lg transition-colors">
                    {{ test_info.test_hint }}
                </a>
            </div>
            
            <div class="mt-6 p-4 bg-blue-50 border border-blue-100 rounded-lg">
                <p class="text-blue-700 text-sm">
                    <i class="fa fa-info-circle mr-2"></i>
                    测试状态: {{ test_info.state }}
                </p>
            </div>
            
            <div class="mt-4 p-4 bg-amber-50 border border-amber-100 rounded-lg">
                <p class="text-amber-700 text-sm">
                    <i class="fa fa-clock-o mr-2"></i>
                    二维码有效期: 5分钟
                </p>
            </div>
        </div>
    </div>
</body>
</html>
    ''', qrcode_url=qr_code_url, test_info=test_info)
    except Exception as e:
        logger.error(f"生成企业微信测试绑定页面失败: {e}, 用户名: {username}")
        session['error_message'] = '生成绑定页面失败，请稍后重试'
        return redirect(url_for('auth.user_center'))

def handle_wechat_bind_production_mode(state, username, ip_address):
    """处理生产模式下的企业微信绑定"""
    try:
        # 验证必要的配置参数
        validate_wechat_configs()
        
        # 对redirect_uri进行完整的URL编码
        import urllib.parse
        encoded_redirect_uri = urllib.parse.quote(WECHAT_REDIRECT_URI, safe='')
        
        # 使用官方更新的API格式，将corpid改为appid
        qr_connect_url = "https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={}&agentid={}&redirect_uri={}&state={}".format(
            str(WECHAT_CORP_ID), str(WECHAT_AGENT_ID), encoded_redirect_uri, state
        )
        
        logger.info(f"生产环境企业微信绑定URL生成成功 - 用户名: {username}, URL长度: {len(qr_connect_url)}, IP: {ip_address}")
        
        # 重定向到企业微信官方页面
        return redirect(qr_connect_url)
    except Exception as e:
        logger.error(f"生成企业微信绑定URL失败: {e}, 用户名: {username}")
        session['error_message'] = '生成绑定链接失败，请联系管理员'
        return redirect(url_for('auth.user_center'))

def validate_wechat_configs():
    """验证企业微信配置参数"""
    config_checks = [
        (WECHAT_CORP_ID, 'wx1234567890abcdef', 'CORP_ID'),
        (WECHAT_AGENT_ID, '1000001', 'AGENT_ID'),
        (WECHAT_APP_SECRET, 'abcdef1234567890abcdef1234567890', 'APP_SECRET'),
        (WECHAT_REDIRECT_URI, 'http://localhost:5000/wechat_callback', 'REDIRECT_URI')
    ]
    
    warnings = []
    for value, default, name in config_checks:
        if not value or value == default:
            warnings.append(f"企业微信{name}未配置或使用默认值")
    
    # 记录所有配置警告
    if warnings:
        for warning in warnings:
            logger.warning(f"{warning} - IP: {request.remote_addr}")
        
        # 配置不完整时仍然允许继续，但记录警告
        return False
    
    return True

@bp.route('/check_wechat_scan_status')
def check_wechat_scan_status():
    """检查企业微信扫码状态"""
    state = request.args.get('state')
    ip_address = request.remote_addr
    
    try:
        # 获取微信会话信息
        wechat_sessions = get_wechat_sessions()
        
        # 检查state是否存在
        if state not in wechat_sessions:
            return jsonify({'status': 'invalid', 'message': '二维码不存在或已失效'}), 404
        
        session_info = wechat_sessions[state]
        
        # 检查扫码状态
        scan_status = session_info.get('scan_status', 'pending')
        
        # 如果已经确认，优先返回confirmed状态，不检查过期
        if scan_status == 'confirmed':
            logger.info(f"检测到已确认状态 - state: {state}, IP: {ip_address}")
            # 不立即清理state，让前端有足够时间收到状态并完成跳转
            # 清理会在前端跳转后自动处理
            return jsonify({'status': scan_status, 'message': '成功'}), 200
        
        # 检查二维码是否过期（延长有效期至5分钟）
        if time.time() - session_info.get('timestamp', 0) > 300:  # 5分钟
            # 从会话中删除过期的state
            try:
                del wechat_sessions[state]
                save_wechat_sessions(wechat_sessions)
            except:
                pass
            return jsonify({'status': 'expired', 'message': '二维码已过期'}), 200
        
        return jsonify({'status': scan_status, 'message': '成功'}), 200
        
    except Exception as e:
        logger.error(f"检查企业微信扫码状态时发生错误: {e}, IP: {ip_address}")
        return jsonify({'status': 'error', 'message': '服务器内部错误'}), 500

@bp.route('/wechat_callback')
def wechat_callback():
    """企业微信扫码回调处理函数（支持登录和绑定两种场景）"""
    # 获取请求参数和基础信息
    state = request.args.get('state')
    code = request.args.get('code')
    ip_address = request.remote_addr
    
    # 提取用户代理信息用于日志记录
    user_agent = request.headers.get('User-Agent', '')
    browser_info = extract_browser_info(user_agent)
    platform_info = extract_platform_info(user_agent)
    
    logger.info(f"企业微信回调请求 - state存在: {bool(state)}, code存在: {bool(code)}, IP: {ip_address}")
    
    # 1. 验证请求参数
    if not validate_callback_params(state, code, ip_address):
        return "无效的请求参数", 400
    
    # 2. 验证state并获取会话信息
    session_info, action = validate_state_and_get_session_info(state, code, ip_address)
    if not session_info:
        return "会话验证失败，请重新扫码", 400
    
    try:
        # 3. 根据环境类型处理
        if is_test_mode(code):
            result = handle_test_mode_callback(state, session_info, action, ip_address)
        else:
            result = handle_production_mode_callback(state, session_info, action, code, ip_address)
        
        # 4. 记录操作日志
        record_wechat_operation_log(
            result['username'], state, action, result['success'], ip_address,
            user_agent, browser_info, platform_info, session_info.get('timestamp')
        )
        
        # 5. 清理资源
        cleanup_callback_resources(state)
        
        # 6. 返回适当的响应
        return handle_callback_response(action, result)
    
    except Exception as e:
        # 异常处理
        logger.error(f"企业微信回调处理异常: {str(e)}, IP: {ip_address}")
        # 记录失败日志
        record_wechat_operation_log(
            "unknown", state, action, False, ip_address,
            user_agent, browser_info, platform_info, None, str(e)
        )
        return "服务器处理异常，请稍后重试", 500

def validate_callback_params(state, code, ip_address):
    """验证回调请求参数"""
    if not state or not code:
        logger.warning(f"企业微信回调参数不完整 - IP: {ip_address}")
        return False
    return True

def extract_browser_info(user_agent):
    """提取浏览器信息"""
    if 'Chrome' in user_agent:
        return 'Chrome'
    elif 'Firefox' in user_agent:
        return 'Firefox'
    elif 'Safari' in user_agent and 'Chrome' not in user_agent:
        return 'Safari'
    elif 'Edge' in user_agent:
        return 'Edge'
    elif 'MSIE' in user_agent or 'Trident/' in user_agent:
        return 'Internet Explorer'
    return 'Unknown'

def extract_platform_info(user_agent):
    """提取平台信息"""
    if 'Windows' in user_agent:
        return 'Windows'
    elif 'Macintosh' in user_agent:
        return 'macOS'
    elif 'Linux' in user_agent:
        return 'Linux'
    elif 'iPhone' in user_agent or 'iPad' in user_agent:
        return 'iOS'
    elif 'Android' in user_agent:
        return 'Android'
    return 'Unknown'

def validate_state_and_get_session_info(state, code, ip_address):
    """验证state并获取会话信息，支持从state字符串中解析action信息"""
    try:
        wechat_sessions = get_wechat_sessions()
        logger.info(f"获取到的微信会话数量: {len(wechat_sessions)}")
        
        # 从state字符串中解析action信息（如果存在）
        parsed_action = None
        if state and '_' in state:
            action_marker = state.split('_')[0]
            if action_marker == 'L':
                parsed_action = 'login'
            elif action_marker == 'B':
                parsed_action = 'bind'
            
        # 检查state是否存在
        if state not in wechat_sessions:
            logger.warning(f"企业微信回调state无效 - state: {state}, IP: {ip_address}")
            # 测试模式下允许跳过state验证
            if code.startswith('test_corp_code_'):
                logger.info(f"测试模式下跳过state验证 - IP: {ip_address}")
                # 创建临时测试会话
                wechat_sessions[state] = {
                    'timestamp': time.time(),
                    'ip_address': ip_address,
                    'mode': 'test',
                    'action': parsed_action or 'login',  # 使用解析的action或默认为登录操作
                    'scan_status': 'pending'
                }
            else:
                return None, None
        
        session_info = wechat_sessions[state]
        
        # 如果session_info中没有action字段，但state中包含action信息，则添加到session_info
        if 'action' not in session_info and parsed_action:
            session_info['action'] = parsed_action
            logger.info(f"从state中解析并补充action信息: {parsed_action}, state: {state}")
        
        # 检查state是否过期（10分钟内有效）
        try:
            session_timestamp = session_info.get('timestamp', 0)
            # 确保时间戳格式正确
            if isinstance(session_timestamp, datetime):
                session_timestamp = session_timestamp.timestamp()
            
            # 转换为浮点数进行比较
            session_timestamp = float(session_timestamp)
            current_time = time.time()
            
            if current_time - session_timestamp > 600:  # 10分钟
                logger.warning(f"企业微信回调state已过期 - state: {state}, IP: {ip_address}")
                # 删除过期的session
                del wechat_sessions[state]
                save_wechat_sessions(wechat_sessions)
                return None, None
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"检查微信会话过期时间错误: {e}, IP: {ip_address}")
            return None, None
        
        # 获取操作类型，不设置默认值，确保准确获取action
        action = session_info.get('action')
        
        # 更新扫码状态为已确认
        try:
            session_info['scan_status'] = 'confirmed'
            save_wechat_sessions(wechat_sessions)
        except Exception as e:
            logger.warning(f"更新扫码状态失败: {e}")
        
        return session_info, action
        
    except Exception as e:
        logger.error(f"验证企业微信state异常: {e}, IP: {ip_address}")
        return None, 'login'

def is_test_mode(code):
    """判断是否为测试模式"""
    return code.startswith('test_corp_code_')

def handle_test_mode_callback(state, session_info, action, ip_address):
    """处理测试模式下的回调"""
    logger.info(f"测试环境企业微信处理 - state: {state}, action: {action}, IP: {ip_address}")
    
    # 检查action是否为None
    if action is None:
        logger.warning(f"测试环境企业微信回调处理 - action为None, state: {state}, IP: {ip_address}")
        return {
            'success': False,
            'username': None,
            'user_info': None
        }
    
    # 生成测试用户ID
    test_userid = f"test_user_{int(time.time()) % 1000}"
    
    result = {
        'success': False,
        'username': None,
        'user_info': None
    }
    
    if action == 'login':
        # 处理登录操作 - 模拟生产环境逻辑，先查找是否有用户绑定了此微信ID
        try:
            # 先尝试通过wechat_corp_userid查找已绑定的用户
            existing_user = User.query.filter_by(wechat_corp_userid=test_userid).first()
            if existing_user:
                # 找到了已绑定的用户
                username = existing_user.username
                logger.info(f"测试环境企业微信登录 - 找到已绑定用户: {username}, 微信ID: {test_userid}")
                
                # 设置会话信息
                session['username'] = username
                session['login_type'] = 'wechat_corp'
                session['user_info'] = {
                    'userid': test_userid,
                    'name': '测试企业微信用户',
                    'avatar': ''
                }
                session.permanent = True
                
                result['success'] = True
                result['username'] = username
                result['user_info'] = session['user_info']
            else:
                # 没有找到已绑定用户，不生成新用户名，返回用户不存在状态
                # 保存临时信息到会话，用于后续确认绑定
                session['wechat_temp_info'] = {
                    'userid': test_userid,
                    'name': '测试企业微信用户',
                    'avatar': ''
                }
                logger.info(f"测试环境企业微信登录 - 未找到已绑定用户，微信ID: {test_userid}")
                
                result['success'] = False
                result['user_not_exist'] = True
                result['wechat_user_info'] = {'name': '测试企业微信用户'}
        except Exception as e:
            logger.error(f"测试环境企业微信登录处理失败: {e}, IP: {ip_address}")
            result['success'] = False
        
    elif action == 'bind':
        # 处理绑定操作
        if 'username' not in session:
            logger.warning(f"绑定操作需要先登录 - IP: {ip_address}")
            return result
        
        current_username = session['username']
        logger.info(f"测试环境企业微信绑定 - 用户名: {current_username}, 微信用户ID: {test_userid}, IP: {ip_address}")
        
        try:
            # 更新数据库中的绑定信息
            user = User.query.filter_by(username=current_username).first()
            if user:
                # 更新所有企业微信相关字段
                user.wechat_corp_userid = test_userid
                user.wechat_corp_name = '测试企业微信用户'
                user.wechat_corp_avatar = ''
                user.wechat_corp_binded_at = datetime.now()  # 使用正确的字段名
                
                # 更新会话中的用户信息
                session['user_info'] = {
                    'userid': test_userid,
                    'name': '测试企业微信用户',
                    'avatar': ''
                }
                
                db.session.commit()
                logger.info(f"测试环境企业微信绑定成功 - 用户名: {current_username}, IP: {ip_address}")
                
                result['success'] = True
                result['username'] = current_username
                result['user_info'] = session['user_info']
        except Exception as e:
            logger.error(f"测试环境企业微信绑定失败: {e}, IP: {ip_address}")
            try:
                db.session.rollback()
            except:
                pass
    
    return result

def handle_production_mode_callback(state, session_info, action, code, ip_address):
    """处理生产模式下的回调"""
    logger.info(f"生产环境企业微信处理 - state: {state}, action: {action}, IP: {ip_address}")
    
    # 检查action是否为None
    if action is None:
        logger.warning(f"企业微信回调处理 - action为None, state: {state}, IP: {ip_address}")
        return {
            'success': False,
            'username': None,
            'user_info': None
        }
    
    # 添加打印语句 - 诊断用户切换问题
    print(f"DEBUG: 进入handle_production_mode_callback函数 - state: {state}, action: {action}, 当前会话用户: {session.get('username')}")
    print(f"DEBUG: session_info: {session_info}, code: {code}")
    
    result = {
        'success': False,
        'username': None,
        'user_info': None
    }
    
    try:
        # 1. 获取access_token
        access_token = get_wechat_access_token(ip_address)
        if not access_token:
            return result
        
        # 2. 使用code获取用户信息
        user_info = get_wechat_user_info(access_token, code, ip_address)
        if not user_info or 'UserId' not in user_info:
            logger.error(f"企业微信返回的用户信息中没有UserId: {user_info}, IP: {ip_address}")
            return result
        
        userid = user_info['UserId']
        
        # 添加打印语句 - 记录获取的微信用户ID
        print(f"DEBUG: 获取微信用户ID: {userid}, 操作类型: {action}")
        
        # 3. 获取用户详细信息
        user_detail = get_wechat_user_detail(access_token, userid, ip_address)
        if not user_detail:
            return result
        
        # 4. 根据操作类型处理
        if action == 'login':
            # 处理登录操作
            print(f"DEBUG: 执行登录操作 - 微信用户ID: {userid}")
            result = handle_wechat_login(userid, user_detail)
        elif action == 'bind':
            # 处理绑定操作
            print(f"DEBUG: 执行绑定操作 - 微信用户ID: {userid}, 当前会话用户: {session.get('username')}")
            result = handle_wechat_bind(userid, user_detail, ip_address)
            # 确保在需要确认时保存临时信息到会话
            if not result['success'] and result.get('need_confirm'):
                session['wechat_bind_temp_info'] = result.get('wechat_user_info', {})
                session['user_display_name'] = result.get('user_display_name', '')
                print(f"DEBUG: 保存临时绑定信息 - 微信用户ID: {userid}, 会话用户: {session.get('username')}")
        
    except Exception as e:
        logger.error(f"生产环境企业微信处理异常: {e}, IP: {ip_address}")
        print(f"DEBUG: 回调处理异常: {str(e)}")
    
    # 添加打印语句 - 记录处理结果
    print(f"DEBUG: 回调处理结果 - success: {result.get('success')}, username: {result.get('username')}, action: {action}")
    
    return result

def get_wechat_access_token(ip_address):
    """获取企业微信access_token"""
    try:
        access_token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECHAT_CORP_ID}&corpsecret={WECHAT_APP_SECRET}"
        logger.info(f"调用企业微信API获取access_token - IP: {ip_address}")
        
        response = requests.get(access_token_url, timeout=10)
        access_token_data = response.json()
        
        if access_token_data.get('errcode') != 0:
            logger.error(f"获取企业微信access_token失败: {access_token_data}, IP: {ip_address}")
            return None
        
        return access_token_data.get('access_token')
    except Exception as e:
        logger.error(f"获取access_token异常: {e}, IP: {ip_address}")
        return None

def get_wechat_user_info(access_token, code, ip_address):
    """使用code获取企业微信用户信息"""
    try:
        user_info_url = f"https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo?access_token={access_token}&code={code}"
        logger.info(f"调用企业微信API获取用户信息 - IP: {ip_address}")
        
        response = requests.get(user_info_url, timeout=10)
        user_info_data = response.json()
        
        if user_info_data.get('errcode') != 0:
            logger.error(f"获取企业微信用户信息失败: {user_info_data}, IP: {ip_address}")
            return None
        
        return user_info_data
    except Exception as e:
        logger.error(f"获取用户信息异常: {e}, IP: {ip_address}")
        return None

def get_wechat_user_detail(access_token, userid, ip_address):
    """获取企业微信用户详细信息"""
    try:
        user_detail_url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={access_token}&userid={userid}"
        response = requests.get(user_detail_url, timeout=10)
        user_detail_data = response.json()
        
        if user_detail_data.get('errcode') != 0:
            logger.error(f"获取企业微信用户详细信息失败: {user_detail_data}, IP: {ip_address}")
            return None
        
        return user_detail_data
    except Exception as e:
        logger.error(f"获取用户详细信息异常: {e}, IP: {ip_address}")
        return None

def handle_wechat_login(userid, user_detail):
    """处理企业微信登录"""
    # 生成用户名
    username = f"wx_corp_{userid}"
    wechat_name = user_detail.get('name', '企业微信用户')
    
    # 检查用户是否存在于数据库中
    # 先尝试通过wechat_corp_userid查找已绑定的用户，再尝试通过username查找
    user = User.query.filter_by(wechat_corp_userid=userid).first()
    if not user:
        user = User.query.filter_by(username=username).first()
    
    if not user:
        # 用户不存在，返回特殊状态，需要显示确认弹窗
        session['wechat_temp_info'] = {
            'userid': userid,
            'name': wechat_name,
            'avatar': user_detail.get('avatar', ''),
            'username': username
        }
        return {
            'success': False,
            'username': username,
            'user_info': None,
            'user_not_exist': True,
            'wechat_user_info': {'name': wechat_name}
        }
    elif not user.display_name:
        # 如果用户存在但没有设置display_name，设置为微信用户名
        try:
            user.display_name = wechat_name
            db.session.commit()
        except Exception as e:
            logger.error(f"更新企业微信用户display_name失败: {e}")
            db.session.rollback()
    
    # 设置会话信息 - 使用实际用户的username而不是生成的username
    session['username'] = user.username  # 使用数据库中的实际用户名
    session['login_type'] = 'wechat_corp'
    session['user_info'] = {
        'userid': userid,
        'name': wechat_name,
        'avatar': user_detail.get('avatar', '')
    }
    session.permanent = True
    
    return {
        'success': True,
        'username': user.username,  # 使用数据库中的实际用户名
        'user_info': session['user_info']
    }

def handle_wechat_bind(userid, user_detail, ip_address):
    """处理企业微信绑定 - 仅针对已登录用户补充企业微信信息（返回需要确认状态）"""
    # 添加打印语句 - 诊断用户切换问题
    print(f"DEBUG: 进入handle_wechat_bind函数 - 当前会话用户: {session.get('username')}, 微信userid: {userid}")
    print(f"DEBUG: 当前会话内容: {dict(session)}")
    
    # 1. 前置校验 - 严格要求用户必须已登录
    if 'username' not in session:
        logger.warning(f"绑定操作需要先登录 - IP: {ip_address}")
        return {
            'success': False,
            'username': None,
            'user_info': None,
            'error': '请先登录系统'
        }
    
    current_username = session['username']
    logger.info(f"企业微信绑定处理 - 仅针对已登录用户: {current_username}, IP: {ip_address}")
    
    # 验证用户ID格式，防止注入攻击
    if not userid or not isinstance(userid, str) or len(userid) > 100:
        logger.warning(f"企业微信绑定 - 无效的用户ID: {userid}, IP: {ip_address}")
        return {
            'success': False,
            'username': current_username,
            'user_info': None,
            'error': '无效的企业微信账号'
        }
    
    # 确保user_detail是字典类型
    if not isinstance(user_detail, dict):
        logger.error(f"企业微信绑定失败: user_detail不是字典类型, IP: {ip_address}")
        return {
            'success': False,
            'username': current_username,
            'user_info': None,
            'error': '获取企业微信信息失败'
        }
    
    # 提取并验证必要的企业微信信息
    wechat_name = user_detail.get('name', '')
    if not wechat_name or not isinstance(wechat_name, str):
        logger.warning(f"企业微信绑定 - 无效的用户名: {wechat_name}, IP: {ip_address}")
        wechat_name = '企业微信用户'
    
    wechat_avatar = user_detail.get('avatar', '')
    
    # 2. 绑定过程校验
    try:
        # 查找已登录用户（仅操作已存在用户，不创建新用户）
        user = User.query.filter_by(username=current_username).first()
        
        # 添加打印语句 - 记录用户查询结果
        print(f"DEBUG: 查找用户结果 - 用户名: {current_username}, 用户存在: {user is not None}")
        
        if not user:
            logger.error(f"企业微信绑定失败: 用户 {current_username} 不存在, IP: {ip_address}")
            return {
                'success': False,
                'username': current_username,
                'user_info': None,
                'error': '用户不存在'
            }
        
        # 安全校验：检查该微信账号是否已被其他用户绑定
        existing_user = User.query.filter_by(wechat_corp_userid=userid).first()
        if existing_user and existing_user.username != current_username:
            logger.warning(f"微信账号已被其他用户绑定 - 微信ID: {userid}, 当前用户: {current_username}, 已绑定用户: {existing_user.username}, IP: {ip_address}")
            print(f"DEBUG: 微信账号冲突 - 微信ID: {userid}, 当前用户: {current_username}, 已绑定用户: {existing_user.username}")
            return {
                'success': False,
                'username': current_username,
                'user_info': None,
                'error': '该企业微信账号已被其他用户绑定'
            }
        
        # 检查用户是否已经绑定了其他企业微信账号
        if hasattr(user, 'wechat_corp_userid') and user.wechat_corp_userid:
            if user.wechat_corp_userid != userid:
                logger.info(f"企业微信绑定 - 用户已绑定其他微信账号，准备更新绑定 - 当前绑定: {user.wechat_corp_userid}, 新账号: {userid}, IP: {ip_address}")
                print(f"DEBUG: 用户更新绑定 - 当前绑定ID: {user.wechat_corp_userid}, 新账号ID: {userid}")
        
        # 获取用户显示名称
        user_display_name = current_username
        if hasattr(user, 'display_name') and user.display_name:
            user_display_name = user.display_name
        
        # 不立即更新数据库，而是返回需要确认的状态
        logger.info(f"企业微信绑定需要用户确认 - 用户名: {current_username}, 微信用户: {wechat_name}, IP: {ip_address}")
        print(f"DEBUG: 返回需要确认状态 - 用户名: {current_username}, 微信用户: {wechat_name}")
        
        # 返回需要确认的状态，包含完整的微信信息
        return {
            'success': False,
            'username': current_username,
            'user_info': None,
            'need_confirm': True,
            'wechat_user_info': {
                'userid': userid,
                'name': wechat_name,
                'avatar': wechat_avatar
            },
            'user_display_name': user_display_name
        }
    except Exception as e:
        logger.error(f"企业微信绑定处理失败: {str(e)}, IP: {ip_address}")
        print(f"DEBUG: 绑定处理异常: {str(e)}")
        return {
            'success': False,
            'username': current_username,
            'user_info': None,
            'error': '系统处理失败'
        }

def record_wechat_operation_log(username, state, action, success, ip_address, 
                              user_agent, browser, platform, timestamp=None, error_msg=None):
    """记录企业微信操作日志"""
    try:
        # 构建请求参数（过滤敏感信息）
        request_params = {
            'state': state,
            'action': action,
            'has_code': True,
            'user_agent': user_agent[:200] if user_agent else '',
            'browser': browser,
            'platform': platform
        }
        
        if error_msg:
            request_params['error'] = error_msg[:100]
        
        # 计算响应时间
        response_time = 0
        if timestamp:
            response_time = time.time() - timestamp
        
        # 获取用户唯一ID（通过username查询）
        user_id = None
        if username and username != 'unknown':
            user = User.query.filter_by(username=username).first()
            user_id = user.id if user else None
        
        login_log = LoginLog(
            user_id=user_id,  # 记录用户唯一ID
            username=username if username else 'unknown',
            ip_address=ip_address,
            login_type='wechat_corp',
            success=success,
            browser=browser,
            user_agent=user_agent[:255] if user_agent else '',
            platform=platform,
            request_params=json.dumps(request_params, ensure_ascii=False),
            response_time=response_time
        )
        
        db.session.add(login_log)
        db.session.commit()
    except Exception as e:
        logger.error(f"保存企业微信操作日志失败: {e}")
        try:
            db.session.rollback()
        except:
            pass

def cleanup_callback_resources(state):
    """清理回调相关资源"""
    try:
        wechat_sessions = get_wechat_sessions()
        if state in wechat_sessions:
            del wechat_sessions[state]
            save_wechat_sessions(wechat_sessions)
            logger.info(f"清理企业微信回调资源 - state: {state}")
    except Exception as e:
        logger.warning(f"清理企业微信回调资源失败: {e}")

@bp.route('/confirm_wechat_login')
def confirm_wechat_login():
    """确认企业微信登录并创建用户"""
    ip_address = request.remote_addr
    
    # 获取临时存储的微信用户信息
    wechat_temp_info = session.get('wechat_temp_info')
    if not wechat_temp_info:
        logger.warning(f"企业微信登录确认失败：临时信息不存在 - IP: {ip_address}")
        session['error_message'] = '登录信息已过期，请重新扫码'
        return redirect(url_for('auth.login'))
    
    # 从临时信息中获取用户数据
    userid = wechat_temp_info.get('userid')
    wechat_name = wechat_temp_info.get('name', '企业微信用户')
    username = wechat_temp_info.get('username')
    avatar = wechat_temp_info.get('avatar', '')
    
    # 创建新用户
    try:
        user = User(
            username=username,  # 登录账号
            display_name=wechat_name,  # 系统用户名，使用微信用户名
            password='',  # 微信登录用户不需要密码
            wechat_corp_userid=userid,  # 微信用户ID
            wechat_corp_name=wechat_name,  # 微信用户名
            wechat_corp_avatar=avatar,
            wechat_corp_binded_at=datetime.now()
        )
        db.session.add(user)
        db.session.commit()
        logger.info(f"企业微信新用户创建成功 - 用户名: {username}, 微信昵称: {wechat_name}, IP: {ip_address}")
    except Exception as e:
        logger.error(f"创建企业微信用户失败: {e}, IP: {ip_address}")
        db.session.rollback()
        session['error_message'] = '创建用户失败，请稍后重试'
        return redirect(url_for('auth.login'))
    finally:
        # 清理临时数据
        session.pop('wechat_temp_info', None)
        session.pop('wechat_user_info', None)
    
    # 设置会话信息，完成登录
    session['username'] = username
    session['login_type'] = 'wechat_corp'
    session['user_info'] = {
        'userid': userid,
        'name': wechat_name,
        'avatar': avatar
    }
    session.permanent = True
    
    return redirect(url_for('auth.user_center'))

@bp.route('/confirm_wechat_bind')
def confirm_wechat_bind():
    print(f"DEBUG: 进入confirm_wechat_bind函数 - 当前会话用户: {session.get('username')}")
    print(f"DEBUG: 当前会话内容: {dict(session)}")
    """确认企业微信绑定并更新用户信息
    
    重要原则：
    1. 仅针对已登录用户补充企微信息，绝不创建新用户
    2. 核查企微账号是否已被其他用户绑定，避免重复绑定
    3. 仅更新当前登录用户的企微相关必要字段
    """
    ip_address = request.remote_addr
    browser_info = extract_browser_info(request.headers.get('User-Agent', ''))
    
    # 1. 确认绑定前的严格校验 - 必须已登录
    if 'username' not in session:
        logger.warning(f"绑定确认操作需要先登录 - IP: {ip_address}, 浏览器: {browser_info}")
        session['error_message'] = '请先登录系统'
        return redirect(url_for('auth.login'))
    
    current_username = session['username']
    logger.info(f"处理企业微信绑定确认 - 用户名: {current_username}, IP: {ip_address}, 浏览器: {browser_info}")
    
    # 获取临时存储的微信用户信息
    wechat_bind_info = session.get('wechat_bind_temp_info')
    print(f"DEBUG: 从会话获取临时微信绑定信息 - 信息存在: {wechat_bind_info is not None}")
    
    if not wechat_bind_info:
        logger.warning(f"企业微信绑定确认失败：临时信息不存在 - IP: {ip_address}, 用户名: {current_username}")
        session['error_message'] = '绑定信息已过期，请重新扫码'
        return redirect(url_for('auth.user_center'))
    
    # 从临时信息中获取微信用户数据并进行严格验证
    userid = wechat_bind_info.get('userid')
    wechat_name = wechat_bind_info.get('name', '企业微信用户')
    avatar = wechat_bind_info.get('avatar', '')
    print(f"DEBUG: 微信绑定信息 - userid: {userid}, name: {wechat_name}")
    
    # 验证必要的微信信息，防止恶意输入
    if not userid or not isinstance(userid, str) or len(userid) > 100:
        logger.warning(f"企业微信绑定 - 无效的用户ID: {userid}, IP: {ip_address}, 用户名: {current_username}")
        session['error_message'] = '无效的企业微信账号信息'
        return redirect(url_for('auth.user_center'))
    
    # 2. 执行绑定操作 - 仅更新已存在用户的企业微信相关字段
    try:
        # 使用数据库事务确保数据一致性
        with db.session.begin_nested():
            # 查找已登录用户（仅操作已存在用户，绝对不创建新用户）
            user = User.query.filter_by(username=current_username).first()
            print(f"DEBUG: 查找登录用户结果 - 用户名: {current_username}, 用户存在: {user is not None}")
            
            if not user:
                logger.error(f"企业微信绑定失败: 用户 {current_username} 不存在, IP: {ip_address}")
                session['error_message'] = '用户不存在，绑定失败'
                return redirect(url_for('auth.user_center'))
            
            # 安全校验：再次检查该微信账号是否已被其他用户绑定
            existing_user = User.query.filter_by(wechat_corp_userid=userid).first()
            print(f"DEBUG: 检查微信账号是否已被绑定 - 微信ID: {userid}, 已绑定用户: {existing_user.username if existing_user else None}")
            
            if existing_user and existing_user.username != current_username:
                logger.warning(f"微信账号已被其他用户绑定 - 微信ID: {userid}, 当前用户: {current_username}, 已绑定用户: {existing_user.username}, IP: {ip_address}")
                print(f"DEBUG: 微信账号冲突 - 当前用户: {current_username}, 已绑定用户: {existing_user.username}")
                # 清理临时数据
                session.pop('wechat_bind_temp_info', None)
                session.pop('user_display_name', None)
                # 渲染确认弹窗页面，告知用户账号已被绑定
                return render_template_string('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>绑定提醒 - Hello World</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#3b82f6',
                        secondary: '#10b981',
                        warning: '#f59e0b',
                        danger: '#ef4444',
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
            .shadow-pop {
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            }
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="bg-white rounded-lg shadow-pop max-w-md w-full mx-auto overflow-hidden">
        <div class="bg-danger p-4">
            <h2 class="text-white text-xl font-bold text-center flex items-center justify-center gap-2">
                <i class="fa fa-exclamation-circle"></i>
                <span>绑定失败</span>
            </h2>
        </div>
        <div class="p-6">
            <div class="text-center mb-6">
                <i class="fa fa-wechat text-4xl text-green-500 mb-4"></i>
                <h3 class="text-xl font-semibold text-gray-800 mb-2">该企业微信账号已被其他用户绑定</h3>
                <p class="text-gray-600">此微信账号已与其他账户关联，无法重复绑定。</p>
            </div>
            
            <div class="text-center">
                <button id="backButton" class="inline-flex items-center justify-center px-4 py-2 bg-primary text-white rounded-md hover:bg-primary/90 transition-colors">
                    <i class="fa fa-arrow-left mr-2"></i>
                    返回用户中心
                </button>
            </div>
        </div>
    </div>
    
    <script>
        document.getElementById('backButton').addEventListener('click', function() {
            window.location.href = '{{ url_for("auth.user_center") }}';
        });
        
        // 防止用户通过后退按钮绕过提示
        window.onpopstate = function() {
            window.location.href = '{{ url_for("auth.user_center") }}';
        };
        history.pushState({}, '', '');
    </script>
</body>
</html>
''')
            
            # 检查用户是否已经绑定了其他企业微信账号
            old_userid = None
            old_wechat_name = None
            if hasattr(user, 'wechat_corp_userid') and user.wechat_corp_userid:
                old_userid = user.wechat_corp_userid
                old_wechat_name = getattr(user, 'wechat_corp_name', '') if hasattr(user, 'wechat_corp_name') else ''
                if user.wechat_corp_userid != userid:
                    logger.info(f"企业微信绑定更新 - 用户重新绑定微信账号 - 用户名: {current_username}, 当前绑定ID: {old_userid}, 当前绑定名称: {old_wechat_name}, 新账号ID: {userid}, 新账号名称: {wechat_name}, IP: {ip_address}")
                    # 如果有其他用户已绑定此微信账号，先解除其绑定（安全考虑）
                if existing_user:
                    logger.info(f"解除其他用户的微信绑定 - 解除绑定用户: {existing_user.username}, 微信ID: {userid}, IP: {ip_address}")
                    print(f"DEBUG: 解除其他用户绑定 - 解除用户: {existing_user.username}, 微信ID: {userid}")
                    existing_user.wechat_corp_userid = None
                    existing_user.wechat_corp_name = None
                    existing_user.wechat_corp_avatar = None
                    existing_user.wechat_corp_binded_at = None
            
            # 仅更新企业微信相关的必要字段（不修改用户ID等核心信息）
            updated_fields = []
            if hasattr(user, 'wechat_corp_userid'):
                user.wechat_corp_userid = userid
                updated_fields.append('wechat_corp_userid')
            if hasattr(user, 'wechat_corp_name'):
                user.wechat_corp_name = wechat_name
                updated_fields.append('wechat_corp_name')
            if hasattr(user, 'wechat_corp_avatar'):
                user.wechat_corp_avatar = avatar
                updated_fields.append('wechat_corp_avatar')
            if hasattr(user, 'wechat_corp_binded_at'):
                user.wechat_corp_binded_at = datetime.now()
                updated_fields.append('wechat_corp_binded_at')
            
            # 更新用户的最后登录时间（如果有此字段）
            if hasattr(user, 'last_login_at'):
                user.last_login_at = datetime.now()
                updated_fields.append('last_login_at')
            
            # 提交数据库更改
            db.session.commit()
            logger.info(f"企业微信绑定成功 - 用户名: {current_username}, 更新字段: {', '.join(updated_fields)}, 微信用户: {wechat_name}, IP: {ip_address}")
            
            # 记录操作日志
            record_wechat_operation_log(
                username=current_username,
                state='',
                action='bind',
                success=True,
                ip_address=ip_address,
                user_agent='',
                browser=browser_info,
                platform=''
            )
            
            # 更新会话中的用户信息
            print(f"DEBUG: 更新会话用户信息 - 用户ID: {current_username}, 微信ID: {userid}")
            session['user_info'] = {
                'userid': userid,
                'name': wechat_name,
                'avatar': avatar
            }
            session['login_type'] = 'wechat_corp'  # 更新登录类型
            session.modified = True
            
            # 设置绑定成功消息
            session['bind_success'] = True
            if old_userid:
                session['success_message'] = '企业微信绑定已更新！'
            else:
                session['success_message'] = '企业微信绑定成功！'
    except IntegrityError as e:
        logger.error(f"企业微信绑定数据库完整性错误: {str(e)}, IP: {ip_address}, 用户名: {current_username}")
        db.session.rollback()
        session['error_message'] = '数据库约束冲突，绑定失败'
    except DatabaseError as e:
        logger.error(f"企业微信绑定数据库错误: {str(e)}, IP: {ip_address}, 用户名: {current_username}")
        db.session.rollback()
        session['error_message'] = '数据库操作失败，绑定失败'
    except Exception as e:
        logger.error(f"企业微信绑定确认失败: {str(e)}, IP: {ip_address}, 用户名: {current_username}")
        try:
            db.session.rollback()
        except Exception as rollback_error:
            logger.error(f"企业微信绑定回滚失败: {str(rollback_error)}, IP: {ip_address}, 用户名: {current_username}")
        session['error_message'] = '绑定失败，请稍后重试'
        # 记录失败日志
        record_wechat_operation_log(
            username=current_username,
            state='',
            action='bind',
            success=False,
            ip_address=ip_address,
            user_agent='',
            browser=browser_info,
            platform='',
            error_msg=str(e)
        )
    finally:
        # 清理临时数据
        session.pop('wechat_bind_temp_info', None)
        session.pop('user_display_name', None)
    
    return redirect(url_for('auth.user_center'))

def handle_callback_response(action, result):
    """处理回调响应"""
    # 确保会话数据被保存
    session.modified = True
    # DEBUG打印
    current_username = session.get('username', '未登录')
    logger.debug(f"[DEBUG] 进入handle_callback_response - 当前会话用户: {current_username}, 操作类型: {action}, 结果: {result}")
    
    # 处理用户不存在的特殊情况
    if action == 'login' and not result['success'] and result.get('user_not_exist'):
        logger.debug(f"[DEBUG] 处理登录-用户不存在情况 - 会话用户: {current_username}, 微信用户ID: {result.get('wechat_user_info', {}).get('userid')}")
        # 保存微信用户信息到会话，用于弹窗显示
        session['wechat_user_info'] = result.get('wechat_user_info', {})
        # 渲染确认弹窗页面
        return render_template_string('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户确认 - Hello World</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#3b82f6',
                        secondary: '#10b981',
                        warning: '#f59e0b',
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
            .modal-shadow {
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            }
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-2xl p-8 max-w-md w-full modal-shadow transform transition-all">
            <div class="text-center mb-6">
                <div class="inline-flex items-center justify-center w-16 h-16 bg-warning/10 text-warning rounded-full mb-4">
                    <i class="fa fa-info-circle text-3xl"></i>
                </div>
                <h3 class="text-xl font-bold text-gray-900 mb-2">用户不存在</h3>
                <p class="text-gray-600">您的企业微信账号尚未在系统中注册，是否确认继续登录？</p>
                <p class="text-sm text-gray-500 mt-2">企业微信昵称：{{ wechat_user_info.name }}</p>
            </div>
            
            <div class="flex space-x-4">
                <button id="cancelButton" class="flex-1 py-3 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
                    返回登录
                </button>
                <button id="confirmButton" class="flex-1 py-3 px-4 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors">
                    确认登录
                </button>
            </div>
        </div>
    </div>

    <script>
        // 确认按钮点击事件
        document.getElementById('confirmButton').addEventListener('click', function() {
            // 跳转到确认登录路由
            window.location.href = '{{ url_for("auth.confirm_wechat_login") }}';
        });
        
        // 取消按钮点击事件
        document.getElementById('cancelButton').addEventListener('click', function() {
            // 返回登录页面
            window.location.href = '{{ url_for("auth.login") }}';
        });
        
        // 按ESC键关闭弹窗
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                window.location.href = '{{ url_for("auth.login") }}';
            }
        });
    </script>
</body>
</html>''', wechat_user_info=result.get('wechat_user_info', {}))
    
    # 处理企业微信绑定需要确认的情况
    if action == 'bind' and not result['success'] and result.get('need_confirm'):
        logger.debug(f"[DEBUG] 处理绑定-需要确认情况 - 会话用户: {current_username}, 微信用户ID: {result.get('wechat_user_info', {}).get('userid')}")
        # 保存微信用户信息到会话，用于弹窗显示和后续确认操作
        session['wechat_bind_temp_info'] = result.get('wechat_user_info', {})
        session['user_display_name'] = result.get('user_display_name', '')
        
        # 检查企业微信账号是否已被其他用户绑定
        wechat_userid = result.get('wechat_user_info', {}).get('userid')
        is_already_bound = False
        bound_username = None
        if wechat_userid:
            try:
                # 查找是否有其他用户已绑定此企业微信账号
                existing_user = User.query.filter_by(wechat_corp_userid=wechat_userid).first()
                if existing_user and existing_user.username != session.get('username'):
                    is_already_bound = True
                    bound_username = existing_user.username
            except Exception as e:
                logger.error(f"检查企业微信账号绑定状态失败: {e}")
        
        # 渲染确认绑定弹窗页面
        return render_template_string('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>确认企业微信绑定 - Hello World</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        primary: '#07C160',
                        secondary: '#10b981',
                        warning: '#f59e0b',
                        danger: '#ef4444'
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
            .modal-shadow {
                box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
            }
            .fade-in {
                animation: fadeIn 0.3s ease-in-out;
            }
            .avatar-hover {
                transition: transform 0.3s ease;
            }
            .avatar-hover:hover {
                transform: scale(1.05);
            }
            .button-hover {
                transition: all 0.3s ease;
            }
            .button-hover:active {
                transform: translateY(1px);
            }
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center p-4">
    <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-2xl p-8 max-w-md w-full modal-shadow transform transition-all fade-in">
            <div class="text-center mb-6">
                <div class="inline-flex items-center justify-center w-20 h-20 bg-primary/10 text-primary rounded-full mb-4">
                    <i class="fa fa-weixin text-4xl"></i>
                </div>
                <h3 class="text-2xl font-bold text-gray-900 mb-3">确认企业微信绑定</h3>
                
                {% if is_already_bound %}
                <div class="bg-danger/10 p-4 rounded-lg border border-danger/20 mb-6">
                    <div class="flex items-start">
                        <i class="fa fa-exclamation-circle text-danger mt-1 mr-2"></i>
                        <div>
                            <div class="text-sm font-medium text-danger mb-1">警告：账号冲突</div>
                            <div class="text-sm text-gray-700">该企业微信账号已被绑定到系统账号 <span class="font-semibold">{{ bound_username }}</span>。绑定后将覆盖原绑定关系。</div>
                        </div>
                    </div>
                </div>
                {% else %}
                <p class="text-gray-600 mb-6">您确定要将企业微信账号绑定到以下系统账号吗？</p>
                {% endif %}
                
                <!-- 企业微信头像和昵称 -->
                <div class="flex flex-col items-center mb-6">
                    <img src="{{ wechat_user_info.avatar if wechat_user_info.avatar else 'data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><circle cx=%2250%22 cy=%2250%22 r=%2240%22 fill=%22%23e8f5e8%22/><text x=%2250%22 y=%2255%22 font-family=%22Arial%22 font-size=%2230%22 text-anchor=%22middle%22 fill=%22%2307C160%22>企业微信</text></svg>' }}" 
                         class="w-20 h-20 rounded-full border-4 border-primary/10 object-cover mb-3 avatar-hover" 
                         alt="企业微信头像">
                    <div class="font-semibold text-lg text-gray-900">{{ wechat_user_info.name }}</div>
                    {% if wechat_user_info.userid %}
                    <div class="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded font-mono">
                        {{ wechat_user_info.userid }}
                    </div>
                    {% endif %}
                </div>
                
                <!-- 信息卡片 -->
                <div class="space-y-3 mb-6">
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <div class="text-sm text-gray-500 mb-1">当前登录账号</div>
                        <div class="font-medium text-gray-900">{{ user_display_name }}</div>
                    </div>
                    
                    <!-- 添加一个提示卡片 -->
                    <div class="bg-warning/10 p-4 rounded-lg border border-warning/20">
                        <div class="flex items-start">
                            <i class="fa fa-info-circle text-warning mt-1 mr-2"></i>
                            <div>
                                <div class="text-sm font-medium text-warning mb-1">绑定说明</div>
                                <div class="text-sm text-gray-700">
                                    绑定后将更新当前登录账号的企业微信信息，可使用企业微信扫码快速登录。
                                    一个企业微信账号只能绑定到一个系统账号。
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 按钮区域 -->
            <div class="flex space-x-4">
                <button id="cancelButton" class="flex-1 py-3 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors button-hover">
                    取消
                </button>
                {% if is_already_bound %}
                <button id="confirmButton" class="flex-1 py-3 px-4 bg-danger text-white rounded-lg hover:bg-danger/90 transition-colors button-hover shadow-lg shadow-danger/20">
                    确认覆盖绑定
                </button>
                {% else %}
                <button id="confirmButton" class="flex-1 py-3 px-4 bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors button-hover shadow-lg shadow-primary/20">
                    确认绑定
                </button>
                {% endif %}
            </div>
            
            <!-- 提示文本 -->
            <div class="text-center text-xs text-gray-500 mt-4">
                按 <kbd class="px-2 py-0.5 bg-gray-200 rounded">ESC</kbd> 键可取消操作
            </div>
        </div>
    </div>

    <script>
        // 确认按钮点击事件
        document.getElementById('confirmButton').addEventListener('click', function() {
            // 添加按钮加载状态
            const button = this;
            button.disabled = true;
            button.innerHTML = '<i class="fa fa-spinner fa-spin mr-2"></i>处理中...';
            
            // 跳转到确认绑定路由
            setTimeout(() => {
                window.location.href = '{{ url_for("auth.confirm_wechat_bind") }}';
            }, 300);
        });
        
        // 取消按钮点击事件
        document.getElementById('cancelButton').addEventListener('click', function() {
            // 返回用户中心
            window.location.href = '{{ url_for("auth.user_center") }}';
        });
        
        // 按ESC键关闭弹窗
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                window.location.href = '{{ url_for("auth.user_center") }}';
            }
        });
        
        // 添加页面加载动画效果
        window.addEventListener('load', function() {
            const modal = document.querySelector('.fade-in');
            modal.style.opacity = '1';
        });
    </script>
</body>
</html>''', wechat_user_info=result.get('wechat_user_info', {}), user_display_name=result.get('user_display_name', ''), is_already_bound=is_already_bound, bound_username=bound_username)
    
    if not result['success']:
        logger.debug(f"[DEBUG] 处理操作失败 - 会话用户: {current_username}, 操作类型: {action}")
        # 处理其他失败情况
        session['error_message'] = '操作失败，请稍后重试'
        # 绑定失败时返回用户中心
        if action == 'bind':
            return redirect(url_for('auth.user_center'))
        return redirect(url_for('auth.login'))
    
    # 根据操作类型设置成功消息
    if action == 'login':
        logger.debug(f"[DEBUG] 登录成功 - 会话用户: {current_username}")
        # 登录成功，跳转到用户中心
        return redirect(url_for('auth.user_center'))
    elif action == 'bind':
        logger.debug(f"[DEBUG] 绑定成功 - 会话用户: {current_username}")
        # 绑定成功，设置成功消息并跳转到用户中心
        session['bind_success'] = True
        return redirect(url_for('auth.user_center'))
    elif action is None:
        logger.warning(f"[WARN] 操作类型为None - 会话用户: {current_username}")
        # 操作类型为None，设置错误消息并跳转到用户中心
        session['error_message'] = '操作类型错误，请重试'
        return redirect(url_for('auth.user_center'))
    else:
        logger.debug(f"[DEBUG] 未知操作类型 - 会话用户: {current_username}, 操作类型: {action}")
        # 未知操作类型，默认跳转到用户中心
        return redirect(url_for('auth.user_center'))


def format_datetime_with_timezone(dt):
    """格式化日期时间，添加时区信息"""
    if not dt:
        return ''
    # 这里假设时间存储为UTC，转换为中国时区（UTC+8）
    from datetime import timezone, timedelta
    cst_tz = timezone(timedelta(hours=8))
    
    try:
        # 如果datetime对象没有时区信息，添加UTC时区并转换
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        cst_dt = dt.astimezone(cst_tz)
        return cst_dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.error(f"格式化日期时间失败: {e}")
        # 如果转换失败，返回原始格式
        return dt.strftime('%Y-%m-%d %H:%M:%S')


@bp.route('/user_center')
def user_center():
    """用户中心页面"""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    username = session.get('username')
    login_type = session.get('login_type', 'default')
    user_info = session.get('user_info', {})
    display_name = username  # 默认使用username作为显示名称
    
    # 检查是否已绑定企业微信
    wechat_binded = False
    wechat_info = {}
    user_id = None
    user_avatar = None
    
    # 获取绑定成功消息（如果有）
    bind_success = session.pop('bind_success', False)
    
    # 获取用户真实IP
    real_ip = request.headers.get('X-Forwarded-For', request.headers.get('X-Real-IP', request.remote_addr))
    if ',' in real_ip:
        real_ip = real_ip.split(',')[0].strip()
    
    # 获取最近一次登录记录，用于显示真实登录时间
    last_login_time = None
    last_login_ip = None
    
    try:
        user = User.query.filter_by(username=username).first()
        if user:
            user_id = user.id
            wechat_binded = bool(user.wechat_corp_userid)
            # 如果用户有display_name，使用它
            if hasattr(user, 'display_name') and user.display_name:
                display_name = user.display_name
            
            # 从数据库加载企业微信信息
            if wechat_binded:
                wechat_info = {
                    'userid': user.wechat_corp_userid,
                    'name': user.wechat_corp_name,
                    'avatar': user.wechat_corp_avatar,
                    'binded_at': user.wechat_corp_binded_at
                }
                # 如果有企业微信头像，使用它
                if user.wechat_corp_avatar:
                    user_avatar = user.wechat_corp_avatar
        
        # 获取最近一次成功登录记录
        last_login = LoginLog.query.filter_by(username=username, success=True)\
            .order_by(LoginLog.created_at.desc())\
            .first()
        
        if last_login:
            last_login_time = last_login.created_at
            last_login_ip = last_login.ip_address
            
    except Exception as e:
        logger.error(f"查询用户信息失败: {e}")
    
    # 查询用户的登录历史记录
    login_history = []
    try:
        login_history = LoginLog.query.filter_by(username=username)\
            .order_by(LoginLog.created_at.desc())\
            .limit(10).all()
    except Exception as e:
        logger.error(f"查询登录历史失败: {e}")
    
    # 准备模板变量，移除不必要的request对象传递
    current_time = datetime.now(timezone.utc)
    current_year = current_time.year
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户中心 - Hello World</title>
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
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen flex flex-col">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm">
        <div class="container mx-auto px-4 py-3 flex justify-between items-center">
            <div class="flex items-center space-x-2">
                <i class="fa fa-user-circle text-primary text-2xl"></i>
                <h1 class="text-xl font-bold text-gray-800">用户中心</h1>
            </div>
            <div class="flex items-center space-x-4">
                <span class="text-gray-600">欢迎，{{ display_name }}</span>
                    {% if user_avatar %}
                    <img src="{{ user_avatar }}" alt="用户头像" class="w-8 h-8 rounded-full ml-2">
                    {% endif %}
                <a href="{{ url_for('auth.logout') }}" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-md transition-colors">
                    <i class="fa fa-sign-out mr-1"></i> 退出登录
                </a>
            </div>
        </div>
    </header>

    <!-- 绑定成功提示 -->
    {% if bind_success %}
    <div class="container mx-auto px-4 py-3">
        <div class="bg-green-50 border-l-4 border-green-400 text-green-700 p-4 rounded">
            <div class="flex items-center">
                <i class="fa fa-check-circle text-xl mr-2"></i>
                <p class="font-medium">企业微信绑定成功！</p>
            </div>
        </div>
    </div>
    {% endif %}

    <!-- 主要内容 -->
    <main class="flex-grow container mx-auto px-4 py-8">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <!-- 用户信息卡片 -->
            <div class="bg-white rounded-xl p-6 card-shadow">
                <h2 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                    <i class="fa fa-user-circle text-primary mr-2"></i> 用户基本信息
                </h2>
                <div class="space-y-4">
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">显示名称:</span>
                        <div class="flex items-center">
                            <span class="font-medium text-gray-800 mr-2">{{ display_name }}</span>
                            <a href="{{ url_for('auth.change_display_name') }}" class="text-primary hover:text-primary/80 text-sm transition-colors" title="修改显示名称">
                                <i class="fa fa-pencil"></i>
                            </a>
                        </div>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">登录账号:</span>
                        <span class="font-medium text-gray-800">{{ username }}</span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">登录类型:</span>
                        <span class="font-medium text-gray-800">
                            {% if login_type == 'default' %}
                                <i class="fa fa-lock text-blue-500 mr-1"></i>账号密码
                            {% elif login_type == 'wechat_corp' %}
                                <i class="fa fa-weixin text-green-500 mr-1"></i>企业微信
                            {% else %}
                                其他
                            {% endif %}
                        </span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">用户ID:</span>
                        <span class="font-medium text-gray-800">{{ user_id }}</span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">登录时间:</span>
                        <span class="text-gray-800">
                            {% if last_login_time %}
                                {{ format_datetime_with_timezone(last_login_time) }}
                            {% else %}
                                {{ format_datetime_with_timezone(current_time) }}
                            {% endif %}
                        </span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">IP地址:</span>
                        <span class="text-gray-800">{{ last_login_ip or real_ip }}</span>
                    </div>
                </div>
            </div>

            <!-- 企业微信信息卡片（如果已绑定企业微信） -->
            {% if wechat_binded %}
            <div class="bg-white rounded-xl p-6 card-shadow">
                <h2 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                    <i class="fa fa-weixin text-green-500 mr-2"></i> 企业微信信息
                </h2>
                <div class="space-y-4">
                    <!-- 头像显示 -->
                    <div class="flex items-center justify-center mb-4">
                        {% if wechat_info.get('avatar') %}
                            <img src="{{ wechat_info.avatar }}" alt="企业微信头像" class="w-20 h-20 rounded-full object-cover border-2 border-green-200">
                        {% else %}
                            <div class="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center border-2 border-green-200">
                                <i class="fa fa-user text-green-500 text-3xl"></i>
                            </div>
                        {% endif %}
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">用户ID:</span>
                        <span class="font-medium text-gray-800">{{ wechat_info.get('userid', '未知') }}</span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">姓名:</span>
                        <span class="font-medium text-gray-800">{{ wechat_info.get('name', '未知') }}</span>
                    </div>
                    {% if wechat_info.get('binded_at') %}
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">绑定时间:</span>
                        <span class="text-gray-600">{{ wechat_info.binded_at.strftime('%Y-%m-%d %H:%M:%S') }}</span>
                    </div>
                    {% endif %}
                </div>
            </div>
            {% endif %}

            <!-- 账户安全卡片 -->
            <div class="bg-white rounded-xl p-6 card-shadow">
                <h2 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                    <i class="fa fa-shield text-red-500 mr-2"></i> 账户安全
                </h2>
                <div class="space-y-4">
                    <a href="{{ url_for('auth.change_password') }}" class="w-full bg-primary hover:bg-primary/90 text-white py-2 rounded-md transition-colors flex justify-center items-center btn-hover">
                        <i class="fa fa-key mr-2"></i> 修改密码
                    </a>
                    <div class="text-sm text-gray-500">
                        <p><i class="fa fa-info-circle mr-1"></i> 建议定期更换密码以保障账户安全</p>
                        <p class="mt-2"><i class="fa fa-check-circle text-green-500 mr-1"></i> 您的账户已通过身份验证</p>
                    </div>
                    <div class="pt-4 border-t border-gray-100">
                        {% if not wechat_binded %}
                        <a href="{{ url_for('auth.bind_wechat_corp') }}" class="w-full bg-secondary hover:bg-secondary/90 text-white py-2 rounded-md transition-colors flex justify-center items-center btn-hover">
                            <i class="fa fa-weixin mr-2"></i> 绑定企业微信
                        </a>
                        {% else %}
                        <button class="w-full bg-gray-100 text-gray-500 py-2 rounded-md transition-colors flex justify-center items-center">
                            <i class="fa fa-check-circle text-green-500 mr-2"></i> 已绑定企业微信
                        </button>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>

        <!-- 登录历史记录 -->
        <div class="mt-8 bg-white rounded-xl p-6 card-shadow">
            <h2 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                <i class="fa fa-history text-gray-500 mr-2"></i> 最近登录记录
            </h2>
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead>
                        <tr>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">登录时间</th>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">登录类型</th>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP地址</th>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">浏览器</th>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">平台</th>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                            <th class="px-4 py-3 bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">错误信息</th>
                        </tr>
                    </thead>
                    <tbody class="bg-white divide-y divide-gray-200">
                        {% for log in login_history %}
                        <tr>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-800">{{ format_datetime_with_timezone(log.created_at) }}</td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-800">
                                {% if log.login_type == 'default' %}
                                    账号密码
                                {% elif log.login_type == 'wechat_corp' %}
                                    企业微信
                                {% else %}
                                    {{ log.login_type }}
                                {% endif %}
                            </td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-800">{{ log.ip_address }}</td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-800">{{ log.browser or '未知' }}</td>
                            <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-800">{{ log.platform or '未知' }}</td>
                            <td class="px-4 py-3 whitespace-nowrap">
                                {% if log.success %}
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">成功</span>
                                {% else %}
                                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">失败</span>
                                {% endif %}
                            </td>
                            <td class="px-4 py-3 text-sm text-gray-800">{{ log.error_message or '无' }}</td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="7" class="px-4 py-3 text-center text-sm text-gray-500">暂无登录记录</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <!-- 页脚 -->
    <footer class="bg-white border-t border-gray-200 py-6">
        <div class="container mx-auto px-4 text-center text-gray-600 text-sm">
            <p>© {{ current_year }} Hello World 系统 | 版本 1.0.0</p>
        </div>
    </footer>
</body>
</html>
''', 
            username=username, 
            display_name=display_name, 
            login_type=login_type, 
            user_info=user_info, 
            login_history=login_history, 
            wechat_binded=wechat_binded, 
            bind_success=bind_success, 
            format_datetime_with_timezone=format_datetime_with_timezone,
            current_time=current_time,
            current_year=current_year,
            user_id=user_id,
            user_avatar=user_avatar,
            wechat_info=wechat_info,
            last_login_time=last_login_time,
            last_login_ip=last_login_ip,
            real_ip=real_ip
        )

@bp.route('/change_display_name', methods=['GET', 'POST'])
def change_display_name():
    """修改显示名称页面"""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    username = session.get('username')
    error_message = None
    success_message = None
    current_display_name = username
    
    # 获取当前显示名称
    try:
        user = User.query.filter_by(username=username).first()
        if user and hasattr(user, 'display_name') and user.display_name:
            current_display_name = user.display_name
    except Exception as e:
        logger.error(f"获取用户显示名称失败: {e}")
    
    if request.method == 'POST':
        new_display_name = request.form.get('display_name').strip()
        
        if not new_display_name:
            error_message = '显示名称不能为空'
        elif len(new_display_name) > 50:
            error_message = '显示名称长度不能超过50个字符'
        else:
            try:
                user = User.query.filter_by(username=username).first()
                if user:
                    # 更新显示名称
                    user.display_name = new_display_name
                    db.session.commit()
                    success_message = '显示名称修改成功'
                    current_display_name = new_display_name
                    logger.info(f"用户 {username} 修改显示名称成功: {new_display_name}")
                else:
                    error_message = '用户不存在'
            except Exception as e:
                logger.error(f"用户 {username} 修改显示名称失败: {e}")
                db.session.rollback()
                error_message = '修改显示名称失败，请稍后重试'
    
    # 渲染修改显示名称页面
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>修改显示名称 - Hello World</title>
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
<body class="bg-gray-100 min-h-screen flex flex-col">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm">
        <div class="container mx-auto px-4 py-3 flex justify-between items-center">
            <div class="flex items-center space-x-2">
                <i class="fa fa-user-circle text-primary text-2xl"></i>
                <h1 class="text-xl font-bold text-gray-800">修改显示名称</h1>
            </div>
            <div class="flex items-center space-x-4">
                <a href="{{ url_for('auth.user_center') }}" class="bg-gray-200 hover:bg-gray-300 text-gray-800 px-4 py-2 rounded-md transition-colors">
                    <i class="fa fa-arrow-left mr-1"></i> 返回
                </a>
            </div>
        </div>
    </header>

    <!-- 主要内容 -->
    <main class="flex-grow container mx-auto px-4 py-8 flex justify-center items-center">
        <div class="w-full max-w-md bg-white rounded-xl p-8 card-shadow">
            <h2 class="text-xl font-semibold mb-6 text-center text-gray-800 flex items-center justify-center">
                <i class="fa fa-user text-primary mr-2"></i> 账户显示名称修改
            </h2>
            
            {% if error_message %}
            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p class="text-red-600 text-sm flex items-center">
                    <i class="fa fa-exclamation-circle mr-2"></i>
                    {{ error_message }}
                </p>
            </div>
            {% endif %}
            
            {% if success_message %}
            <div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                <p class="text-green-600 text-sm flex items-center">
                    <i class="fa fa-check-circle mr-2"></i>
                    {{ success_message }}
                </p>
            </div>
            {% endif %}
            
            <form method="post" class="space-y-4">
                <div>
                    <label for="display_name" class="block text-sm font-medium text-gray-700 mb-1">显示名称</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <i class="fa fa-user-circle"></i>
                        </div>
                        <input 
                            type="text" 
                            id="display_name" 
                            name="display_name" 
                            value="{{ current_display_name }}"
                            required
                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                            placeholder="请输入新的显示名称（最多50个字符）"
                            maxlength="50"
                        >
                    </div>
                </div>
                
                <div class="text-sm text-gray-500 mt-2 mb-4">
                    <p>显示名称将作为您在系统中的昵称，可随时修改</p>
                </div>
                
                <button 
                    type="submit" 
                    class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                >
                    <i class="fa fa-save mr-2"></i> 保存修改
                </button>
            </form>
        </div>
    </main>
</body>
</html>
''', username=username, current_display_name=current_display_name, error_message=error_message, success_message=success_message)

@bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """修改密码页面"""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    username = session.get('username')
    error_message = None
    success_message = None
    
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # 验证密码
        if not old_password or not new_password or not confirm_password:
            error_message = '请填写所有密码字段'
        elif new_password != confirm_password:
            error_message = '两次输入的新密码不一致'
        elif len(new_password) < 6:
            error_message = '新密码长度至少为6位'
        else:
            try:
                # 获取用户
                user = User.query.filter_by(username=username).first()
                if not user:
                    error_message = '用户不存在'
                else:
                    # 验证旧密码
                    old_password_hash = hashlib.sha256(old_password.encode()).hexdigest()
                    if user.password != old_password_hash:
                        error_message = '原密码错误'
                    else:
                        # 更新密码
                        new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                        user.password = new_password_hash
                        db.session.commit()
                        success_message = '密码修改成功'
                        logger.info(f"用户 {username} 修改密码成功")
            except Exception as e:
                logger.error(f"用户 {username} 修改密码时发生错误: {e}")
                db.session.rollback()
                error_message = '修改密码失败，请稍后重试'
    
    # 渲染修改密码页面
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>修改密码 - Hello World</title>
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
<body class="bg-gray-100 min-h-screen flex flex-col">
    <!-- 顶部导航栏 -->
    <header class="bg-white shadow-sm">
        <div class="container mx-auto px-4 py-3 flex justify-between items-center">
            <div class="flex items-center space-x-2">
                <i class="fa fa-user-circle text-primary text-2xl"></i>
                <h1 class="text-xl font-bold text-gray-800">修改密码</h1>
            </div>
            <div class="flex items-center space-x-4">
                <a href="{{ url_for('auth.user_center') }}" class="bg-gray-200 hover:bg-gray-300 text-gray-800 px-4 py-2 rounded-md transition-colors">
                    <i class="fa fa-arrow-left mr-1"></i> 返回
                </a>
            </div>
        </div>
    </header>

    <!-- 主要内容 -->
    <main class="flex-grow container mx-auto px-4 py-8 flex justify-center items-center">
        <div class="w-full max-w-md bg-white rounded-xl p-8 card-shadow">
            <h2 class="text-xl font-semibold mb-6 text-center text-gray-800 flex items-center justify-center">
                <i class="fa fa-key text-primary mr-2"></i> 账户密码修改
            </h2>
            
            {% if error_message %}
            <div class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                <p class="text-red-600 text-sm flex items-center">
                    <i class="fa fa-exclamation-circle mr-2"></i>
                    {{ error_message }}
                </p>
            </div>
            {% endif %}
            
            {% if success_message %}
            <div class="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                <p class="text-green-600 text-sm flex items-center">
                    <i class="fa fa-check-circle mr-2"></i>
                    {{ success_message }}
                </p>
            </div>
            {% endif %}
            
            <form method="post" class="space-y-4">
                <div>
                    <label for="old_password" class="block text-sm font-medium text-gray-700 mb-1">原密码</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <i class="fa fa-lock"></i>
                        </div>
                        <input 
                            type="password" 
                            id="old_password" 
                            name="old_password" 
                            required
                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                            placeholder="请输入原密码"
                        >
                    </div>
                </div>
                
                <div>
                    <label for="new_password" class="block text-sm font-medium text-gray-700 mb-1">新密码</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <i class="fa fa-key"></i>
                        </div>
                        <input 
                            type="password" 
                            id="new_password" 
                            name="new_password" 
                            required
                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                            placeholder="请输入新密码（至少6位）"
                        >
                    </div>
                </div>
                
                <div>
                    <label for="confirm_password" class="block text-sm font-medium text-gray-700 mb-1">确认新密码</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <i class="fa fa-check-square-o"></i>
                        </div>
                        <input 
                            type="password" 
                            id="confirm_password" 
                            name="confirm_password" 
                            required
                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                            placeholder="请再次输入新密码"
                        >
                    </div>
                </div>
                
                <button 
                    type="submit" 
                    class="w-full bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg btn-hover flex items-center justify-center"
                >
                    <i class="fa fa-save mr-2"></i> 保存修改
                </button>
            </form>
        </div>
    </main>
</body>
</html>
''', username=username, error_message=error_message, success_message=success_message)



@bp.route('/logout')
def logout():
    """退出登录 - 完整清除会话信息"""
    # 先获取用户信息用于日志记录
    username = session.get('username', '未知用户')
    login_type = session.get('login_type', '未知类型')
    
    logger.info(f"用户退出登录 - 用户名: {username}, 登录类型: {login_type}, IP: {request.remote_addr}")
    
    # 完整清除所有会话信息
    session.clear()
    
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
                    <label for="username" class="block text-sm font-medium text-gray-700 mb-1">登录账号</label>
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
                            placeholder="请输入登录账号（用于登录系统）"
                            value="{{ username }}"
                        >
                    </div>
                    <p class="text-xs text-gray-500 mt-1">登录账号创建后不可修改</p>
                </div>
                
                <div>
                    <label for="display_name" class="block text-sm font-medium text-gray-700 mb-1">系统用户名</label>
                    <div class="relative">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <i class="fa fa-smile-o"></i>
                        </div>
                        <input 
                            type="text" 
                            id="display_name" 
                            name="display_name" 
                            required
                            class="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                            placeholder="请输入显示名称（用户昵称）"
                            value="{{ display_name }}"
                        >
                    </div>
                    <p class="text-xs text-gray-500 mt-1">这是您在系统中显示的昵称，后续可修改</p>
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

