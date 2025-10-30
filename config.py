import os
from datetime import timedelta
import secrets
from urllib.parse import quote_plus

class Config:
    """应用配置类"""
    
    # Flask配置
    SECRET_KEY = secrets.token_hex(16)
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # 数据库配置 - 默认使用MySQL
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # 从环境变量构建数据库URL - 优先使用环境变量，与.env.development文件保持一致
    DB_HOST = os.environ.get('DB_HOST', '172.18.0.1')
    DB_PORT = os.environ.get('DB_PORT', '33060')
    DB_USER = os.environ.get('DB_USER', 'helloworld_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Helloworld@123')
    DB_NAME = os.environ.get('DB_NAME', 'helloworld_db')
    DB_CHARSET = os.environ.get('DB_CHARSET', 'utf8mb4')
    
    # 构建MySQL连接URL
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset={DB_CHARSET}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 确保数据目录存在（用于日志等非数据库文件）
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

# MySQL配置 - 所有环境统一使用此类
class MySQLConfig(Config):
    # 从环境变量构建数据库URL - 优先使用环境变量，与.env.development文件保持一致
    DB_HOST = os.environ.get('DB_HOST', '172.18.0.1')
    DB_PORT = os.environ.get('DB_PORT', '33060')
    DB_USER = os.environ.get('DB_USER', 'helloworld_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Helloworld@123')
    DB_NAME = os.environ.get('DB_NAME', 'helloworld_db')
    DB_CHARSET = os.environ.get('DB_CHARSET', 'utf8mb4')
    
    # 构建MySQL连接URL
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset={DB_CHARSET}"
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
    
    # 保持对DATABASE_URL环境变量的兼容支持
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
    
    # 测试环境使用特定的MySQL配置
    DB_HOST = os.environ.get('TEST_DB_HOST', '192.168.7.7')
    DB_PORT = os.environ.get('TEST_DB_PORT', '32770')
    DB_USER = os.environ.get('TEST_DB_USER', 'helloworld_user')
    DB_PASSWORD = os.environ.get('TEST_DB_PASSWORD', 'Helloworld@123')
    DB_NAME = os.environ.get('TEST_DB_NAME', 'helloworld_db')
    DB_CHARSET = os.environ.get('DB_CHARSET', 'utf8mb4')
    
    # 重新构建测试环境的数据库URL
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset={DB_CHARSET}"

# 根据环境变量选择配置
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}