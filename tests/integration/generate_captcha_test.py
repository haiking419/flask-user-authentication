from app import app
from app.utils import generate_captcha

with app.app_context():
    # 生成验证码
    captcha_text, captcha_image = generate_captcha()
    print(f"生成的验证码: {captcha_text}")
    print("请使用此验证码进行登录测试")