import requests
import time
import re

print("开始测试企业微信登录功能...")

# 1. 测试生成测试模式登录页面
print("\n1. 测试生成测试模式登录页面...")
response = requests.get('http://localhost:5000/wechat_corp_login?mode=test')
print(f"状态码: {response.status_code}")

if response.status_code == 200:
    # 2. 提取回调URL
    match = re.search(r'href=["\'](/wechat_callback[^\"\']+)', response.text)
    if match:
        callback_url = match.group(1)
        # 修复URL编码问题
        callback_url = callback_url.replace('&amp;', '&')
        print(f"\n2. 成功提取回调URL (修复后): {callback_url}")
        
        # 3. 立即测试回调功能
        print("\n3. 测试回调功能...")
        full_callback_url = f'http://localhost:5000{callback_url}'
        callback_response = requests.get(full_callback_url, allow_redirects=False)
        print(f"回调状态码: {callback_response.status_code}")
        print(f"响应头: {callback_response.headers}")
        
        # 4. 检查是否重定向到首页
        if callback_response.status_code == 302:
            location = callback_response.headers.get('Location', '')
            print(f"\n4. 回调重定向到: {location}")
            if location == '/':
                print("✓ 企业微信测试模式登录成功！")
            else:
                print(f"! 回调重定向到了非首页地址: {location}")
        else:
            print(f"! 回调未返回302重定向，返回内容: {callback_response.text[:200]}...")
    else:
        print("! 无法从页面中提取回调URL")
        print("页面内容预览:", response.text[:300])
else:
    print(f"! 生成登录页面失败: {response.text}")

print("\n测试完成！")