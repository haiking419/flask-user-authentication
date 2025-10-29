from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

# 创建数据库实例
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Verification(db.Model):
    __tablename__ = 'verification'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True, unique=True)
    code = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WechatSession(db.Model):
    __tablename__ = 'wechat_session'
    
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(128), nullable=False, index=True, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LoginLog(db.Model):
    __tablename__ = 'login_log'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    login_type = db.Column(db.String(20), nullable=False, default='default')
    success = db.Column(db.Boolean, nullable=False)
    error_message = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

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
    now = datetime.utcnow()
    
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