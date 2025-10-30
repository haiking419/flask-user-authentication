import os
from .db import User, Verification, WechatSession, LoginLog, db

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
    """获取所有企业微信登录会话"""
    try:
        sessions_dict = {}
        # 获取所有会话，包括过期的用于调试
        sessions = WechatSession.query.all()
        for session in sessions:
            # 初始化会话数据字典，确保返回的timestamp是时间戳格式
            if isinstance(session.created_at, datetime):
                timestamp = session.created_at.timestamp()
            else:
                timestamp = session.created_at
            
            session_data = {
                'timestamp': timestamp
            }
            # 如果有其他字段，可以在这里添加
            sessions_dict[session.state] = session_data
        
        # 清理过期会话（超过1小时）
        try:
            import time
            current_time = time.time()
            expired_states = []
            for state, data in sessions_dict.items():
                # 确保比较时间戳类型的一致性
                session_timestamp = data.get('timestamp', 0)
                # 转换为浮点数时间戳
                if isinstance(session_timestamp, datetime):
                    session_timestamp = session_timestamp.timestamp()
                
                # 比较是否超过过期时间
                if current_time - float(session_timestamp) > 3600:
                    expired_states.append(state)
            
            if expired_states:
                # 删除过期会话
                WechatSession.query.filter(WechatSession.state.in_(expired_states)).delete(synchronize_session=False)
                db.session.commit()
                print(f"成功清理 {len(expired_states)} 个过期微信会话")
                # 从返回结果中移除
                for state in expired_states:
                    if state in sessions_dict:
                        del sessions_dict[state]
        except Exception as e:
            print(f"清理过期微信会话失败: {e}")
        
        return sessions_dict
    except Exception as e:
        print(f"从数据库获取微信会话失败: {e}")
        return {}

def save_wechat_sessions(sessions):
    """保存企业微信登录会话"""
    try:
        # 使用事务确保数据一致性
        try:
            # 对于需要更新的会话，先删除旧记录
            existing_states = [state for state, _ in sessions.items()]
            if existing_states:
                WechatSession.query.filter(WechatSession.state.in_(existing_states)).delete(synchronize_session=False)
            
            # 创建新会话
            for state, session_info in sessions.items():
                try:
                    # 创建会话对象
                    session = WechatSession(
                        state=state
                    )
                    
                    # 如果会话信息中包含timestamp，且需要使用它作为created_at
                    if 'timestamp' in session_info:
                        try:
                            # 转换时间戳为datetime对象
                            if isinstance(session_info['timestamp'], (int, float)):
                                from datetime import datetime
                                session.created_at = datetime.fromtimestamp(session_info['timestamp'])
                        except (ValueError, TypeError) as e:
                            print(f"转换时间戳失败 - state: {state}, 错误: {e}")
                            # 继续使用默认的created_at
                    
                    db.session.add(session)
                except Exception as e:
                    print(f"保存微信会话项失败 - state: {state}, 错误: {e}")
            
            # 提交事务
            db.session.commit()
            print(f"成功保存 {len(sessions)} 个微信会话")
        except Exception as e:
            print(f"保存微信会话事务失败: {e}")
            db.session.rollback()
    except Exception as e:
        print(f"保存微信会话到数据库失败: {e}")
        db.session.rollback()

def clean_wechat_sessions(session_states):
    """清理指定的微信会话"""
    if not session_states:
        return True
    
    try:
        # 使用参数化查询删除指定会话
        WechatSession.query.filter(WechatSession.state.in_(session_states)).delete(synchronize_session=False)
        db.session.commit()
        print(f"成功清理 {len(session_states)} 个微信会话")
        return True
    except Exception as e:
        print(f"清理微信会话失败: {e}")
        db.session.rollback()
        return False
