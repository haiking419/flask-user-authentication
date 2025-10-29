import unittest
import json
import os
import sys
from unittest.mock import patch, mock_open, MagicMock

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入要测试的函数
from app.models import get_users, save_users, get_verifications, save_verifications, get_wechat_sessions, save_wechat_sessions

class TestModels(unittest.TestCase):
    
    @patch('app.models.USERS_FILE', 'test_users.json')
    def test_get_users_file_exists(self):
        """测试当用户文件存在时获取用户数据"""
        # 模拟文件内容
        test_users = {"user1": {"username": "testuser", "password": "hashedpass"}}
        
        # 使用mock_open模拟文件读取
        with patch('builtins.open', mock_open(read_data=json.dumps(test_users))):
            with patch('os.path.exists', return_value=True):
                users = get_users()
                
                # 验证返回的数据
                self.assertEqual(users, test_users)
    
    @patch('app.models.USERS_FILE', 'test_users.json')
    def test_get_users_file_not_exists(self):
        """测试当用户文件不存在时获取用户数据"""
        # 模拟文件不存在
        with patch('os.path.exists', return_value=False):
            users = get_users()
            
            # 验证返回空字典
            self.assertEqual(users, {})
    
    @patch('app.models.USERS_FILE', 'test_users.json')
    def test_get_users_file_error(self):
        """测试当用户文件读取错误时获取用户数据"""
        # 模拟文件存在但读取错误
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open()) as mock_file:
                # 使json.load抛出异常
                mock_file.return_value.__enter__.side_effect = json.JSONDecodeError("Expecting property name", "doc", 0)
                users = get_users()
                
                # 验证返回空字典
                self.assertEqual(users, {})
    
    @patch('app.models.USERS_FILE', 'test_users.json')
    def test_save_users(self):
        """测试保存用户数据"""
        # 测试数据
        test_users = {"user1": {"username": "testuser", "password": "hashedpass"}}
        
        # 使用mock_open模拟文件写入
        m = mock_open()
        with patch('builtins.open', m):
            save_users(test_users)
            
            # 验证文件被打开，但不检查具体的文件名和写入次数
            m.assert_called_once()
    
    @patch('app.models.VERIFICATIONS_FILE', 'test_verifications.json')
    def test_get_verifications(self):
        """测试获取验证码数据"""
        # 模拟文件内容
        test_verifications = {"user@example.com": {"code": "123456", "timestamp": 123456789}}
        
        # 使用mock_open模拟文件读取
        with patch('builtins.open', mock_open(read_data=json.dumps(test_verifications))):
            with patch('os.path.exists', return_value=True):
                verifications = get_verifications()
                
                # 验证返回的数据
                self.assertEqual(verifications, test_verifications)
    
    @patch('app.models.VERIFICATIONS_FILE', 'test_verifications.json')
    def test_save_verifications(self):
        """测试保存验证码数据"""
        # 测试数据
        test_verifications = {"user@example.com": {"code": "123456", "timestamp": 123456789}}
        
        # 使用mock_open模拟文件写入
        m = mock_open()
        with patch('builtins.open', m):
            save_verifications(test_verifications)
            
            # 验证文件被打开，但不检查具体的文件名和写入次数
            m.assert_called_once()
    
    @patch('app.models.WECHAT_SESSIONS_FILE', 'test_wechat_sessions.json')
    def test_get_wechat_sessions(self):
        """测试获取微信会话数据"""
        # 模拟文件内容
        test_sessions = {"state123": {"openid": "openid123", "user_info": {"name": "测试用户"}}}
        
        # 使用mock_open模拟文件读取
        with patch('builtins.open', mock_open(read_data=json.dumps(test_sessions))):
            with patch('os.path.exists', return_value=True):
                sessions = get_wechat_sessions()
                
                # 验证返回的数据
                self.assertEqual(sessions, test_sessions)
    
    @patch('app.models.WECHAT_SESSIONS_FILE', 'test_wechat_sessions.json')
    def test_save_wechat_sessions(self):
        """测试保存微信会话数据"""
        # 测试数据
        test_sessions = {"state123": {"openid": "openid123", "user_info": {"name": "测试用户"}}}
        
        # 使用mock_open模拟文件写入
        m = mock_open()
        with patch('builtins.open', m):
            save_wechat_sessions(test_sessions)
            
            # 验证文件被打开，但不检查具体的文件名和写入次数
            m.assert_called_once()

if __name__ == '__main__':
    unittest.main()
