import os
import shutil
import sys

def remove_file(file_path):
    """删除单个文件"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"已删除文件: {file_path}")
        else:
            print(f"文件不存在: {file_path}")
    except Exception as e:
        print(f"删除文件失败 {file_path}: {e}")

def remove_directory(dir_path):
    """删除整个目录"""
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            print(f"已删除目录: {dir_path}")
        else:
            print(f"目录不存在: {dir_path}")
    except Exception as e:
        print(f"删除目录失败 {dir_path}: {e}")

def main():
    # 获取当前工作目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("开始清理临时文件和初始化文件...")
    
    # 1. 删除tests/temp目录下的临时测试文件
    temp_dir = os.path.join(base_dir, "tests", "temp")
    temp_files = [
        "analyze_project_structure.py",
        "create_test_user.py",
        "restructure_project.py",
        "simple_test_registration.py",
        "simulate_registration_login.py",
        "test_login.py",
        "test_verification_code.py",
        "test_verify_code.py",
        "test_with_real_code.py"
    ]
    
    for file in temp_files:
        remove_file(os.path.join(temp_dir, file))
    
    # 2. 删除根目录下的临时初始化和迁移脚本
    temp_scripts = [
        "add_admin_user.py",
        "add_side_user.py",
        "check_update_admin.py",
        "init_db.py",
        "init_mysql.sql",
        "init_mysql_db.py",
        "read_mysql_users.py",
        "restore_mysql_users.py",
        "setup_mysql.py",
        "setup_mysql_admin.py",
        "upgrade_to_db.py",
        "verify_users.py"
    ]
    
    for script in temp_scripts:
        remove_file(os.path.join(base_dir, script))
    
    # 3. 删除__pycache__目录
    pycache_dirs = [
        os.path.join(base_dir, "__pycache__"),
        os.path.join(base_dir, "tests", "__pycache__"),
        os.path.join(base_dir, "tests", "unit", "__pycache__"),
        os.path.join(base_dir, "app", "__pycache__")
    ]
    
    for dir_path in pycache_dirs:
        remove_directory(dir_path)
    
    print("清理完成！")

if __name__ == "__main__":
    main()
