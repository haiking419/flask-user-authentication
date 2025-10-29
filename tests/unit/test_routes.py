import unittest
import json
import os
import sys
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

class TestRoutes(unittest.TestCase):
    
    def setUp(self):
        # 创建测试客户端
        self.client = app.test_client()
        # 设置测试环境
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # 禁用CSRF保护以便测试
        
    def tearDown(self):
        # 清理测试会话
        pass
    
    def test_index_redirects_to_login(self):
        """测试未登录用户访问首页重定向到登录页"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
    
    def test_index_authenticated(self):
        """测试已登录用户访问首页"""
        with self.client.session_transaction() as session:
            session['username'] = 'testuser'
            session['login_type'] = 'default'
        
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('欢迎，testuser'.encode('utf-8'), response.data)
    
    def test_login_get(self):
        """测试登录页面GET请求"""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn('登录'.encode('utf-8'), response.data)
        self.assertIn('企业微信登录'.encode('utf-8'), response.data)
    
    @patch('app.routes.auth.get_users')
    def test_login_post_success(self, mock_get_users):
        """测试登录成功的情况"""
        # 模拟用户数据
        import hashlib
        mock_get_users.return_value = {
            'testuser': {
                'password': hashlib.sha256('password123'.encode()).hexdigest(),
                'login_type': 'default'
            }
        }
        
        # 发送登录请求
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'password123'
        })
        
        # 验证重定向到首页
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')
        
        # 验证会话被设置
        with self.client.session_transaction() as session:
            self.assertEqual(session['username'], 'testuser')
            self.assertEqual(session['login_type'], 'default')
    
    @patch('app.routes.auth.get_users')
    def test_login_post_failure(self, mock_get_users):
        """测试登录失败的情况"""
        # 模拟用户数据
        mock_get_users.return_value = {'testuser': {'password': 'wronghash', 'login_type': 'default'}}
        
        # 发送错误的登录请求
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        })
        
        # 验证页面返回错误信息
        self.assertEqual(response.status_code, 200)
        self.assertIn('用户名或密码错误'.encode('utf-8'), response.data)
    
    def test_register_get(self):
        """测试注册页面GET请求"""
        response = self.client.get('/register')
        self.assertEqual(response.status_code, 200)
        self.assertIn('注册'.encode('utf-8'), response.data)
        self.assertIn('发送验证码'.encode('utf-8'), response.data)
    
    @patch('app.routes.auth.get_users')
    @patch('app.routes.auth.verify_code')
    @patch('app.routes.auth.save_users')
    def test_register_post_success(self, mock_save_users, mock_verify_code, mock_get_users):
        """测试注册成功的情况"""
        # 模拟用户不存在
        mock_get_users.return_value = {}
        # 模拟验证码验证成功
        mock_verify_code.return_value = True
        
        # 发送注册请求
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'verification_code': '123456',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        # 验证重定向到首页
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')
        
        # 验证保存用户被调用
        mock_save_users.assert_called_once()
        
        # 验证会话被设置
        with self.client.session_transaction() as session:
            self.assertEqual(session['username'], 'newuser')
            self.assertEqual(session['login_type'], 'default')
    
    @patch('app.routes.auth.get_users')
    def test_register_post_existing_username(self, mock_get_users):
        """测试注册时用户名已存在的情况"""
        # 模拟用户名已存在
        mock_get_users.return_value = {'existinguser': {}}
        
        # 发送注册请求
        response = self.client.post('/register', data={
            'username': 'existinguser',
            'email': 'newuser@example.com',
            'verification_code': '123456',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        # 验证页面返回错误信息
        self.assertEqual(response.status_code, 200)
        self.assertIn('用户名已存在'.encode('utf-8'), response.data)
    
    @patch('app.routes.auth.verify_code')
    @patch('app.routes.auth.get_users')
    def test_register_post_password_mismatch(self, mock_get_users, mock_verify_code):
        """测试注册时密码不匹配的情况"""
        # 模拟用户不存在
        mock_get_users.return_value = {}
        # 模拟验证码验证通过（这样才能到达密码验证逻辑）
        mock_verify_code.return_value = True
        
        # 发送密码不匹配的注册请求
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'verification_code': '123456',
            'password': 'password123',
            'confirm_password': 'differentpassword'
        })
        
        # 验证页面返回正确的错误信息
        self.assertEqual(response.status_code, 200)
        self.assertIn('两次输入的密码不一致'.encode('utf-8'), response.data)
    
    @patch('app.routes.auth.get_users')
    @patch('app.routes.auth.verify_code')
    def test_register_post_invalid_code(self, mock_verify_code, mock_get_users):
        """测试注册时验证码无效的情况"""
        # 模拟用户不存在
        mock_get_users.return_value = {}
        # 模拟验证码验证失败
        mock_verify_code.return_value = False
        
        # 发送验证码无效的注册请求
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'newuser@example.com',
            'verification_code': 'invalid',
            'password': 'password123',
            'confirm_password': 'password123'
        })
        
        # 验证页面返回错误信息
        self.assertEqual(response.status_code, 200)
        self.assertIn('验证码无效或已过期'.encode('utf-8'), response.data)
    
    @patch('app.routes.auth.get_users')
    @patch('app.routes.auth.get_verifications')
    @patch('app.routes.auth.save_verifications')
    @patch('app.routes.auth.generate_verification_code')
    @patch('app.routes.auth.send_email')
    def test_send_verification_success(self, mock_send_email, mock_generate_code, 
                                      mock_save_verifications, mock_get_verifications, 
                                      mock_get_users):
        """测试发送验证码成功的情况"""
        # 模拟用户不存在
        mock_get_users.return_value = {}
        # 模拟验证码数据
        mock_get_verifications.return_value = {}
        # 模拟生成验证码
        mock_generate_code.return_value = '123456'
        # 模拟发送邮件成功
        mock_send_email.return_value = True
        
        # 发送请求
        response = self.client.post('/send_verification', data={
            'email': 'test@example.com'
        })
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], '验证码已发送')
        
        # 验证保存验证码被调用
        mock_save_verifications.assert_called_once()
    
    @patch('app.routes.auth.get_users')
    def test_send_verification_invalid_email(self, mock_get_users):
        """测试发送验证码时邮箱格式不正确的情况"""
        # 模拟用户数据
        mock_get_users.return_value = {}
        
        # 发送无效邮箱
        response = self.client.post('/send_verification', data={
            'email': 'invalid-email'
        })
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], '邮箱格式不正确')
    
    @patch('app.routes.auth.get_users')
    def test_send_verification_existing_email(self, mock_get_users):
        """测试发送验证码时邮箱已被注册的情况"""
        # 模拟邮箱已存在
        mock_get_users.return_value = {
            'user1': {'email': 'existing@example.com'}
        }
        
        # 发送已注册邮箱
        response = self.client.post('/send_verification', data={
            'email': 'existing@example.com'
        })
        
        # 验证响应
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], '该邮箱已被注册')
    
    @patch('app.routes.auth.get_wechat_sessions')
    @patch('app.routes.auth.save_wechat_sessions')
    @patch('app.routes.auth.get_users')
    @patch('app.routes.auth.save_users')
    def test_wechat_callback(self, mock_save_users, mock_get_users, 
                            mock_save_wechat_sessions, mock_get_wechat_sessions):
        """测试微信回调处理"""
        # 模拟微信会话
        mock_get_wechat_sessions.return_value = {'valid_state': {'timestamp': 123456789}}
        # 模拟用户不存在
        mock_get_users.return_value = {}
        
        # 发送回调请求
        response = self.client.get('/wechat_callback?code=test_code&state=valid_state')
        
        # 验证重定向到首页
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, '/')
        
        # 验证保存用户被调用
        mock_save_users.assert_called_once()
        
        # 验证删除会话被调用
        mock_save_wechat_sessions.assert_called_once()
    
    @patch('app.routes.auth.get_wechat_sessions')
    def test_wechat_callback_invalid_state(self, mock_get_wechat_sessions):
        """测试微信回调处理时state无效的情况"""
        # 模拟微信会话中没有对应的state
        mock_get_wechat_sessions.return_value = {}
        
        # 发送无效state的回调请求
        response = self.client.get('/wechat_callback?code=test_code&state=invalid_state')
        
        # 验证返回错误信息
        self.assertEqual(response.status_code, 200)
        self.assertIn('无效的请求参数'.encode('utf-8'), response.data)
    
    def test_logout(self):
        """测试退出登录"""
        # 先设置会话
        with self.client.session_transaction() as session:
            session['username'] = 'testuser'
            session['login_type'] = 'default'
        
        # 发送退出登录请求
        response = self.client.get('/logout')
        
        # 验证重定向到登录页
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
        
        # 验证会话被清除
        with self.client.session_transaction() as session:
            self.assertNotIn('username', session)
            self.assertNotIn('login_type', session)

if __name__ == '__main__':
    unittest.main()
