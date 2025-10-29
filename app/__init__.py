from flask import Flask
import os
import logging
from config import config_by_name, MySQLConfig
from flask_cors import CORS

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 尝试加载环境变量文件
try:
    from dotenv import load_dotenv
    # 根据环境变量加载对应的环境配置文件
    config_name = os.environ.get('APP_ENV', 'development')
    if config_name == 'production':
        load_dotenv('.env.production')
    else:
        load_dotenv('.env.development', override=True)
    logger.info(f"成功加载环境变量文件: .env.{config_name}")
except ImportError:
    logger.warning("python-dotenv未安装，将不加载环境变量文件")
except Exception as e:
    logger.error(f"加载环境变量文件失败: {e}")

# 获取环境配置，默认为development
config_name = os.environ.get('APP_ENV', 'development')
logger.info(f"应用环境: {config_name}")

# 确保使用MySQL配置
if config_name not in config_by_name:
    config = MySQLConfig()
else:
    config = config_by_name[config_name]

# 初始化Flask应用
app = Flask(__name__)
app.config.from_object(config)

# 初始化配置管理器
from app.utils.config_manager import init_config_manager, get_config_manager
init_config_manager(app.config)
config_manager = get_config_manager()

# 验证配置
if not config_manager.validate_all():
    errors = config_manager.get_validation_errors()
    for key, error in errors.items():
        logger.error(f"配置错误 - {key}: {error}")

# 初始化数据库
from app.models.db import db, migrate_from_json, cleanup_expired_data
db.init_app(app)

# 从配置管理器获取常量
MAIL_SERVER = config_manager.get('MAIL_SERVER')
MAIL_PORT = config_manager.get('MAIL_PORT')
MAIL_USERNAME = config_manager.get('MAIL_USERNAME')
MAIL_PASSWORD = config_manager.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = config_manager.get('MAIL_DEFAULT_SENDER')

WECHAT_CORP_ID = config_manager.get('WECHAT_CORP_ID')
WECHAT_AGENT_ID = config_manager.get('WECHAT_AGENT_ID')
WECHAT_APP_SECRET = config_manager.get('WECHAT_APP_SECRET')
WECHAT_REDIRECT_URI = config_manager.get('WECHAT_REDIRECT_URI')

# 不再需要数据文件路径，所有数据都存储在MySQL中

# 数据库初始化
try:
    with app.app_context():
        # 创建数据库表
        db.create_all()
        
        # 执行数据迁移（无论环境，因为migrate_from_json函数中有容错处理）
        try:
            migrate_from_json()
        except Exception as e:
            print(f"数据迁移过程中的异常: {e}")
        
        # 清理过期数据
        try:
            cleanup_expired_data()
        except Exception as e:
            print(f"清理过期数据时的异常: {e}")
except Exception as e:
    print(f"数据库连接失败: {e}")
    print("应用将继续运行，但数据库功能可能受限。")


# 从其他模块导入路由
from app.routes import auth
from app.routes.api import api

# 配置CORS支持
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 注册蓝图
app.register_blueprint(auth.bp)
app.register_blueprint(api)
