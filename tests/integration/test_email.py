import requests

# 测试发送验证码
def test_send_verification():
    print("开始测试发送验证码...")
    
    # 准备表单数据
    data = {'email': 'test@example.com'}
    
    try:
        # 发送POST请求
        response = requests.post('http://127.0.0.1:5000/send_verification', data=data)
        
        # 打印响应状态和内容
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        # 尝试解析JSON响应
        try:
            json_response = response.json()
            print(f"JSON响应: {json_response}")
        except:
            print("响应不是有效的JSON格式")
            
        print("测试完成")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")

if __name__ == "__main__":
    test_send_verification()