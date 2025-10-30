# API路由模块
from flask import Blueprint, request, jsonify, session, current_app
from app.models.db import User, Verification, db
from app.models import get_wechat_sessions, save_wechat_sessions
import uuid
from urllib.parse import quote
import time
import random
import re
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.utils.config_manager import get_config_manager
config_manager = get_config_manager()

api = Blueprint('api', __name__, url_prefix='/api')

# 验证码生成函数
def generate_verification_code():
    return ''.join(random.choices('0123456789', k=6))

# 发送邮件函数
def send_email(recipient, subject, content):
    try:
        smtp_config = config_manager.get_smtp_config()
        
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = smtp_config['sender']
        msg['To'] = recipient
        msg['Subject'] = subject
        
        # 添加邮件正文
        msg.attach(MIMEText(content, 'html', 'utf-8'))
        
        # 连接SMTP服务器并发送邮件
        with smtplib.SMTP(smtp_config['server'], smtp_config['port']) as server:
            if smtp_config.get('use_ssl', False):
                server.starttls()
            if smtp_config.get('username') and smtp_config.get('password'):
                server.login(smtp_config['username'], smtp_config['password'])
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"发送邮件失败: {str(e)}")
        return False

# 清理过期验证码
def clean_expired_verifications():
    try:
        # 删除10分钟前的验证码
        expired_time = datetime.now() - timedelta(minutes=10)
        Verification.delete().where(Verification.created_at < expired_time).execute()
    except Exception as e:
        print(f"清理过期验证码失败: {str(e)}")

# 发送验证码路由
@api.route('/send_verification', methods=['POST'])
def send_verification():
    try:
        data = request.get_json()
        email = data.get('email', '')
        
        # 验证邮箱格式
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'success': False, 'message': '请输入有效的邮箱地址'})
        
        # 检查邮箱是否已注册
        existing_user = User.select().where(User.email == email).first()
        if existing_user:
            return jsonify({'success': False, 'message': '该邮箱已被注册'})
        
        # 清理过期验证码
        clean_expired_verifications()
        
        # 生成验证码
        code = generate_verification_code()
        
        # 保存验证码到数据库
        Verification.create(
            email=email,
            code=code,
            created_at=datetime.now()
        )
        
        # 发送邮件（在开发环境下可以不实际发送）
        if config_manager.get_app_config('debug', False):
            print(f"开发环境验证码: {code} (发送至: {email})")
            return jsonify({'success': True, 'message': '验证码已发送（开发环境）'})
        else:
            # 实际发送邮件
            subject = '您的验证码'
            content = f"""
            <html>
            <body>
                <p>尊敬的用户，</p>
                <p>您的验证码是：<strong style='font-size: 18px; color: #1890ff;'>{code}</strong></p>
                <p>验证码有效期为10分钟，请及时使用。</p>
                <p>如非本人操作，请忽略此邮件。</p>
            </body>
            </html>
            """
            
            if send_email(email, subject, content):
                return jsonify({'success': True, 'message': '验证码已发送，请查收邮箱'})
            else:
                return jsonify({'success': False, 'message': '发送验证码失败，请稍后重试'})
                
    except Exception as e:
        print(f"发送验证码异常: {str(e)}")
        return jsonify({'success': False, 'message': '系统错误，请稍后重试'})

# 注册路由
@api.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username', '')
        email = data.get('email', '')
        verification_code = data.get('verification_code', '')
        password = data.get('password', '')
        
        # 验证输入
        if not all([username, email, verification_code, password]):
            return jsonify({'success': False, 'message': '请填写所有必填字段'})
        
        # 检查用户名
        if User.select().where(User.username == username).first():
            return jsonify({'success': False, 'message': '用户名已存在'})
        
        # 检查邮箱
        if User.select().where(User.email == email).first():
            return jsonify({'success': False, 'message': '邮箱已被注册'})
        
        # 验证验证码
        verification = Verification.select().where(
            (Verification.email == email) & 
            (Verification.code == verification_code)
        ).first()
        
        if not verification:
            return jsonify({'success': False, 'message': '验证码错误'})
        
        # 检查验证码是否过期
        if (datetime.now() - verification.created_at).total_seconds() > 600:  # 10分钟
            return jsonify({'success': False, 'message': '验证码已过期'})
        
        # 创建用户
        User.create(
            username=username,
            email=email,
            password=password,  # 注意：实际应用中应该加密存储密码
            created_at=datetime.now()
        )
        
        # 删除已使用的验证码
        verification.delete_instance()
        
        return jsonify({'success': True, 'message': '注册成功'})
        
    except Exception as e:
        print(f"注册异常: {str(e)}")
        return jsonify({'success': False, 'message': '注册失败，请稍后重试'})

