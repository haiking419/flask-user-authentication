#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复数据库表结构，调整字段长度和类型以匹配模型定义"""

import os
import sys
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

# 加载环境变量
load_dotenv('.env.development')

# 数据库配置
DB_USER = os.environ.get('DB_USER', 'helloworld_user')
DB_PASSWORD = quote_plus(os.environ.get('DB_PASSWORD', 'Helloworld@123'))
DB_HOST = os.environ.get('DB_HOST', '172.18.0.1')
DB_PORT = os.environ.get('DB_PORT', '33060')
DB_NAME = os.environ.get('DB_NAME', 'helloworld_db')

# 创建数据库连接
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

print("="*60)
print("修复数据库表结构开始")
print("="*60)

try:
    # 创建数据库引擎
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as connection:
        # 开始事务
        trans = connection.begin()
        
        try:
            # 1. 修复User表字段长度和类型
            print("\n1. 修复User表字段长度和类型...")
            
            # 修改username字段长度为80（与模型定义匹配）
            try:
                connection.execute(text("ALTER TABLE user MODIFY COLUMN username VARCHAR(80) NOT NULL"))
                print("   ✓ username字段长度修改为80成功")
            except Exception as e:
                print(f"   ℹ username字段修改失败: {str(e)}")
                
            # 修改password字段长度为200（与模型定义匹配）
            try:
                connection.execute(text("ALTER TABLE user MODIFY COLUMN password VARCHAR(200) NOT NULL"))
                print("   ✓ password字段长度修改为200成功")
            except Exception as e:
                print(f"   ℹ password字段修改失败: {str(e)}")
                
            # 修改email字段长度为120（与模型定义匹配）
            try:
                connection.execute(text("ALTER TABLE user MODIFY COLUMN email VARCHAR(120) NULL"))
                print("   ✓ email字段长度修改为120成功")
            except Exception as e:
                print(f"   ℹ email字段修改失败: {str(e)}")
                
            # 修改created_at字段类型为datetime（与模型定义匹配）
            try:
                # 先添加临时字段
                connection.execute(text("ALTER TABLE user ADD COLUMN created_at_temp DATETIME NULL"))
                # 复制数据
                connection.execute(text("UPDATE user SET created_at_temp = created_at"))
                # 删除原字段
                connection.execute(text("ALTER TABLE user DROP COLUMN created_at"))
                # 创建新字段
                connection.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                # 复制数据回新字段
                connection.execute(text("UPDATE user SET created_at = created_at_temp"))
                # 删除临时字段
                connection.execute(text("ALTER TABLE user DROP COLUMN created_at_temp"))
                print("   ✓ created_at字段类型修改为datetime成功")
            except Exception as e:
                print(f"   ℹ created_at字段修改失败: {str(e)}")
            
            # 2. 为现有用户补充display_name字段值
            print("\n2. 为现有用户补充display_name字段值...")
            try:
                connection.execute(text("UPDATE user SET display_name = username WHERE display_name IS NULL"))
                print("   ✓ 已为所有display_name为空的用户设置为username值")
            except Exception as e:
                print(f"   ℹ display_name字段更新失败: {str(e)}")
            
            # 提交事务
            trans.commit()
            print("\n✓ 所有修复操作完成")
            
            # 验证更新后的表结构
            print("\n3. 验证更新后的表结构...")
            
            # 验证User表
            print("\nUser表结构:")
            result = connection.execute(text("SHOW COLUMNS FROM user"))
            columns = result.fetchall()
            print(f"表中现在有 {len(columns)} 个字段:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
            
        except Exception as e:
            # 回滚事务
            trans.rollback()
            print(f"\n❌ 操作失败，已回滚: {e}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"\n❌ 数据库连接失败: {e}")

print("\n" + "="*60)
print("数据库表结构修复完成")
print("="*60)