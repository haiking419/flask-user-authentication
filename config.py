import os
from datetime import timedelta
import secrets

class Config:
    """应用配置类"""
    
    # Flask配置
    SECRET_KEY = secrets.token_hex(16)
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # 数据库配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'data', 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 确保数据目录存在
    if not os.path.exists(os.path.join(BASE_DIR, 'data')):
        os.makedirs(os.path.join(BASE_DIR, 'data'))
    
    # 邮件服务器配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.example.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'noreply@example.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'password'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or MAIL_USERNAME
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    
    # 微信企业号配置
    WECHAT_CORP_ID = os.environ.get('WECHAT_CORP_ID') or 'wx1234567890abcdef'
    WECHAT_AGENT_ID = os.environ.get('WECHAT_AGENT_ID') or '1000001'
    WECHAT_APP_SECRET = os.environ.get('WECHAT_APP_SECRET') or 'abcdef1234567890abcdef1234567890'
    WECHAT_REDIRECT_URI = os.environ.get('WECHAT_REDIRECT_URI') or 'http://localhost:5000/wechat_callback'
    
    # 不再需要数据文件路径，所有数据都存储在MySQL中
    
    # 验证码配置
    VERIFICATION_CODE_LENGTH = 6
    VERIFICATION_CODE_EXPIRE = 600  # 10分钟
    
    # 应用配置
    DEBUG = os.environ.get('DEBUG') == 'True'
    APP_ENV = os.environ.get('APP_ENV', 'development')  # development, production
    # 确保默认使用开发环境以避免SECRET_KEY错误

# MySQL配置
class MySQLConfig(Config):
    # 使用MySQL数据库（使用URL编码的密码）
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://helloworld_user:Helloworld%40123@172.18.0.1:33060/helloworld_db?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 连接池配置
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_MAX_OVERFLOW = 20
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 1800

# 开发环境配置
class DevelopmentConfig(MySQLConfig):
    DEBUG = True
    APP_ENV = 'development'

# 生产环境配置
class ProductionConfig(MySQLConfig):
    DEBUG = False
    APP_ENV = 'production'
    
    # 生产环境建议使用更强的密钥
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # 从环境变量覆盖数据库配置
    if os.environ.get('DATABASE_URL'):
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL').replace('postgres://', 'postgresql://')
    
    def __init__(self):
        # 确保必要的环境变量已设置
        if not self.SECRET_KEY:
            raise ValueError("Production environment requires SECRET_KEY to be set")

# 测试环境配置
class TestingConfig(MySQLConfig):
    DEBUG = False
    TESTING = True
    APP_ENV = 'testing'
    
    # 测试环境也使用MySQL数据库
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://helloworld_user:Helloworld@123@192.168.7.7:32770/helloworld_db?charset=utf8mb4'

# 根据环境变量选择配置
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}