# 登录路由
@api.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email', '')
        password = data.get('password', '')
        
        # 验证输入
        if not email or not password:
            return jsonify({'success': False, 'message': '请输入邮箱和密码'})
        
        # 查找用户
        user = User.select().where(User.email == email).first()
        
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'})
        
        # 验证密码（实际应用中应该使用加密验证）
        if user.password != password:
            return jsonify({'success': False, 'message': '密码错误'})
        
        # 设置会话
        session['user_id'] = user.id
        session['username'] = user.username
        session['email'] = user.email
        
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None
            }
        })
        
    except Exception as e:
        print(f"登录异常: {str(e)}")
        return jsonify({'success': False, 'message': '登录失败，请稍后重试'})

# 获取用户信息路由
@api.route('/user_info', methods=['GET'])
def get_user_info():
    try:
        # 检查用户是否登录
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': '未登录'}), 401
        
        # 获取用户信息
        user_id = session['user_id']
        user = User.select().where(User.id == user_id).first()
        
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat() if hasattr(user, 'created_at') else None
            }
        })
        
    except Exception as e:
        print(f"获取用户信息异常: {str(e)}")
        return jsonify({'success': False, 'message': '获取用户信息失败'}), 500

# 退出登录路由
@api.route('/logout', methods=['POST'])
def logout():
    try:
        # 清除会话
        session.clear()
        return jsonify({'success': True, 'message': '退出成功'})
    except Exception as e:
        print(f"退出登录异常: {str(e)}")
        return jsonify({'success': False, 'message': '退出失败'}), 500

# 获取微信登录二维码路由
@api.route('/wechat_qrcode', methods=['GET'])
def get_wechat_qrcode():
    try:
        print("\n===== 企业微信扫码登录流程 - 生成二维码开始 =====")
        
        # 从环境变量获取企业微信配置
        WECHAT_CORP_ID = current_app.config.get('WECHAT_CORP_ID')
        WECHAT_AGENT_ID = current_app.config.get('WECHAT_AGENT_ID')
        WECHAT_REDIRECT_URI = current_app.config.get('WECHAT_REDIRECT_URI')
        
        # 生成state参数
        state = str(uuid.uuid4())
        
        # 打印详细的配置参数和请求信息
        print("[DEBUG] 请求URL: GET /api/wechat_qrcode")
        print("[DEBUG] 请求参数: 无")
        print("[DEBUG] 企业微信配置参数:")
        print(f"[DEBUG] WECHAT_CORP_ID: {WECHAT_CORP_ID} (类型: {type(WECHAT_CORP_ID)})")
        print(f"[DEBUG] WECHAT_AGENT_ID: {WECHAT_AGENT_ID} (类型: {type(WECHAT_AGENT_ID)})")
        print(f"[DEBUG] WECHAT_REDIRECT_URI: {WECHAT_REDIRECT_URI}")
        print(f"[DEBUG] 生成的state: {state}")
        
        # 确保参数类型正确
        WECHAT_CORP_ID = str(WECHAT_CORP_ID)
        WECHAT_AGENT_ID = str(WECHAT_AGENT_ID)
        
        # 编码redirect_uri
        encoded_redirect_uri = quote(WECHAT_REDIRECT_URI)
        print(f"[DEBUG] 编码后的redirect_uri: {encoded_redirect_uri}")
        
        # 生成企业微信登录URL - 使用官方更新的格式，将corpid改为appid
        wechat_qrcode_url = f"https://open.work.weixin.qq.com/wwopen/sso/qrConnect?appid={WECHAT_CORP_ID}&agentid={WECHAT_AGENT_ID}&redirect_uri={encoded_redirect_uri}&state={state}"
        print(f"[DEBUG] 生成的企业微信登录URL: {wechat_qrcode_url}")
        print(f"[DEBUG] URL参数分解:")
        print(f"[DEBUG]   - 基础URL: https://open.work.weixin.qq.com/wwopen/sso/qrConnect")
        print(f"[DEBUG]   - appid: {WECHAT_CORP_ID}")
        print(f"[DEBUG]   - agentid: {WECHAT_AGENT_ID}")
        print(f"[DEBUG]   - redirect_uri: {encoded_redirect_uri}")
        print(f"[DEBUG]   - state: {state}")
        
        # 保存state到数据库中，供回调验证使用
        try:
            wechat_sessions = get_wechat_sessions()
            wechat_sessions[state] = {'timestamp': time.time()}
            save_wechat_sessions(wechat_sessions)
            print(f"[DEBUG] 成功保存state到数据库: {state}")
        except Exception as save_error:
            print(f"[DEBUG] 保存state到数据库失败: {str(save_error)}")
        
        response_data = {
            'success': True,
            'qrcode_url': wechat_qrcode_url,
            'state': state
        }
        print(f"[DEBUG] 返回数据: {response_data}")
        print("===== 企业微信扫码登录流程 - 生成二维码结束 =====\n")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"[ERROR] 获取微信二维码异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': '获取二维码失败'}), 500

