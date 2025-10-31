#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为User表添加updated_at字段
"""

import os
import sys
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv('.env.development')
except ImportError:
    print("未找到dotenv模块，使用默认配置")

# 数据库连接配置
DB_USER = os.environ.get('DB_USER', 'helloworld_user')
DB_PASSWORD = quote_plus(os.environ.get('DB_PASSWORD', 'Helloworld@123'))
DB_HOST = os.environ.get('DB_HOST', '172.18.0.1')
DB_PORT = os.environ.get('DB_PORT', '33060')
DB_NAME = os.environ.get('DB_NAME', 'helloworld_db')

DATABASE_URL = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'

def add_updated_at_field():
    """为User表添加updated_at字段"""
    print("开始为User表添加updated_at字段...")
    
    try:
        # 创建数据库引擎
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # 检查字段是否已存在
            check_column = conn.execute(text("SHOW COLUMNS FROM user LIKE 'updated_at'")).fetchone()
            
            if check_column:
                print("✓ updated_at字段已存在，无需添加")
                return True
            
            # 添加updated_at字段
            print("执行添加updated_at字段操作...")
            conn.execute(text("""
                ALTER TABLE user 
                ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                MODIFY COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            """))
            
            # 提交更改
            conn.commit()
            
            # 验证字段是否添加成功
            verify_column = conn.execute(text("SHOW COLUMNS FROM user LIKE 'updated_at'")).fetchone()
            
            if verify_column:
                print("✅ updated_at字段添加成功！")
                print(f"  - 字段名: {verify_column[0]}")
                print(f"  - 字段类型: {verify_column[1]}")
                
                # 为现有数据设置默认的updated_at值
                print("正在为现有数据设置updated_at默认值...")
                conn.execute(text("""
                    UPDATE user 
                    SET updated_at = created_at 
                    WHERE updated_at IS NULL
                """))
                conn.commit()
                
                updated_count = conn.execute(text("SELECT COUNT(*) FROM user WHERE updated_at IS NOT NULL")).scalar()
                print(f"  ✅ 已为 {updated_count} 条记录设置了updated_at值")
                
                return True
            else:
                print("❌ updated_at字段添加失败！")
                return False
                
    except Exception as e:
        print(f"添加字段过程中发生错误: {e}")
        return False
    finally:
        if 'engine' in locals():
            engine.dispose()

def show_updated_table_structure():
    """显示更新后的表结构"""
    print("\n更新后的User表结构:")
    
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SHOW COLUMNS FROM user"))
            for row in result:
                print(f"  - {row[0]}: {row[1]}")
    except Exception as e:
        print(f"显示表结构时发生错误: {e}")
    finally:
        if 'engine' in locals():
            engine.dispose()

def main():
    """主函数"""
    print("="*60)
    print("为User表添加updated_at字段脚本")
    print("="*60)
    
    # 显示数据库连接信息
    print(f"连接数据库: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    
    # 添加字段
    success = add_updated_at_field()
    
    if success:
        # 显示更新后的表结构
        show_updated_table_structure()
        print("\n🎉 数据库字段添加完成！")
        print("📝 接下来需要更新User模型和相关代码")
    else:
        print("\n💥 操作失败，请检查错误信息")
    
    print("\n" + "="*60)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
