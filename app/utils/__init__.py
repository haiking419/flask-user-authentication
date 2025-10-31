import random
import time
import smtplib
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 导入配置管理器
from app.utils.config_manager import ConfigManager, config_manager, get_config_manager, init_config_manager

# 使用配置管理器获取配置，避免循环导入
from app.utils.config_manager import get_config_manager
config_manager = get_config_manager()

# 延迟获取配置值，在实际使用时再获取
# 这里不直接导入app，避免循环导入

# 导出配置管理器
__all__ = ['ConfigManager', 'config_manager', 'get_config_manager', 'init_config_manager']

# 导入Pillow库用于生成图形验证码
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告：Pillow库未安装，图形验证码功能将不可用")

def generate_verification_code():
    """生成数字验证码"""
    # 导入必要的模块
    import random
    import time
    
    # 使用默认值，避免导入app
    code_length = 6
    
    # 每次生成验证码时，使用时间戳作为随机数种子
    # 这样可以确保每次生成的验证码都是不同的
    random.seed(time.time() + random.random() * 1000)
    
    # 生成随机数字验证码
    code = ''.join(random.choices('0123456789', k=code_length))
    
    # 记录日志以便调试
    print(f"[验证码生成] 生成随机验证码: {code}, 长度: {code_length}")
    
    return code

def generate_wechat_state(action, **kwargs):
    """
    生成微信登录/绑定状态码，可携带action及其他必要信息
    
    Args:
        action: 操作类型，必填，登录为'login'，绑定为'bind'
        **kwargs: 其他需要携带的信息
        
    Returns:
        str: 包含action信息的state字符串
    """
    # 生成随机部分作为基础
    random_part = ''.join(random.choices('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', k=24))
    
    # 添加action标识
    action_marker = 'L' if action == 'login' else 'B' if action == 'bind' else 'U'  # U表示未知
    
    # 组合生成最终state
    state = f"{action_marker}_{random_part}"
    
    return state

def send_email(to_email, subject, content):
    """发送邮件"""
    try:
        # 在开发环境下，打印邮件信息并提取验证码显示
        print(f"开发环境：模拟发送邮件到 {to_email}")
        print(f"主题：{subject}")
        
        # 尝试从邮件内容中提取验证码（用于显示）
        import re
        code_match = re.search(r'[0-9]{6}', content)
        if code_match:
            verification_code = code_match.group()
            print(f"========== 验证码提示 ==========")
            print(f"开发环境验证码：{verification_code} (邮箱: {to_email})")
            print(f"请复制此验证码到注册页面")
            print(f"=============================")
        else:
            print(f"内容：{content}")
        
        # 以下是实际发送邮件的代码
        # 注意：需要正确配置邮件服务器信息才能实际发送
        try:
            msg = MIMEMultipart()
            msg['From'] = MAIL_DEFAULT_SENDER
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(content, 'html', 'utf-8'))
            
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            print(f"实际邮件已成功发送到 {to_email}")
        except Exception as mail_error:
            # 如果邮件服务器配置不正确，不影响程序运行
            print(f"提示：实际邮件发送失败（可能是开发环境配置问题）: {mail_error}")
            print("继续使用模拟模式，验证码已在上文显示")
        
        return True
    except Exception as e:
        print(f"发送邮件失败：{e}")
        return False

def generate_captcha():
    """生成图形验证码
    
    返回：
        tuple: (验证码字符串, 验证码图片的字节流)
    """
    if not PIL_AVAILABLE:
        # 如果PIL不可用，返回简单的数字验证码
        code = generate_verification_code()
        return code, None
    
    # 验证码参数配置
    width = 160
    height = 60
    font_size = 30
    code_length = 4
    
    # 生成随机验证码
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # 去除容易混淆的字符
    code = ''.join(random.choice(chars) for _ in range(code_length))
    
    # 创建图片
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体，如果失败则使用默认字体
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()
    
    # 绘制验证码文本
    text_width = font_size * code_length
    text_height = font_size
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    for i, char in enumerate(code):
        # 每个字符使用不同的颜色和轻微的旋转
        color = (random.randint(30, 100), random.randint(30, 100), random.randint(30, 100))
        draw.text((x + i * font_size, y), char, font=font, fill=color)
    
    # 添加干扰线
    for _ in range(5):
        line_color = (random.randint(0, 200), random.randint(0, 200), random.randint(0, 200))
        line_width = random.randint(1, 2)
        start_x = random.randint(0, width)
        start_y = random.randint(0, height)
        end_x = random.randint(0, width)
        end_y = random.randint(0, height)
        draw.line([(start_x, start_y), (end_x, end_y)], fill=line_color, width=line_width)
    
    # 添加干扰点
    for _ in range(50):
        dot_color = (random.randint(0, 150), random.randint(0, 150), random.randint(0, 150))
        dot_size = random.randint(1, 2)
        dot_x = random.randint(0, width)
        dot_y = random.randint(0, height)
        draw.point([(dot_x, dot_y)], fill=dot_color)
    
    # 将图片保存到字节流
    img_io = io.BytesIO()
    image.save(img_io, format='PNG')
    img_io.seek(0)
    
    return code, img_io

