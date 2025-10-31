from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone
import os

# 创建数据库实例
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)  # 系统用户ID，作为用户的唯一标识
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)  # 登录账号，用于账号密码登录
    display_name = db.Column(db.String(100), nullable=True)  # 系统用户名，作为页面展示的用户昵称，可随时修改
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    # 企业微信相关字段，用于微信扫码登录时关联用户
    wechat_corp_userid = db.Column(db.String(120), unique=True, nullable=True, index=True)  # 微信用户ID
    wechat_corp_name = db.Column(db.String(120), nullable=True)  # 微信用户名
    wechat_corp_avatar = db.Column(db.String(500), nullable=True)  # 企业微信头像URL
    wechat_corp_binded_at = db.Column(db.DateTime, nullable=True)  # 企业微信绑定时间
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def before_update(self):
        """在更新前自动设置updated_at字段"""
        self.updated_at = datetime.now(timezone.utc)

class Verification(db.Model):
    __tablename__ = 'verification'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True, unique=True)
    code = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class WechatSession(db.Model):
    __tablename__ = 'wechat_session'
    
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(128), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class LoginLog(db.Model):
    __tablename__ = 'login_log'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)  # 用户唯一ID
    username = db.Column(db.String(80), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    browser = db.Column(db.String(200), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    platform = db.Column(db.String(100), nullable=True)
    # 注意：密码只在开发调试阶段记录，生产环境必须移除或置空
    password_hash_debug = db.Column(db.String(200), nullable=True)
    login_type = db.Column(db.String(20), nullable=False, default='default')
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.String(200), nullable=True)
    request_params = db.Column(db.Text, nullable=True)
    response_time = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

# 数据库操作辅助函数
def get_db():
    """获取数据库会话"""
    return db

def commit_db():
    """提交数据库更改"""
    try:
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"数据库提交失败: {e}")
        return False

def init_db(app):
    """初始化MySQL数据库"""
    db.init_app(app)
    
    # 在应用上下文中创建所有表
    with app.app_context():
        db.create_all()
        print(f"数据库表已在 {app.config['SQLALCHEMY_DATABASE_URI']} 创建")

# 清理过期数据的函数（保留用于数据库维护）
def cleanup_expired_data():
    """清理过期的数据"""
    now = datetime.now(timezone.utc)
    
    # 清理过期的验证码（超过10分钟）
    expired_verifications = Verification.query.filter(
        Verification.created_at < (now - timedelta(minutes=10))
    ).all()
    
    for verification in expired_verifications:
        db.session.delete(verification)
    
    db.session.commit()
    print(f"清理了 {len(expired_verifications)} 条过期验证码")
    
    # 清理过期的微信会话（超过5分钟）
    expired_sessions = WechatSession.query.filter(
        WechatSession.created_at < (now - timedelta(minutes=5))
    ).all()
    
    for session in expired_sessions:
        db.session.delete(session)
    
    db.session.commit()
    print(f"清理了 {len(expired_sessions)} 条过期微信会话")