# 检查微信登录状态路由
@api.route('/check_wechat_login/<session_key>', methods=['GET'])
def check_wechat_login(session_key):
    print("\n===== 企业微信扫码登录流程 - 检查登录状态开始 =====")
    print(f"[DEBUG] 请求URL: GET /api/check_wechat_login/{session_key}")
    print(f"[DEBUG] 请求参数: session_key={session_key}")
    
    try:
        # 获取微信会话数据
        wechat_sessions = get_wechat_sessions()
        print(f"[DEBUG] 当前微信会话数据: {wechat_sessions}")
        
        # 检查session_key是否存在
        if session_key not in wechat_sessions:
            print(f"[DEBUG] 会话不存在: {session_key}")
            response = {
                'success': True,
                'logged_in': False,
                'message': '等待扫码',
                'status': 'init'
            }
            print(f"[DEBUG] 返回数据: {response}")
            print("===== 企业微信扫码登录流程 - 检查登录状态结束 =====\n")
            return jsonify(response)
        
        # 获取会话信息
        session_info = wechat_sessions[session_key]
        current_time = time.time()
        session_time = session_info.get('timestamp', 0)
        
        # 计算时间信息
        elapsed_time = current_time - session_time
        remaining_time = 300 - elapsed_time  # 5分钟 = 300秒
        print(f"[DEBUG] 会话信息: {session_info}")
        print(f"[DEBUG] 会话创建时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session_time))}")
        print(f"[DEBUG] 当前时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}")
        print(f"[DEBUG] 已经过时间: {elapsed_time:.2f}秒")
        print(f"[DEBUG] 剩余有效期: {remaining_time:.2f}秒")
        
        # 检查会话是否过期（二维码有效期为5分钟）
        if current_time - session_time > 300:  # 5分钟有效期
            print(f"[DEBUG] 会话已过期: {session_key}")
            response = {
                'success': True,
                'logged_in': False,
                'message': '二维码已过期，请重新获取',
                'status': 'expired'
            }
            print(f"[DEBUG] 返回数据: {response}")
            print("===== 企业微信扫码登录流程 - 检查登录状态结束 =====\n")
            return jsonify(response)
        
        # 检查用户是否已扫码但未确认
        if session_info.get('scanned', False) and not session_info.get('confirmed', False):
            print(f"[DEBUG] 用户已扫码但未确认: {session_key}")
            response = {
                'success': True,
                'logged_in': False,
                'message': '请在手机上确认登录',
                'status': 'scanned'
            }
            print(f"[DEBUG] 返回数据: {response}")
            print("===== 企业微信扫码登录流程 - 检查登录状态结束 =====\n")
            return jsonify(response)
        
        # 检查用户是否已确认登录
        if session_info.get('confirmed', False):
            # 如果用户已确认登录，返回登录成功状态和用户信息
            user_info = session_info.get('user_info', {})
            print(f"[DEBUG] 用户已确认登录: {session_key}")
            response = {
                'success': True,
                'logged_in': True,
                'message': '登录成功',
                'status': 'confirmed',
                'user': user_info
            }
            print(f"[DEBUG] 返回数据: {response}")
            print("===== 企业微信扫码登录流程 - 检查登录状态结束 =====\n")
            return jsonify(response)
        
        # 默认状态：等待扫码
        print(f"[DEBUG] 等待用户扫码: {session_key}")
        response = {
            'success': True,
            'logged_in': False,
            'message': '等待扫码',
            'status': 'init'
        }
        print(f"[DEBUG] 返回数据: {response}")
        print("===== 企业微信扫码登录流程 - 检查登录状态结束 =====\n")
        return jsonify(response)
        
    except Exception as e:
        print(f"[ERROR] 检查微信登录状态异常: {str(e)}")
        import traceback
        traceback.print_exc()
        response = {'success': False, 'message': '检查登录状态失败'}
        print(f"[DEBUG] 返回数据: {response}")
        print("===== 企业微信扫码登录流程 - 检查登录状态结束 =====\n")
        return jsonify(response), 500

# 验证码图片生成（模拟）
@api.route('/captcha', methods=['GET'])
def generate_captcha():
    try:
        # 在实际应用中，这里应该生成一个真实的验证码图片
        # 这里为了演示，返回一个模拟的验证码
        captcha_code = generate_verification_code()
        
        # 保存验证码到session
        session['captcha'] = captcha_code
        session['captcha_time'] = time.time()
        
        # 返回验证码图片URL（模拟）
        return jsonify({
            'success': True,
            'captcha_url': f"/api/captcha_image?timestamp={int(time.time())}"
        })
        
    except Exception as e:
        print(f"生成验证码异常: {str(e)}")
        return jsonify({'success': False, 'message': '生成验证码失败'}), 500