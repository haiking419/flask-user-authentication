import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 打印路径以调试
print(f"Current directory: {os.getcwd()}")
print(f"Added to path: {os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))}")

from app import app
from app.models import LoginLog, db, User
from app.utils import generate_captcha
import time

# 主测试流程
def main():
    # 使用已知的admin用户进行测试，因为admin用户密码可能已经设置正确
    test_username = 'admin'
    test_password = 'admin'  # 假设admin密码为'admin'
    
    with app.app_context():
        # 检查数据库中的用户
        print("检查数据库中的用户...")
        
        # 获取所有用户
        users = User.query.all()
        print(f"数据库中的用户列表: {[user.username for user in users]}")
        
        # 检查admin用户是否存在
        admin_user = User.query.filter_by(username='admin').first()
        if admin_user:
            print(f"管理员用户 admin 存在，使用此用户进行测试")
        else:
            print("管理员用户不存在，将使用test_user进行测试")
            test_username = 'test_user'
    
    # 测试不同的登录场景
    test_login_scenarios(test_username, test_password)

# 测试多个登录场景
def test_login_scenarios(username, password):
    with app.test_client() as client:
        # 测试场景1: 错误的验证码
        print("\n===== 测试场景1: 错误的验证码 =====")
        test_login_with_invalid_captcha(client, username, password)
        
        # 测试场景2: 正确的验证码但密码错误
        print("\n===== 测试场景2: 正确的验证码但密码错误 =====")
        test_login_with_wrong_password(client, username, "wrong_password")
        
        # 测试场景3: 正确的验证码和密码
        print("\n===== 测试场景3: 正确的验证码和密码 =====")
        test_login_with_correct_credentials(client, username, password)
        
        # 测试场景4: 不存在的用户
        print("\n===== 测试场景4: 不存在的用户 =====")
        test_login_with_nonexistent_user(client, "nonexistent_user", "password")

# 测试错误的验证码
def test_login_with_invalid_captcha(client, username, password):
    # 生成正确的验证码但使用错误的验证码提交
    code, img_io = generate_captcha()
    captcha_upper = code.upper()
    invalid_captcha = "INVALID"
    
    # 设置正确的验证码到会话
    with client.session_transaction() as sess:
        sess['captcha'] = captcha_upper
        sess['captcha_timestamp'] = time.time()
    
    # 使用错误的验证码提交登录
    response = client.post('/login', data={
        'username': username,
        'password': password,
        'captcha': invalid_captcha
    }, follow_redirects=True)
    
    print(f"请求状态码: {response.status_code}")

# 测试正确的验证码但密码错误
def test_login_with_wrong_password(client, username, wrong_password):
    # 生成并设置正确的验证码
    code, img_io = generate_captcha()
    captcha_upper = code.upper()
    
    with client.session_transaction() as sess:
        sess['captcha'] = captcha_upper
        sess['captcha_timestamp'] = time.time()
    
    # 使用错误的密码提交登录
    response = client.post('/login', data={
        'username': username,
        'password': wrong_password,
        'captcha': captcha_upper
    }, follow_redirects=True)
    
    print(f"请求状态码: {response.status_code}")

# 测试正确的验证码和密码
def test_login_with_correct_credentials(client, username, password):
    # 生成并设置正确的验证码
    code, img_io = generate_captcha()
    captcha_upper = code.upper()
    
    with client.session_transaction() as sess:
        sess['captcha'] = captcha_upper
        sess['captcha_timestamp'] = time.time()
    
    # 使用正确的凭证提交登录
    response = client.post('/login', data={
        'username': username,
        'password': password,
        'captcha': captcha_upper
    }, follow_redirects=True)
    
    print(f"请求状态码: {response.status_code}")

# 测试不存在的用户
def test_login_with_nonexistent_user(client, nonexistent_username, password):
    # 生成并设置正确的验证码
    code, img_io = generate_captcha()
    captcha_upper = code.upper()
    
    with client.session_transaction() as sess:
        sess['captcha'] = captcha_upper
        sess['captcha_timestamp'] = time.time()
    
    # 使用不存在的用户名提交登录
    response = client.post('/login', data={
        'username': nonexistent_username,
        'password': password,
        'captcha': captcha_upper
    }, follow_redirects=True)
    
    print(f"请求状态码: {response.status_code}")
    
    # 检查登录日志
    print("\n最终检查: 所有测试后的登录日志")
    with app.app_context():
        # 查询最近的登录日志
        recent_logs = LoginLog.query.order_by(LoginLog.created_at.desc()).limit(8).all()
        
        print(f"最近{len(recent_logs)}条登录日志:")
        for log in recent_logs:
            status = "成功" if log.success else f"失败 - 错误: {log.error_message}"
            print(f"时间: {log.created_at}, 用户名: {log.username}, IP: {log.ip_address}, 状态: {status}")

if __name__ == '__main__':
    main()