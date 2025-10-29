from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import json

# 初始化SQLAlchemy，使用简化配置避免版本问题
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

# 用于迁移旧的JSON数据到数据库的函数
def migrate_from_json():
    """
    从JSON文件迁移数据到数据库
    """
    try:
        # 使用相对路径而不是导入，避免循环导入问题
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        DATA_DIR = os.path.join(BASE_DIR, 'data')
        
        # 迁移用户数据
        users_file = os.path.join(DATA_DIR, 'users.json')
        if os.path.exists(users_file):
            with open(users_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            # 根据数据格式进行不同处理
            if isinstance(users_data, list):
                # 列表格式: [{'username': 'user1', ...}, ...]
                for user_data in users_data:
                    try:
                        if isinstance(user_data, dict):
                            username = user_data.get('username')
                            password = user_data.get('password', '')
                            email = user_data.get('email')
                            
                            # 检查用户是否已存在
                            if username:
                                existing_user = User.query.filter_by(username=username).first()
                                if not existing_user:
                                    user = User(
                                        username=username,
                                        password=password,
                                        email=email
                                    )
                                    db.session.add(user)
                    except Exception as e:
                        print(f"处理用户数据时出错: {e}")
                
                db.session.commit()
                print(f"成功迁移 {len(users_data)} 个用户数据到数据库")
            elif isinstance(users_data, dict):
                # 字典格式: {'username1': {'password': 'pass1', 'email': 'email1'}, ...}
                for username, user_info in users_data.items():
                    try:
                        if isinstance(username, str):
                            if isinstance(user_info, dict):
                                password = user_info.get('password', '')
                                email = user_info.get('email')
                            else:
                                # 如果user_info不是字典，假设它是密码
                                password = str(user_info)
                                email = None
                            
                            # 检查用户是否已存在
                            existing_user = User.query.filter_by(username=username).first()
                            if not existing_user:
                                user = User(
                                    username=username,
                                    password=password,
                                    email=email
                                )
                                db.session.add(user)
                    except Exception as e:
                        print(f"处理用户数据时出错: {e}")
                
                db.session.commit()
                print(f"成功迁移 {len(users_data)} 个用户数据到数据库")
            else:
                print(f"用户数据格式不支持: {type(users_data)}")
    
        # 迁移验证码数据
        verifications_file = os.path.join(DATA_DIR, 'verifications.json')
        if os.path.exists(verifications_file):
            with open(verifications_file, 'r', encoding='utf-8') as f:
                verifications_data = json.load(f)
            
            # 确保是字典格式
            if isinstance(verifications_data, dict):
                for email, code_data in verifications_data.items():
                    try:
                        # 处理不同的数据格式
                        if isinstance(code_data, dict):
                            code = code_data.get('code', '')
                        elif isinstance(code_data, str):
                            code = code_data
                        else:
                            code = str(code_data)
                        
                        # 检查验证码是否已存在
                        existing_verification = Verification.query.filter_by(email=email).first()
                        if not existing_verification:
                            verification = Verification(
                                email=email,
                                code=code
                            )
                            db.session.add(verification)
                    except Exception as e:
                        print(f"处理验证码数据时出错: {e}")
                
                db.session.commit()
                print(f"成功迁移 {len(verifications_data)} 个验证码数据到数据库")
            else:
                print(f"验证码数据格式不支持: {type(verifications_data)}")
    
        # 迁移微信会话数据
        sessions_file = os.path.join(DATA_DIR, 'wechat_sessions.json')
        if os.path.exists(sessions_file):
            with open(sessions_file, 'r', encoding='utf-8') as f:
                sessions_data = json.load(f)
            
            # 处理不同的数据格式
            if isinstance(sessions_data, list):
                # 列表格式: ['state1', 'state2', ...]
                for state in sessions_data:
                    try:
                        if isinstance(state, str):
                            # 检查会话是否已存在
                            existing_session = WechatSession.query.filter_by(state=state).first()
                            if not existing_session:
                                session = WechatSession(state=state)
                                db.session.add(session)
                    except Exception as e:
                        print(f"处理微信会话数据时出错: {e}")
            elif isinstance(sessions_data, dict):
                # 字典格式: {'state1': {...}, 'state2': {...}}
                for state in sessions_data.keys():
                    try:
                        if isinstance(state, str):
                            # 检查会话是否已存在
                            existing_session = WechatSession.query.filter_by(state=state).first()
                            if not existing_session:
                                session = WechatSession(state=state)
                                db.session.add(session)
                    except Exception as e:
                        print(f"处理微信会话数据时出错: {e}")
            
            db.session.commit()
            print(f"成功迁移 {len(sessions_data)} 个微信会话数据到数据库")
    
    except Exception as e:
        print(f"数据迁移过程中出错: {e}")
        try:
            db.session.rollback()
        except:
            pass
        # 不抛出异常，允许应用继续运行

# 清理过期数据的函数
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