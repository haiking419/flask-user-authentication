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
                
                login_log = LoginLog(
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
                            
                            login_log = LoginLog(
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
                    
                    login_log = LoginLog(
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
    state = generate_wechat_state()
    # 编码redirect_uri
    encoded_redirect_uri = quote(WECHAT_REDIRECT_URI)
    # 使用官方更新的格式，将corpid改为appid
    wechat_qrcode_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={WECHAT_CORP_ID}&agentid={WECHAT_AGENT_ID}&redirect_uri={encoded_redirect_uri}&state={state}"
    
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
    """企业微信扫码登录"""
    # 获取查询参数
    ip_address = request.remote_addr
    mode = request.args.get('mode', 'production')  # 支持测试模式
    
    # 生成state参数，用于防止CSRF攻击
    state = generate_wechat_state()
    
    # 保存state到数据库，用于后续验证
    try:
        wechat_sessions = get_wechat_sessions()
        wechat_sessions[state] = {
            'timestamp': time.time(),
            'ip_address': ip_address,
            'mode': mode
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
                    <a href="{{ qrcode_url }}" target="_blank">
                        <img src="{{ qrcode_url }}" alt="企业微信登录二维码" class="w-full h-full object-contain">
                    </a>
                </div>
            </div>
            
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
                countdownElement.textContent = '已过期';
                countdownElement.classList.remove('text-primary');
                countdownElement.classList.add('text-red-500');
                refreshButton.classList.remove('opacity-50', 'cursor-not-allowed');
                refreshButton.disabled = false;
            }
        }, 1000);
        
        // 刷新二维码功能
        refreshButton.addEventListener('click', () => {
            window.location.reload();
        });
    </script>
</body>
</html>
    ''', state=state, qrcode_url=qr_code_url)
    except Exception as e:
        logger.error(f"生成企业微信登录URL失败: {e}, IP: {ip_address}")
        return "生成登录二维码失败，请稍后重试", 500

@bp.route('/wechat_callback')
def wechat_callback():
    """企业微信登录回调处理"""
    state = request.args.get('state')
    code = request.args.get('code')
    ip_address = request.remote_addr
    
    # 提取用户代理信息
    user_agent = request.headers.get('User-Agent', '')
    browser = 'Unknown'
    platform = 'Unknown'
    
    # 简单的浏览器和平台识别
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
    
    if 'Windows' in user_agent:
        platform = 'Windows'
    elif 'Macintosh' in user_agent:
        platform = 'macOS'
    elif 'Linux' in user_agent:
        platform = 'Linux'
    elif 'iPhone' in user_agent or 'iPad' in user_agent:
        platform = 'iOS'
    elif 'Android' in user_agent:
        platform = 'Android'
    
    logger.info(f"企业微信登录回调 - state: {state}, code存在: {bool(code)}, IP: {ip_address}")
    
    # 1. 验证请求参数
    if not state or not code:
        logger.warning(f"企业微信登录回调参数不完整 - IP: {ip_address}")
        return "无效的请求参数", 400
    
    # 2. 验证state是否有效
    try:
        wechat_sessions = get_wechat_sessions()
        # 添加调试日志
        logger.info(f"获取到的微信会话数量: {len(wechat_sessions)}, 会话键列表: {list(wechat_sessions.keys())[:3]}")
        
        if state not in wechat_sessions:
            logger.warning(f"企业微信登录回调state无效 - state: {state}, IP: {ip_address}")
            # 对于测试模式，允许跳过state验证
            if code.startswith('test_corp_code_'):
                logger.info(f"测试模式下跳过state验证 - IP: {ip_address}")
                # 创建临时会话数据
                wechat_sessions[state] = {'timestamp': time.time(), 'ip_address': ip_address, 'mode': 'test'}
            else:
                return "无效的请求参数", 400
        
        # 3. 检查state是否过期（10分钟内有效）
        try:
            session_timestamp = wechat_sessions[state]['timestamp']
            # 确保时间戳格式正确
            if isinstance(session_timestamp, datetime):
                session_timestamp = session_timestamp.timestamp()
            
            # 转换为浮点数进行比较
            session_timestamp = float(session_timestamp)
            current_time = time.time()
            
            if current_time - session_timestamp > 600:
                logger.warning(f"企业微信登录回调state已过期 - state: {state}, IP: {ip_address}")
                # 删除过期的session
                del wechat_sessions[state]
                save_wechat_sessions(wechat_sessions)
                return "登录已过期，请重新扫码", 400
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"检查微信会话过期时间时发生错误: {e}, IP: {ip_address}")
            # 如果时间戳检查失败，视为会话无效
            return "会话验证失败，请重新扫码", 400
        
    except Exception as e:
        logger.error(f"验证企业微信state时发生错误: {e}, IP: {ip_address}")
        return "验证失败，请重新尝试", 500
    
    # 4. 在开发/测试环境下的模拟登录逻辑
    if code.startswith('test_corp_code_'):
        logger.info(f"测试环境企业微信登录 - state: {state}, IP: {ip_address}")
        
        # 生成测试用户名
        username = f"wx_corp_test_user_{int(time.time()) % 1000}"
        
        # 将用户信息存储到会话中
        session['username'] = username
        session['login_type'] = 'wechat_corp'  # 记录登录方式
        session.permanent = True  # 设置会话持久化
        
        # 记录登录日志
        try:
            # 构建请求参数（过滤敏感信息）
            request_params = {
                'state': state,
                'has_code': bool(code),
                'user_agent': user_agent[:200] if user_agent else '',
                'browser': browser,
                'platform': platform
            }
            
            login_log = LoginLog(
                username=username,
                ip_address=ip_address,
                login_type='wechat_corp',
                success=True,
                browser=browser,
                user_agent=user_agent[:255] if user_agent else '',
                platform=platform,
                request_params=json.dumps(request_params, ensure_ascii=False),
                response_time=time.time() - session_timestamp if 'timestamp' in wechat_sessions.get(state, {}) else 0
            )
            db.session.add(login_log)
            db.session.commit()
        except Exception as e:
            logger.error(f"保存企业微信登录日志失败: {e}")
            try:
                db.session.rollback()
            except:
                pass
        
        logger.info(f"企业微信测试登录成功 - 用户名: {username}, IP: {ip_address}")
        
        # 清理已使用的state
        try:
            del wechat_sessions[state]
            save_wechat_sessions(wechat_sessions)
        except:
            pass
        
        # 跳转到用户中心
        return redirect(url_for('auth.user_center'))
    
    # 5. 生产环境：调用企业微信API获取用户信息
    try:
        # 5.1 获取access_token
        access_token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={WECHAT_CORP_ID}&corpsecret={WECHAT_APP_SECRET}"
        logger.info(f"调用企业微信API获取access_token - IP: {ip_address}")
        
        response = requests.get(access_token_url, timeout=10)
        access_token_data = response.json()
        
        if access_token_data.get('errcode') != 0:
            logger.error(f"获取企业微信access_token失败: {access_token_data}, IP: {ip_address}")
            return "登录失败，请稍后重试", 500
        
        access_token = access_token_data.get('access_token')
        
        # 5.2 使用code获取用户信息
        user_info_url = f"https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo?access_token={access_token}&code={code}"
        logger.info(f"调用企业微信API获取用户信息 - IP: {ip_address}")
        
        user_info_response = requests.get(user_info_url, timeout=10)
        user_info_data = user_info_response.json()
        
        if user_info_data.get('errcode') != 0:
            logger.error(f"获取企业微信用户信息失败: {user_info_data}, IP: {ip_address}")
            return "登录失败，请稍后重试", 500
        
        # 5.3 获取用户详情
        userid = user_info_data.get('UserId')
        if not userid:
            logger.error(f"企业微信返回的用户信息中没有UserId: {user_info_data}, IP: {ip_address}")
            return "登录失败，请确保您是企业成员", 403
        
        # 5.4 获取用户详细信息
        user_detail_url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={access_token}&userid={userid}"
        user_detail_response = requests.get(user_detail_url, timeout=10)
        user_detail_data = user_detail_response.json()
        
        if user_detail_data.get('errcode') != 0:
            logger.error(f"获取企业微信用户详细信息失败: {user_detail_data}, IP: {ip_address}")
            return "登录失败，请稍后重试", 500
        
        # 6. 处理用户信息，创建或更新用户
        # 生成用户名（可以根据需要调整规则）
        username = f"wx_corp_{userid}"
        
        # 这里可以根据需要查询数据库，创建或更新用户信息
        # 为了演示，我们直接使用微信返回的用户信息
        
        # 7. 将用户信息存储到会话中
        session['username'] = username
        session['login_type'] = 'wechat_corp'  # 记录登录方式
        session['user_info'] = {
            'userid': userid,
            'name': user_detail_data.get('name', '企业微信用户'),
            'avatar': user_detail_data.get('avatar', '')
        }  # 存储用户信息
        session.permanent = True  # 设置会话持久化
        
        # 8. 记录登录日志
        try:
            # 构建请求参数（过滤敏感信息）
            request_params = {
                'state': state,
                'has_code': bool(code),
                'user_agent': user_agent[:200] if user_agent else '',
                'browser': browser,
                'platform': platform
            }
            
            login_log = LoginLog(
                username=username,
                ip_address=ip_address,
                login_type='wechat_corp',
                success=True,
                browser=browser,
                user_agent=user_agent[:255] if user_agent else '',
                platform=platform,
                request_params=json.dumps(request_params, ensure_ascii=False),
                response_time=time.time() - session_timestamp if 'timestamp' in wechat_sessions.get(state, {}) else 0
            )
            db.session.add(login_log)
            db.session.commit()
        except Exception as e:
            logger.error(f"保存企业微信登录日志失败: {e}")
            try:
                db.session.rollback()
            except:
                pass
        
        logger.info(f"企业微信登录成功 - 用户名: {username}, userid: {userid}, IP: {ip_address}")
        
        # 9. 清理已使用的state
        try:
            del wechat_sessions[state]
            save_wechat_sessions(wechat_sessions)
        except:
            pass
        
        # 10. 跳转到用户中心
        return redirect(url_for('auth.user_center'))
        
    except requests.exceptions.RequestException as e:
        logger.error(f"调用企业微信API时发生网络错误: {e}, IP: {ip_address}")
        return "网络连接失败，请检查网络后重试", 500
    except Exception as e:
        logger.error(f"企业微信登录过程中发生未知错误: {e}, IP: {ip_address}")
        return "登录失败，请稍后重试", 500

@bp.route('/user_center')
def user_center():
    """用户中心页面"""
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    username = session.get('username')
    login_type = session.get('login_type', 'default')
    user_info = session.get('user_info', {})
    
    # 查询用户的登录历史记录
    login_history = []
    try:
        login_history = LoginLog.query.filter_by(username=username)\
            .order_by(LoginLog.created_at.desc())\
            .limit(10).all()
    except Exception as e:
        logger.error(f"查询登录历史失败: {e}")
    
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
                <span class="text-gray-600">欢迎，{{ username }}</span>
                <a href="{{ url_for('auth.logout') }}" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-md transition-colors">
                    <i class="fa fa-sign-out mr-1"></i> 退出登录
                </a>
            </div>
        </div>
    </header>

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
                        <span class="text-gray-500 w-24">用户名:</span>
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
                        <span class="text-gray-500 w-24">登录时间:</span>
                        <span class="text-gray-800">{{ format_datetime_with_timezone(datetime.now(timezone.utc)) }}</span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">IP地址:</span>
                        <span class="text-gray-800">{{ request.remote_addr }}</span>
                    </div>
                </div>
            </div>

            <!-- 企业微信信息卡片（如果是企业微信登录） -->
            {% if login_type == 'wechat_corp' and user_info %}
            <div class="bg-white rounded-xl p-6 card-shadow">
                <h2 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                    <i class="fa fa-weixin text-green-500 mr-2"></i> 企业微信信息
                </h2>
                <div class="space-y-4">
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">用户ID:</span>
                        <span class="font-medium text-gray-800">{{ user_info.userid or '未知' }}</span>
                    </div>
                    <div class="flex items-center">
                        <span class="text-gray-500 w-24">姓名:</span>
                        <span class="font-medium text-gray-800">{{ user_info.name or '未知' }}</span>
                    </div>
                </div>
            </div>
            {% endif %}

            <!-- 账户安全卡片 -->
            <div class="bg-white rounded-xl p-6 card-shadow">
                <h2 class="text-lg font-semibold mb-4 text-gray-800 flex items-center">
                    <i class="fa fa-shield text-red-500 mr-2"></i> 账户安全
                </h2>
                <div class="space-y-4">
                    <button class="w-full bg-primary hover:bg-primary/90 text-white py-2 rounded-md transition-colors flex justify-center items-center">
                        <i class="fa fa-key mr-2"></i> 修改密码
                    </button>
                    <div class="text-sm text-gray-500">
                        <p><i class="fa fa-info-circle mr-1"></i> 建议定期更换密码以保障账户安全</p>
                        <p class="mt-2"><i class="fa fa-check-circle text-green-500 mr-1"></i> 您的账户已通过身份验证</p>
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
            <p>© {{ datetime.now().year }} Hello World 系统 | 版本 1.0.0</p>
        </div>
    </footer>
</body>
</html>
''', username=username, login_type=login_type, user_info=user_info, login_history=login_history, datetime=datetime, timezone=timezone, format_datetime_with_timezone=format_datetime_with_timezone, request=request)

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

