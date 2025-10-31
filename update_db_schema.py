#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新数据库表结构，添加缺失的企业微信相关字段和登录日志字段"""

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
print("更新数据库表结构开始")
print("="*60)

try:
    # 创建数据库引擎
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as connection:
        # 开始事务
        trans = connection.begin()
        
        try:
            # 1. 更新User表，添加企业微信相关字段
            print("\n1. 更新User表，添加企业微信相关字段...")
            
            # 添加display_name字段（系统用户名，用于页面展示）
            try:
                connection.execute(text("ALTER TABLE user ADD COLUMN display_name VARCHAR(100) NULL AFTER username"))
                print("   ✓ display_name字段添加成功")
            except Exception as e:
                print(f"   ℹ display_name字段可能已存在: {str(e)}")
                
            # 添加wechat_corp_userid字段
            try:
                connection.execute(text("ALTER TABLE user ADD COLUMN wechat_corp_userid VARCHAR(120) NULL UNIQUE AFTER email"))
                print("   ✓ wechat_corp_userid字段添加成功")
            except Exception as e:
                print(f"   ℹ wechat_corp_userid字段可能已存在: {str(e)}")
            
            # 添加wechat_corp_name字段
            try:
                connection.execute(text("ALTER TABLE user ADD COLUMN wechat_corp_name VARCHAR(120) NULL AFTER wechat_corp_userid"))
                print("   ✓ wechat_corp_name字段添加成功")
            except Exception as e:
                print(f"   ℹ wechat_corp_name字段可能已存在: {str(e)}")
            
            # 添加wechat_corp_avatar字段
            try:
                connection.execute(text("ALTER TABLE user ADD COLUMN wechat_corp_avatar VARCHAR(500) NULL AFTER wechat_corp_name"))
                print("   ✓ wechat_corp_avatar字段添加成功")
            except Exception as e:
                print(f"   ℹ wechat_corp_avatar字段可能已存在: {str(e)}")
            
            # 添加wechat_corp_binded_at字段
            try:
                connection.execute(text("ALTER TABLE user ADD COLUMN wechat_corp_binded_at DATETIME NULL AFTER wechat_corp_avatar"))
                print("   ✓ wechat_corp_binded_at字段添加成功")
            except Exception as e:
                print(f"   ℹ wechat_corp_binded_at字段可能已存在: {str(e)}")
            
            # 2. 更新LoginLog表
            print("\n2. 更新LoginLog表，添加缺失字段...")
            
            # 添加browser字段
            try:
                connection.execute(text("ALTER TABLE login_log ADD COLUMN browser VARCHAR(200) NULL AFTER ip_address"))
                print("   ✓ browser字段添加成功")
            except Exception as e:
                print(f"   ℹ browser字段可能已存在: {str(e)}")
            
            # 添加user_agent字段
            try:
                connection.execute(text("ALTER TABLE login_log ADD COLUMN user_agent VARCHAR(500) NULL AFTER browser"))
                print("   ✓ user_agent字段添加成功")
            except Exception as e:
                print(f"   ℹ user_agent字段可能已存在: {str(e)}")
            
            # 添加platform字段
            try:
                connection.execute(text("ALTER TABLE login_log ADD COLUMN platform VARCHAR(100) NULL AFTER user_agent"))
                print("   ✓ platform字段添加成功")
            except Exception as e:
                print(f"   ℹ platform字段可能已存在: {str(e)}")
            
            # 添加password_hash_debug字段（仅调试用）
            try:
                connection.execute(text("ALTER TABLE login_log ADD COLUMN password_hash_debug VARCHAR(200) NULL AFTER platform"))
                print("   ✓ password_hash_debug字段添加成功")
            except Exception as e:
                print(f"   ℹ password_hash_debug字段可能已存在: {str(e)}")
            
            # 添加request_params字段
            try:
                connection.execute(text("ALTER TABLE login_log ADD COLUMN request_params TEXT NULL AFTER error_message"))
                print("   ✓ request_params字段添加成功")
            except Exception as e:
                print(f"   ℹ request_params字段可能已存在: {str(e)}")
            
            # 添加response_time字段
            try:
                connection.execute(text("ALTER TABLE login_log ADD COLUMN response_time FLOAT NULL AFTER request_params"))
                print("   ✓ response_time字段添加成功")
            except Exception as e:
                print(f"   ℹ response_time字段可能已存在: {str(e)}")
            
            # 提交事务
            trans.commit()
            print("\n✓ 所有字段更新操作完成")
            
            # 验证更新后的表结构
            print("\n3. 验证更新后的表结构...")
            
            # 验证User表
            print("\nUser表结构:")
            result = connection.execute(text("SHOW COLUMNS FROM user"))
            columns = result.fetchall()
            print(f"表中现在有 {len(columns)} 个字段:")
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
            
            # 验证LoginLog表
            print("\nLoginLog表结构:")
            result = connection.execute(text("SHOW COLUMNS FROM login_log"))
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
print("数据库表结构更新完成")
print("="*60)
