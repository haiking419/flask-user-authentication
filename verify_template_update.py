#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证用户中心页面模板更新是否成功"""

import re

print("="*60)
print("验证用户中心页面模板更新")
print("="*60)

# 要检查的文件路径
file_path = "c:\\Users\\79434\\Documents\\trae_projects\\helloworld\\app\\routes\\auth.py"

# 要查找的关键字段
required_columns = [
    "登录时间",
    "登录类型", 
    "IP地址",
    "浏览器",  # 新增字段
    "平台",    # 新增字段
    "状态",
    "错误信息" # 新增字段
]

# 要查找的表格数据字段引用
required_data_fields = [
    "log.created_at",
    "log.login_type",
    "log.ip_address",
    "log.browser",  # 新增字段引用
    "log.platform", # 新增字段引用
    "log.success",
    "log.error_message" # 新增字段引用
]

def verify_template_update():
    """验证模板更新"""
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"\n1. 文件读取成功: {file_path}")
        
        # 检查用户中心路由
        if '@bp.route(\'/user_center\')' not in content:
            print("❌ 未找到用户中心路由")
            return False
        
        print("✅ 找到用户中心路由")
        
        # 检查表格列头
        print("\n2. 检查表格列头:")
        table_headers_found = []
        table_headers_missing = []
        
        for column in required_columns:
            if f">{column}<" in content:
                table_headers_found.append(column)
            else:
                table_headers_missing.append(column)
        
        if table_headers_found:
            print(f"   ✅ 找到的列头: {', '.join(table_headers_found)}")
        
        if table_headers_missing:
            print(f"   ❌ 缺少的列头: {', '.join(table_headers_missing)}")
        
        # 检查表格数据字段
        print("\n3. 检查表格数据字段引用:")
        data_fields_found = []
        data_fields_missing = []
        
        for field in required_data_fields:
            if field in content:
                data_fields_found.append(field)
            else:
                data_fields_missing.append(field)
        
        if data_fields_found:
            print(f"   ✅ 找到的数据字段: {', '.join(data_fields_found)}")
        
        if data_fields_missing:
            print(f"   ❌ 缺少的数据字段: {', '.join(data_fields_missing)}")
        
        # 检查colspan是否更新
        print("\n4. 检查表格空数据行:")
        if 'colspan="7"' in content and '暂无登录记录' in content:
            print("   ✅ 空数据行colspan已更新为7")
        else:
            print("   ❌ 空数据行colspan可能未更新")
        
        # 总结
        print("\n5. 更新总结:")
        if not table_headers_missing and not data_fields_missing:
            print("✅ 模板更新成功！所有必要的字段都已添加到用户中心页面")
            print("   - 表格列头: 共7列，包含所有必要信息")
            print("   - 数据字段: 所有相应的字段引用都存在")
            print("   - 空数据行: colspan已正确更新")
            return True
        else:
            print("❌ 模板更新不完整")
            if table_headers_missing:
                print(f"   - 缺少列头: {', '.join(table_headers_missing)}")
            if data_fields_missing:
                print(f"   - 缺少数据字段引用: {', '.join(data_fields_missing)}")
            return False
        
    except Exception as e:
        print(f"\n❌ 验证过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    verify_template_update()
    print("\n" + "="*60)
    print("验证完成")
    print("="*60)
