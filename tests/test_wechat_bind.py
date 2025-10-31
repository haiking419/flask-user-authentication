import unittest
from unittest.mock import patch, MagicMock
from flask import session, request

from app import create_app
from app.models import User

class WechatBindTestCase(unittest.TestCase):
    """企业微信绑定功能测试"""
    
    def setUp(self):
        """设置测试环境"""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
    def tearDown(self):
        """清理测试环境"""
        self.app_context.pop()
    
    @patch('app.routes.auth.db.session')
    @patch('app.routes.auth.User')
    def test_handle_wechat_bind_success(self, mock_user, mock_db_session):
        """测试handle_wechat_bind函数成功处理绑定请求"""
        # 模拟用户对象
        mock_user_obj = MagicMock()
        mock_user_obj.username = 'test_user'
        mock_user_obj.id = 1
        mock_user.query.filter_by.return_value.first.return_value = mock_user_obj
        
        # 创建一个测试请求上下文
        with self.client as c:
            with c.session_transaction() as sess:
                sess['username'] = 'test_user'
            
            # 模拟微信用户信息
            wechat_user_info = {
                'userid': 'wechat_test_user',
                'name': '测试用户',
                'avatar': 'http://example.com/avatar.jpg'
            }
            
            # 导入handle_wechat_bind函数并调用
            from app.routes.auth import handle_wechat_bind
            result = handle_wechat_bind(wechat_user_info)
            
            # 验证结果
            self.assertFalse(result['success'])
            self.assertTrue(result['need_confirm'])
            self.assertEqual(result['wechat_user_info'], wechat_user_info)
            self.assertEqual(result['user_display_name'], 'test_user')
    
    @patch('app.routes.auth.db.session')
    @patch('app.routes.auth.User')
    def test_confirm_wechat_bind(self, mock_user, mock_db_session):
        """测试confirm_wechat_bind函数确认绑定"""
        # 模拟用户对象
        mock_user_obj = MagicMock()
        mock_user_obj.username = 'test_user'
        mock_user_obj.wechat_corp_userid = None
        mock_user.query.filter_by.return_value.first.return_value = mock_user_obj
        
        # 创建一个测试请求上下文
        with self.client as c:
            with c.session_transaction() as sess:
                sess['username'] = 'test_user'
                sess['wechat_bind_temp_info'] = {
                    'userid': 'wechat_test_user',
                    'name': '测试用户',
                    'avatar': 'http://example.com/avatar.jpg'
                }
                sess['user_display_name'] = '测试用户显示名'
            
            # 调用确认绑定路由
            response = c.get('/auth/confirm_wechat_bind')
            
            # 验证结果
            self.assertEqual(response.status_code, 302)  # 应该重定向
            self.assertTrue(mock_user_obj.wechat_corp_userid, 'wechat_test_user')
            mock_db_session.commit.assert_called_once()
    
    @patch('app.routes.auth.db.session')
    def test_confirm_wechat_bind_no_session(self, mock_db_session):
        """测试未登录状态下确认绑定"""
        with self.client as c:
            # 不设置会话信息
            response = c.get('/auth/confirm_wechat_bind', follow_redirects=True)
            
            # 验证结果
            self.assertEqual(response.status_code, 200)  # 重定向到登录页面
            mock_db_session.commit.assert_not_called()
    
    @patch('app.routes.auth.db.session')
    def test_confirm_wechat_bind_no_temp_info(self, mock_db_session):
        """测试临时信息不存在时确认绑定"""
        with self.client as c:
            with c.session_transaction() as sess:
                sess['username'] = 'test_user'
                # 不设置临时微信信息
            
            response = c.get('/auth/confirm_wechat_bind', follow_redirects=True)
            
            # 验证结果
            self.assertEqual(response.status_code, 200)  # 重定向到用户中心
            mock_db_session.commit.assert_not_called()

if __name__ == '__main__':
    unittest.main()