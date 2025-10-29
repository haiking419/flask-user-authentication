import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入各个测试模块
from tests.unit.test_utils import TestUtils
from tests.unit.test_models import TestModels
from tests.unit.test_routes import TestRoutes

def create_test_suite():
    """创建测试套件"""
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    # 添加各个测试类
    test_suite.addTest(loader.loadTestsFromTestCase(TestUtils))
    test_suite.addTest(loader.loadTestsFromTestCase(TestModels))
    test_suite.addTest(loader.loadTestsFromTestCase(TestRoutes))
    
    return test_suite

def run_tests():
    """运行所有测试"""
    test_suite = create_test_suite()
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # 返回测试结果
    return result.wasSuccessful()

if __name__ == '__main__':
    print("=== Hello World 应用测试套件 ===")
    print("运行所有测试...")
    
    success = run_tests()
    
    if success:
        print("\n所有测试通过！")
        sys.exit(0)
    else:
        print("\n测试失败！")
        sys.exit(1)
