"""临时调试配置文件"""

# 从主配置导入所有设置
from app.config import *

# 设置调试模式
DEBUG = True

# 设置日志级别为DEBUG，以便查看所有调试信息
LOG_LEVEL = 'DEBUG'
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s'

# 确保不会缓存静态文件
SEND_FILE_MAX_AGE_DEFAULT = 0

# 为了更好地捕获异常，开启异常详细显示
PROPAGATE_EXCEPTIONS = True

# 会话超时设置（秒）
PERMANENT_SESSION_LIFETIME = 3600
