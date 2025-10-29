import pymysql
import mysql.connector
from datetime import datetime
import os
import argparse

def test_pymysql_connection(host='localhost', user='root', password='', database='mysql', port=3306):
    """
    使用PyMySQL测试MySQL连接
    """
    print(f"\n=== 使用PyMySQL测试连接到 {host}:{port} 数据库 {database} ===")
    try:
        # 尝试连接
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print("✅ PyMySQL连接成功!")
        
        # 测试执行查询
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT VERSION() as version")
                result = cursor.fetchone()
                print(f"✅ MySQL服务器版本: {result['version']}")
                
                # 显示当前数据库中的表
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                print(f"✅ 数据库 {database} 中的表数量: {len(tables)}")
                if tables:
                    print("表列表:")
                    for i, table in enumerate(tables, 1):
                        print(f"  {i}. {list(table.values())[0]}")
        finally:
            conn.close()
            print("✅ 连接已关闭")
        
        return True
    except Exception as e:
        print(f"❌ PyMySQL连接失败: {str(e)}")
        return False

def test_mysql_connector_connection(host='localhost', user='root', password='', database='mysql', port=3306):
    """
    使用mysql-connector-python测试MySQL连接
    """
    print(f"\n=== 使用mysql-connector-python测试连接到 {host}:{port} 数据库 {database} ===")
    try:
        # 尝试连接
        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )
        
        print("✅ mysql-connector-python连接成功!")
        
        # 测试执行查询
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT VERSION() as version")
            result = cursor.fetchone()
            print(f"✅ MySQL服务器版本: {result['version']}")
        finally:
            cursor.close()
            conn.close()
            print("✅ 连接已关闭")
        
        return True
    except Exception as e:
        print(f"❌ mysql-connector-python连接失败: {str(e)}")
        return False

def test_sqlalchemy_mysql_connection(host='localhost', user='root', password='', database='mysql', port=3306):
    """
    使用SQLAlchemy测试MySQL连接
    """
    print(f"\n=== 使用SQLAlchemy测试连接到 {host}:{port} 数据库 {database} ===")
    try:
        from sqlalchemy import create_engine
        
        # 创建MySQL连接URL
        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        
        # 创建引擎
        engine = create_engine(db_url, pool_pre_ping=True)
        
        # 测试连接
        with engine.connect() as conn:
            result = conn.execute("SELECT VERSION() as version")
            version = result.fetchone()[0]
            print(f"✅ SQLAlchemy连接成功!")
            print(f"✅ MySQL服务器版本: {version}")
        
        return True
    except ImportError:
        print("❌ SQLAlchemy未安装，请先安装: pip install sqlalchemy")
        return False
    except Exception as e:
        print(f"❌ SQLAlchemy连接失败: {str(e)}")
        return False

def print_flask_sqlalchemy_config_example():
    """
    打印Flask-SQLAlchemy配置示例
    """
    example = '''
=== Flask-SQLAlchemy MySQL配置示例 ===
在config.py中添加MySQL配置：

class MySQLConfig(Config):
    # MySQL数据库配置
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://用户名:密码@主机地址:端口号/数据库名?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 连接池配置
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_MAX_OVERFLOW = 20
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 1800
    '''
    print(example)

def parse_args():
    """
    解析命令行参数
    """
    parser = argparse.ArgumentParser(description='MySQL连接测试工具')
    parser.add_argument('--host', default='localhost', help='MySQL主机地址')
    parser.add_argument('--port', type=int, default=3306, help='MySQL端口号')
    parser.add_argument('--user', default='root', help='MySQL用户名')
    parser.add_argument('--password', default='', help='MySQL密码')
    parser.add_argument('--database', default='mysql', help='MySQL数据库名')
    return parser.parse_args()

def main():
    # 解析命令行参数
    args = parse_args()
    
    print("="*60)
    print("        MySQL连接测试工具        ")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print(f"使用以下连接信息:")
    print(f"主机地址: {args.host}")
    print(f"端口号: {args.port}")
    print(f"用户名: {args.user}")
    print(f"密码: {'*' * len(args.password)}")  # 密码隐藏显示
    print(f"数据库名: {args.database}")
    print("="*60)
    
    # 设置连接参数
    host = args.host
    port = args.port
    user = args.user
    password = args.password
    database = args.database
    
    print("\n开始测试连接...")
    
    # 运行测试
    pymysql_result = test_pymysql_connection(host, user, password, database, port)
    connector_result = test_mysql_connector_connection(host, user, password, database, port)
    sqlalchemy_result = test_sqlalchemy_mysql_connection(host, user, password, database, port)
    
    # 打印总结
    print("\n" + "="*60)
    print("测试结果汇总:")
    print(f"PyMySQL: {'成功' if pymysql_result else '失败'}")
    print(f"mysql-connector-python: {'成功' if connector_result else '失败'}")
    print(f"SQLAlchemy: {'成功' if sqlalchemy_result else '失败'}")
    
    # 如果全部失败，给出建议
    if not any([pymysql_result, connector_result, sqlalchemy_result]):
        print("\n❌ 所有连接测试都失败了，建议检查：")
        print("1. MySQL服务是否已启动")
        print("2. 连接信息是否正确")
        print("3. 用户是否有足够的权限")
        print("4. 防火墙是否允许连接")
    
    # 打印Flask配置示例
    print_flask_sqlalchemy_config_example()
    print("="*60)

if __name__ == "__main__":
    main()
