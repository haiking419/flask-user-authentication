"""配置管理器模块"""
import os
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigManager:
    """统一的配置管理器，提供配置获取和验证功能"""
    
    def __init__(self, config_obj: Any = None):
        """初始化配置管理器
        
        Args:
            config_obj: Flask配置对象
        """
        self.config_obj = config_obj
        self._cached_config: Dict[str, Any] = {}
        self._validation_errors: Dict[str, str] = {}
        
    def get(self, key: str, default: Any = None, validate: bool = False) -> Any:
        """获取配置值
        
        优先级：
        1. 环境变量
        2. Flask配置对象
        3. 默认值
        
        Args:
            key: 配置键名
            default: 默认值
            validate: 是否验证配置
            
        Returns:
            配置值
        """
        # 先检查缓存
        cache_key = f"{key}_{default}"
        if cache_key in self._cached_config:
            return self._cached_config[cache_key]
        
        # 从环境变量获取
        value = os.environ.get(key)
        
        # 如果环境变量不存在，尝试从Flask配置对象获取
        if value is None and self.config_obj:
            value = getattr(self.config_obj, key, default)
        elif value is None:
            value = default
        
        # 进行配置验证
        if validate:
            self._validate_config(key, value)
        
        # 缓存配置值
        self._cached_config[cache_key] = value
        return value
    
    def _validate_config(self, key: str, value: Any) -> None:
        """验证配置有效性
        
        Args:
            key: 配置键名
            value: 配置值
        """
        # 验证必要的配置项
        required_configs = [
            'SECRET_KEY', 
            'WECHAT_CORP_ID', 
            'WECHAT_AGENT_ID', 
            'WECHAT_APP_SECRET', 
            'WECHAT_REDIRECT_URI'
        ]
        
        if key in required_configs and not value:
            error_msg = f"必要配置项 {key} 未设置"
            self._validation_errors[key] = error_msg
            logger.error(error_msg)
        
        # 验证特定格式的配置项
        if key == 'WECHAT_CORP_ID' and value and not (len(value) >= 18 and len(value) <= 20):
            error_msg = f"企业微信CORP_ID格式不正确: {value}"
            self._validation_errors[key] = error_msg
            logger.warning(error_msg)
        
        if key == 'WECHAT_AGENT_ID' and value and not str(value).isdigit():
            error_msg = f"企业微信AGENT_ID必须是数字: {value}"
            self._validation_errors[key] = error_msg
            logger.warning(error_msg)
    
    def validate_all(self) -> bool:
        """验证所有必要配置项
        
        Returns:
            是否所有配置都有效
        """
        required_configs = [
            'SECRET_KEY', 
            'WECHAT_CORP_ID', 
            'WECHAT_AGENT_ID', 
            'WECHAT_APP_SECRET', 
            'WECHAT_REDIRECT_URI'
        ]
        
        for config_key in required_configs:
            self.get(config_key, validate=True)
        
        return len(self._validation_errors) == 0
    
    def get_validation_errors(self) -> Dict[str, str]:
        """获取配置验证错误
        
        Returns:
            错误信息字典
        """
        return self._validation_errors.copy()
    
    def get_app_env(self) -> str:
        """获取当前应用环境
        
        Returns:
            环境名称 (development/production/testing)
        """
        env = self.get('APP_ENV', 'development').lower()
        if env not in ['development', 'production', 'testing']:
            logger.warning(f"无效的APP_ENV值: {env}，使用默认值 development")
            return 'development'
        return env
    
    def is_production(self) -> bool:
        """是否为生产环境
        
        Returns:
            是否为生产环境
        """
        return self.get_app_env() == 'production'
    
    def is_development(self) -> bool:
        """是否为开发环境
        
        Returns:
            是否为开发环境
        """
        return self.get_app_env() == 'development'
    
    def is_testing(self) -> bool:
        """是否为测试环境
        
        Returns:
            是否为测试环境
        """
        return self.get_app_env() == 'testing'


# 创建全局配置管理器实例
config_manager = ConfigManager()


def get_config_manager() -> ConfigManager:
    """获取配置管理器实例
    
    Returns:
        配置管理器实例
    """
    global config_manager
    return config_manager


def init_config_manager(config_obj: Any) -> None:
    """初始化配置管理器
    
    Args:
        config_obj: Flask配置对象
    """
    global config_manager
    config_manager = ConfigManager(config_obj)
    # 验证所有配置
    config_manager.validate_all()