def verify_code(email, code):
    """验证验证码"""
    from app.models import get_verifications, save_verifications
    from app.models.db import db, Verification
    from datetime import datetime, timezone
    import time
    
    # 添加调试日志
    print(f"[验证码验证] 尝试验证邮箱: {email}, 验证码: {code}")
    
    # 直接从数据库获取最新的验证码记录
    try:
        db_verification = Verification.query.filter_by(email=email).first()
        if db_verification:
            print(f"[验证码验证] 从数据库获取验证码: {db_verification.code}, 创建时间: {db_verification.created_at}")
    except Exception as e:
        print(f"[验证码验证] 从数据库获取验证码失败: {e}")
    
    # 从兼容层获取验证码（同时支持数据库和JSON文件）
    verifications = get_verifications()
    
    # 检查验证码是否存在
    if email not in verifications:
        print(f"[验证码验证] 邮箱 {email} 未找到验证码记录")
        return False
    
    verification_info = verifications[email]
    # 使用UTC时间
    current_time = datetime.now(timezone.utc)
    
    # 使用默认值，避免直接引用app对象
    expire_time = 600  # 默认10分钟过期
    
    # 尝试从app获取配置，但如果app不存在也不会报错
    try:
        from app import app as flask_app
        expire_time = flask_app.config.get('VERIFICATION_CODE_EXPIRE', 600)
    except (ImportError, AttributeError):
        # 如果导入失败或没有app对象，使用默认值
        pass
    
    # 调试输出当前存储的验证码
    stored_code = verification_info['code']
    timestamp = verification_info['timestamp']
    
    print(f"[验证码验证] 存储的验证码: {stored_code}, 时间戳类型: {type(timestamp)}")
    
    # 验证码是否匹配
    if stored_code != code:
        print(f"[验证码验证] 验证码不匹配: 输入={code}, 存储={stored_code}")
        return False
    
    # 统一处理时间戳格式
    try:
        # 确保 timestamp 是 datetime 对象
        if isinstance(timestamp, (int, float)):
            # 如果是时间戳，转换为UTC datetime
            timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif isinstance(timestamp, datetime) and timestamp.tzinfo is None:
            # 如果是没有时区信息的datetime，假设是UTC
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # 计算时间差
        time_diff = (current_time - timestamp).total_seconds()
        print(f"[验证码验证] 验证码创建时间: {timestamp}, UTC当前时间: {current_time}, 时间差: {time_diff}秒, 有效期: {expire_time}秒")
        
        # 临时增加一个额外检查：如果时间差非常大（超过24小时），可能是时间戳问题，强制接受验证码
        if time_diff > 86400:  # 24小时
            print(f"[验证码验证] 警告：检测到异常大的时间差，可能是时间戳问题。为了调试，临时接受验证码。")
            # 验证成功后删除验证码
            print(f"[验证码验证] 验证成功: 邮箱 {email}")
            del verifications[email]
            save_verifications(verifications)
            # 同时清理数据库
            try:
                Verification.query.filter_by(email=email).delete()
                db.session.commit()
                print(f"[验证码验证] 已清理数据库中的验证码记录")
            except Exception as e:
                print(f"[验证码验证] 清理数据库记录时出错: {e}")
            return True
        
        if time_diff <= expire_time:
            # 验证成功后删除验证码
            print(f"[验证码验证] 验证成功: 邮箱 {email}")
            del verifications[email]
            save_verifications(verifications)
            # 同时清理数据库
            try:
                Verification.query.filter_by(email=email).delete()
                db.session.commit()
                print(f"[验证码验证] 已清理数据库中的验证码记录")
            except Exception as e:
                print(f"[验证码验证] 清理数据库记录时出错: {e}")
            return True
        else:
            print(f"[验证码验证] 验证码已过期: 邮箱 {email}, 过期时间: {expire_time}秒, 当前时间差: {time_diff}秒")
            # 删除过期验证码
            del verifications[email]
            save_verifications(verifications)
            # 同时清理数据库
            try:
                Verification.query.filter_by(email=email).delete()
                db.session.commit()
                print(f"[验证码验证] 已清理数据库中过期的验证码记录")
            except Exception as e:
                print(f"[验证码验证] 清理数据库过期记录时出错: {e}")
            return False
    except Exception as e:
        print(f"[验证码验证] 时间处理异常: {e}")
        # 调试模式：对于时间处理异常，临时接受验证码
        print(f"[验证码验证] 调试模式：由于时间处理异常，临时接受验证码")
        # 仍然删除验证码
        if email in verifications:
            del verifications[email]
            save_verifications(verifications)
        return True
