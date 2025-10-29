import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import app
from app.utils import generate_captcha

with app.app_context():
    # 生成验证码
    captcha_text, captcha_image = generate_captcha()
    print(f"生成的验证码: {captcha_text}")
    print("请使用此验证码进行登录测试")
    
    # 验证验证码长度和格式
    print(f"验证码长度: {len(captcha_text)}")
    valid_chars = set('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
    is_valid = all(c in valid_chars for c in captcha_text)
    print(f"验证码格式有效: {is_valid}")
    
    # 验证图片不为空
    if captcha_image:
        print("验证码图片生成成功")
        captcha_image.seek(0)
        image_size = len(captcha_image.read())
        print(f"验证码图片大小: {image_size} 字节")
    else:
        print("警告: 验证码图片生成失败，可能是PIL库未安装")