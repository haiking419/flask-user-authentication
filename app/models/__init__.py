import os
from .db import User, Verification, WechatSession, db

def get_users():
    """获取所有用户数据（仅使用MySQL数据库）"""
    try:
        users_dict = {}
        users = User.query.all()
        for user in users:
            users_dict[user.username] = {
                'password': user.password,
                'email': user.email,
                'created_at': user.created_at
            }
        return users_dict
    except Exception as e:
        print(f"从数据库获取用户失败: {e}")
        return {}

def save_users(users):
    """保存用户数据（仅使用MySQL数据库）"""
    try:
        for username, user_info in users.items():
            # 查找用户是否已存在
            user = User.query.filter_by(username=username).first()
            if not user:
                # 创建新用户
                user = User(
                    username=username,
                    password=user_info.get('password'),
                    email=user_info.get('email')
                )
                # 不设置created_at，使用模型的默认值
                db.session.add(user)
            else:
                # 更新现有用户
                user.password = user_info.get('password')
                user.email = user_info.get('email')
                # 不更新created_at，保留数据库中的值
        db.session.commit()
    except Exception as e:
        print(f"保存用户到数据库失败: {e}")
        db.session.rollback()

def get_verifications():
    """获取所有验证码数据（仅使用MySQL数据库）"""
    try:
        verifications_dict = {}
        verifications = Verification.query.all()
        for verification in verifications:
            verifications_dict[verification.email] = {
                'code': verification.code,
                'timestamp': verification.created_at
            }
        return verifications_dict
    except Exception as e:
        print(f"从数据库获取验证码失败: {e}")
        return {}

def save_verifications(verifications):
    """保存验证码数据（仅使用MySQL数据库）"""
    try:
        for email, verification_info in verifications.items():
            # 查找验证码是否已存在
            verification = Verification.query.filter_by(email=email).first()
            if verification:
                # 更新现有验证码
                verification.code = verification_info.get('code')
                # 更新created_at为当前时间
                from datetime import datetime
                verification.created_at = datetime.utcnow()
            else:
                # 创建新验证码
                verification = Verification(
                    email=email,
                    code=verification_info.get('code')
                )
                # 不设置created_at，使用模型的默认值
                db.session.add(verification)
        db.session.commit()
    except Exception as e:
        print(f"保存验证码到数据库失败: {e}")
        db.session.rollback()

def get_wechat_sessions():
    """获取微信会话数据（仅使用MySQL数据库）"""
    try:
        sessions_dict = {}
        sessions = WechatSession.query.all()
        for session in sessions:
            sessions_dict[session.state] = {
                'timestamp': session.created_at
            }
        return sessions_dict
    except Exception as e:
        print(f"从数据库获取微信会话失败: {e}")
        return {}

def save_wechat_sessions(sessions):
    """保存微信会话数据（仅使用MySQL数据库）"""
    try:
        for state, session_info in sessions.items():
            # 查找会话是否已存在
            session = WechatSession.query.filter_by(state=state).first()
            if not session:
                # 创建新会话
                session = WechatSession(
                    state=state
                )
                # 不设置created_at，使用模型的默认值
                db.session.add(session)
        db.session.commit()
    except Exception as e:
        print(f"保存微信会话到数据库失败: {e}")
        db.session.rollback()
