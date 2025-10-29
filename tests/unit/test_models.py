import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入要测试的函数和模块
from app.models import get_users, save_users, get_verifications, save_verifications, get_wechat_sessions, save_wechat_sessions
from app.models.db import User, Verification, WechatSession, db
from app import app

class TestModels(unittest.TestCase):
    
    def setUp(self):
        # 推送应用上下文
        self.app_context = app.app_context()
        self.app_context.push()
    
    def tearDown(self):
        # 清理应用上下文
        self.app_context.pop()
    
    def test_get_users(self):
        """测试从数据库获取用户数据"""
        # 创建模拟用户对象
        mock_user1 = MagicMock()
        mock_user1.username = 'user1'
        mock_user1.password = 'password1'
        mock_user1.email = 'user1@example.com'
        mock_user1.created_at = '2023-01-01 00:00:00'
        
        mock_user2 = MagicMock()
        mock_user2.username = 'user2'
        mock_user2.password = 'password2'
        mock_user2.email = 'user2@example.com'
        mock_user2.created_at = '2023-01-02 00:00:00'
        
        # 模拟User.query.all()返回模拟用户
        with patch('app.models.User.query') as mock_query:
            mock_query.all.return_value = [mock_user1, mock_user2]
            
            # 调用被测试函数
            users = get_users()
            
            # 验证返回的数据
            expected_users = {
                'user1': {
                    'password': 'password1',
                    'email': 'user1@example.com',
                    'created_at': '2023-01-01 00:00:00'
                },
                'user2': {
                    'password': 'password2',
                    'email': 'user2@example.com',
                    'created_at': '2023-01-02 00:00:00'
                }
            }
            self.assertEqual(users, expected_users)
    
    def test_get_users_empty(self):
        """测试当数据库中没有用户时获取用户数据"""
        # 模拟User.query.all()返回空列表
        with patch('app.models.User.query') as mock_query:
            mock_query.all.return_value = []
            
            # 调用被测试函数
            users = get_users()
            
            # 验证返回空字典
            self.assertEqual(users, {})
    
    def test_get_users_error(self):
        """测试当数据库查询出错时获取用户数据"""
        # 模拟User.query.all()抛出异常
        with patch('app.models.User.query') as mock_query:
            mock_query.all.side_effect = Exception('Database error')
            
            # 调用被测试函数
            users = get_users()
            
            # 验证返回空字典
            self.assertEqual(users, {})
    
    def test_save_users(self):
        """测试保存用户数据到数据库"""
        # 测试数据
        test_users = {
            'user1': {
                'password': 'password1',
                'email': 'user1@example.com'
            },
            'user2': {
                'password': 'password2',
                'email': 'user2@example.com'
            }
        }
        
        # 创建模拟用户（用于查找已存在的用户）
        mock_existing_user = MagicMock()
        
        # 模拟User.query.filter_by().first()
        with patch('app.models.db.User.query') as mock_query:
            # 第一个用户不存在，返回None
            mock_query.filter_by.return_value.first.side_effect = [None, mock_existing_user]
            
            # 模拟db.session.add, db.session.commit
            with patch.object(db.session, 'add') as mock_add, \
                 patch.object(db.session, 'commit') as mock_commit:
                
                # 调用被测试函数
                save_users(test_users)
                
                # 验证调用
                self.assertEqual(mock_add.call_count, 1)  # 只添加一个新用户
                mock_commit.assert_called_once()
    
    def test_get_verifications(self):
        """测试从数据库获取验证码数据"""
        # 创建模拟验证码对象
        mock_verification1 = MagicMock()
        mock_verification1.email = 'user1@example.com'
        mock_verification1.code = '123456'
        mock_verification1.created_at = 123456789
        
        mock_verification2 = MagicMock()
        mock_verification2.email = 'user2@example.com'
        mock_verification2.code = '654321'
        mock_verification2.created_at = 987654321
        
        # 模拟Verification.query.all()返回模拟验证码
        with patch('app.models.Verification.query') as mock_query:
            mock_query.all.return_value = [mock_verification1, mock_verification2]
            
            # 调用被测试函数
            verifications = get_verifications()
            
            # 验证返回的数据
            expected_verifications = {
                'user1@example.com': {
                    'code': '123456',
                    'timestamp': 123456789
                },
                'user2@example.com': {
                    'code': '654321',
                    'timestamp': 987654321
                }
            }
            self.assertEqual(verifications, expected_verifications)
    
    def test_save_verifications(self):
        """测试保存验证码数据到数据库"""
        # 测试数据
        test_verifications = {
            'user1@example.com': {
                'code': '123456',
                'timestamp': 123456789
            },
            'user2@example.com': {
                'code': '654321',
                'timestamp': 987654321
            }
        }
        
        # 创建模拟验证码（用于查找已存在的验证码）
        mock_existing_verification = MagicMock()
        
        # 模拟Verification.query.filter_by().first()
        with patch('app.models.db.Verification.query') as mock_query:
            # 第一个验证码不存在，返回None
            mock_query.filter_by.return_value.first.side_effect = [None, mock_existing_verification]
            
            # 模拟db.session.add, db.session.commit
            with patch.object(db.session, 'add') as mock_add, \
                 patch.object(db.session, 'commit') as mock_commit:
                
                # 调用被测试函数
                save_verifications(test_verifications)
                
                # 验证调用
                self.assertEqual(mock_add.call_count, 1)  # 只添加一个新验证码
                mock_commit.assert_called_once()
    
    def test_get_wechat_sessions(self):
        """测试从数据库获取微信会话数据"""
        # 创建模拟微信会话对象
        mock_session1 = MagicMock()
        mock_session1.state = 'state123'
        mock_session1.created_at = 123456789
        
        mock_session2 = MagicMock()
        mock_session2.state = 'state456'
        mock_session2.created_at = 987654321
        
        # 模拟WechatSession.query.all()返回模拟会话
        with patch('app.models.WechatSession.query') as mock_query:
            mock_query.all.return_value = [mock_session1, mock_session2]
            
            # 调用被测试函数
            sessions = get_wechat_sessions()
            
            # 验证返回的数据 - 注意：根据实际模型，只有state和created_at字段
            expected_sessions = {
                'state123': {
                    'timestamp': 123456789
                },
                'state456': {
                    'timestamp': 987654321
                }
            }
            self.assertEqual(sessions, expected_sessions)
    
    def test_save_wechat_sessions(self):
        """测试保存微信会话数据到数据库"""
        # 测试数据
        test_sessions = {
            'state123': {
                'openid': 'openid123',
                'user_info': '{"name": "测试用户1"}'
            },
            'state456': {
                'openid': 'openid456',
                'user_info': '{"name": "测试用户2"}'
            }
        }
        
        # 创建模拟微信会话（用于查找已存在的会话）
        mock_existing_session = MagicMock()
        
        # 模拟WechatSession.query.filter_by().first()
        with patch('app.models.db.WechatSession.query') as mock_query:
            # 第一个会话不存在，返回None
            mock_query.filter_by.return_value.first.side_effect = [None, mock_existing_session]
            
            # 模拟db.session.add, db.session.commit
            with patch.object(db.session, 'add') as mock_add, \
                 patch.object(db.session, 'commit') as mock_commit:
                
                # 调用被测试函数
                save_wechat_sessions(test_sessions)
                
                # 验证调用
                self.assertEqual(mock_add.call_count, 2)  # 添加两个会话
                mock_commit.assert_called_once()

if __name__ == '__main__':
    unittest.main()
