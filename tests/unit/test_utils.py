import unittest
import time
import json
import os
import sys
import io
from unittest.mock import patch, MagicMock

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils import generate_verification_code, generate_wechat_state, send_email, verify_code, generate_captcha, PIL_AVAILABLE

class TestUtils(unittest.TestCase):
    
    def test_generate_verification_code(self):
        """测试验证码生成功能"""
        # 生成验证码
        code = generate_verification_code()
        
        # 验证验证码格式
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        
        # 验证多次生成的验证码不同（概率测试）
        codes = set()
        for _ in range(100):
            codes.add(generate_verification_code())
        self.assertGreater(len(codes), 90)  # 期望至少90个不同的验证码
    
    def test_generate_wechat_state(self):
        """测试微信登录状态码生成功能"""
        # 生成状态码
        state = generate_wechat_state()
        
        # 验证状态码格式
        self.assertEqual(len(state), 32)
        
        # 验证字符集
        valid_chars = set('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
        self.assertTrue(all(c in valid_chars for c in state))
        
        # 验证多次生成的状态码不同（概率测试）
        states = set()
        for _ in range(100):
            states.add(generate_wechat_state())
        self.assertGreater(len(states), 90)  # 期望至少90个不同的状态码
    
    @patch('builtins.print')
    def test_send_email(self, mock_print):
        """测试邮件发送功能"""
        # 测试模拟发送邮件
        result = send_email('test@example.com', '测试主题', '测试内容')
        
        # 验证结果
        self.assertTrue(result)
        mock_print.assert_any_call("开发环境：模拟发送邮件到 test@example.com")
        mock_print.assert_any_call("主题：测试主题")
        mock_print.assert_any_call("内容：测试内容")
    
    @patch('app.models.get_verifications')
    @patch('app.models.save_verifications')
    def test_verify_code_success(self, mock_save_verifications, mock_get_verifications):
        """测试验证码验证成功的情况"""
        # 模拟验证码数据 - 使用1分钟前的时间戳，确保在有效期内
        current_time = time.time()
        mock_verifications = {
            'test@example.com': {
                'code': '123456',
                'timestamp': current_time - 60  # 1分钟前生成，在有效期内
            }
        }
        mock_get_verifications.return_value = mock_verifications
        
        # 验证正确的验证码
        with patch('time.time', return_value=current_time):
            result = verify_code('test@example.com', '123456')
            
            # 验证结果和函数调用
            self.assertTrue(result)
            mock_save_verifications.assert_called_once_with({})
    
    @patch('app.models.get_verifications')
    def test_verify_code_wrong_code(self, mock_get_verifications):
        """测试验证码错误的情况"""
        # 模拟验证码数据
        mock_verifications = {
            'test@example.com': {
                'code': '123456',
                'timestamp': time.time()  # 使用当前时间作为时间戳
            }
        }
        mock_get_verifications.return_value = mock_verifications
        
        # 验证错误的验证码
        result = verify_code('test@example.com', '654321')
        
        # 验证结果
        self.assertFalse(result)
    
    @patch('app.models.get_verifications')
    @patch('app.models.save_verifications')
    def test_verify_code_expired(self, mock_save_verifications, mock_get_verifications):
        """测试验证码过期的情况"""
        # 模拟验证码数据 - 使用11分钟前的时间戳，确保已过期
        current_time = time.time()
        mock_verifications = {
            'test@example.com': {
                'code': '123456',
                'timestamp': current_time - 660  # 11分钟前生成，已过期
            }
        }
        mock_get_verifications.return_value = mock_verifications
        
        # 验证过期的验证码
        with patch('time.time', return_value=current_time):
            # 避免调试逻辑影响测试结果，我们需要确保过期时间设置正确
            result = verify_code('test@example.com', '123456')
            
            # 验证结果
            self.assertFalse(result)
            # 验证验证码被删除
            mock_save_verifications.assert_called()
    
    @patch('app.models.get_verifications')
    def test_verify_code_not_found(self, mock_get_verifications):
        """测试验证码不存在的情况"""
        # 模拟空的验证码数据
        mock_get_verifications.return_value = {}
        
        # 验证不存在的邮箱
        result = verify_code('nonexistent@example.com', '123456')
        
        # 验证结果
        self.assertFalse(result)
    
    def test_generate_captcha(self):
        """测试图形验证码生成功能"""
        # 生成验证码
        code, image = generate_captcha()
        
        # 验证验证码长度
        self.assertEqual(len(code), 4)
        
        # 验证验证码字符集（只包含指定的字符）
        valid_chars = set('ABCDEFGHJKLMNPQRSTUVWXYZ23456789')
        self.assertTrue(all(c in valid_chars for c in code))
        
        # 验证多次生成的验证码不同（概率测试）
        codes = set()
        for _ in range(100):
            codes.add(generate_captcha()[0])
        self.assertGreater(len(codes), 90)  # 期望至少90个不同的验证码
    
    def test_generate_captcha_image_type(self):
        """测试图形验证码图片类型"""
        # 生成验证码
        code, image = generate_captcha()
        
        # 如果PIL可用，验证图片是BytesIO对象
        if PIL_AVAILABLE:
            self.assertIsInstance(image, io.BytesIO)
            # 验证图片不为空
            image.seek(0)
            image_data = image.read()
            self.assertGreater(len(image_data), 0)
        else:
            # 如果PIL不可用，图片应为None
            self.assertIsNone(image)
    
    @patch('app.utils.PIL_AVAILABLE', False)
    def test_generate_captcha_without_pil(self):
        """测试在没有PIL库的情况下生成验证码"""
        # 生成验证码
        code, image = generate_captcha()
        
        # 验证验证码长度和类型
        self.assertEqual(len(code), 6)  # 在没有PIL时使用generate_verification_code，长度为6
        self.assertTrue(code.isdigit())
        # 验证图片为None
        self.assertIsNone(image)

if __name__ == '__main__':
    unittest.main()
