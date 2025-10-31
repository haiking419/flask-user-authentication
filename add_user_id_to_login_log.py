#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：为login_log表添加user_id字段
"""

import os
import sys
import pymysql
from pymysql.cursors import DictCursor

# 从环境变量获取数据库配置
DB_HOST = os.environ.get('DB_HOST', '172.18.0.1')
DB_PORT = int(os.environ.get('DB_PORT', '33060'))
DB_USER = os.environ.get('DB_USER', 'helloworld_user')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'Helloworld@123')
DB_NAME = os.environ.get('DB_NAME', 'helloworld_db')

def connect_db():
    """连接数据库"""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            db=DB_NAME,
            charset='utf8mb4',
            cursorclass=DictCursor
        )
        print(f"成功连接到数据库: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        sys.exit(1)

def check_column_exists(conn, table_name, column_name):
    """检查列是否已存在"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = %s 
                AND table_name = %s 
                AND column_name = %s
            """, (DB_NAME, table_name, column_name))
            result = cursor.fetchone()
            return result is not None
    except Exception as e:
        print(f"检查列是否存在时出错: {e}")
        return False

def add_user_id_column(conn):
    """为login_log表添加user_id字段"""
    try:
        # 检查字段是否已存在
        if check_column_exists(conn, 'login_log', 'user_id'):
            print("user_id字段已存在，无需添加")
            return True
        
        with conn.cursor() as cursor:
            # 添加user_id字段
            cursor.execute("""
                ALTER TABLE login_log 
                ADD COLUMN user_id INT(11) NULL, 
                ADD INDEX idx_user_id (user_id)
            """)
            conn.commit()
            print("成功为login_log表添加user_id字段")
            return True
    except Exception as e:
        print(f"添加user_id字段时出错: {e}")
        conn.rollback()
        return False

def main():
    """主函数"""
    print("开始执行数据库迁移: 为login_log表添加user_id字段")
    
    # 连接数据库
    conn = connect_db()
    
    try:
        # 添加字段
        success = add_user_id_column(conn)
        
        if success:
            print("数据库迁移成功完成")
        else:
            print("数据库迁移失败")
            sys.exit(1)
    finally:
        # 关闭数据库连接
        if conn:
            conn.close()
            print("数据库连接已关闭")

if __name__ == '__main__':
    main()
