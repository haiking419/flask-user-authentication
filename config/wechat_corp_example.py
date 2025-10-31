# 企业微信配置示例文件
# 请将此文件复制为 wechat_corp.py 并填入实际配置

class WechatCorpConfig:
    """企业微信配置类"""
    
    # 企业ID，从企业微信管理后台获取
    CORPID = 'your_corpid_here'
    
    # 应用的Secret，从企业微信管理后台获取
    CORPSECRET = 'your_corpsecret_here'
    
    # 应用ID，从企业微信管理后台获取
    AGENTID = 'your_agentid_here'
    
    # 企业微信扫码登录成功后的回调地址
    # 注意：此地址必须在企业微信管理后台中配置为可信域名
    CALLBACK_URL = 'http://yourdomain.com/auth/wechat_callback'
    
    # 企业微信授权登录URL
    AUTHORIZE_URL = 'https://open.weixin.qq.com/connect/oauth2/snsapi_base'
    
    # 企业微信获取access_token的URL
    ACCESS_TOKEN_URL = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
    
    # 企业微信获取用户信息的URL
    USER_INFO_URL = 'https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo'
    
    # 企业微信获取用户详情的URL
    USER_DETAIL_URL = 'https://qyapi.weixin.qq.com/cgi-bin/user/get'
    
    # 企业微信二维码登录URL
    QRCODE_LOGIN_URL = 'https://open.work.weixin.qq.com/wwopen/sso/qrConnect'
    
    # 会话中临时存储微信绑定信息的键名
    SESSION_WECHAT_BIND_TEMP_INFO = 'wechat_bind_temp_info'
    
    # 会话中存储用户显示名的键名
    SESSION_USER_DISPLAY_NAME = 'user_display_name'
    
    # 会话中存储微信操作类型的键名（login/bind）
    SESSION_WECHAT_OPERATION_TYPE = 'wechat_operation_type'
    
    # 会话中存储状态的键名
    SESSION_WECHAT_STATE = 'wechat_state'
    
    # 会话中存储创建时间的键名
    SESSION_WECHAT_STATE_CREATED_AT = 'wechat_state_created_at'
    
    # 会话中存储绑定状态的键名
    SESSION_WECHAT_BIND_NEED_CONFIRM = 'wechat_bind_need_confirm'
    
    # state过期时间（秒）
    STATE_EXPIRE_SECONDS = 300
    
    # 是否开启测试模式
    TEST_MODE = False
    
    # 测试模式下模拟的用户信息
    TEST_USER_INFO = {
        'userid': 'test_wechat_user',
        'name': '测试用户',
        'avatar': 'https://example.com/test_avatar.jpg'
    }
    
    # 日志记录级别
    LOG_LEVEL = 'INFO'
    
    # 是否记录详细的操作日志
    ENABLE_DETAILED_LOGGING = True

# 从环境变量加载配置的优先级高于硬编码配置
# 如果使用环境变量，取消下面注释并删除上面的硬编码配置
# import os
# CORPID = os.environ.get('WECHAT_CORP_ID', '')
# CORPSECRET = os.environ.get('WECHAT_CORP_SECRET', '')
# AGENTID = os.environ.get('WECHAT_AGENT_ID', '')
# CALLBACK_URL = os.environ.get('WECHAT_CALLBACK_URL', '')