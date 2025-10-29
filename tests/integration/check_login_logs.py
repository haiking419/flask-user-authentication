from app import app
from app.models import db, LoginLog

with app.app_context():
    # 检查login_log表是否存在
    print("检查login_log表是否存在...")
    tables = db.engine.table_names()
    if 'login_log' in tables:
        print("✓ login_log表已存在")
        
        # 查询登录日志数据
        print("\n查询登录日志数据...")
        logs = LoginLog.query.all()
        print(f"找到 {len(logs)} 条登录日志")
        
        if logs:
            print("\n最新的登录日志:")
            # 获取最近5条日志
            recent_logs = LoginLog.query.order_by(LoginLog.created_at.desc()).limit(5).all()
            for log in recent_logs:
                status = "成功" if log.success else "失败"
                error_msg = f" - 错误: {log.error_message}" if not log.success else ""
                print(f"时间: {log.created_at}, 用户名: {log.username}, IP: {log.ip_address}, 状态: {status}{error_msg}")
    else:
        print("✗ login_log表不存在")
        print("尝试创建表...")
        try:
            # 尝试重新创建表
            db.create_all()
            print("✓ 表已创建")
        except Exception as e:
            print(f"✗ 创建表失败: {e}")
    
    # 打印所有数据库表
    print("\n所有数据库表:")
    for table in tables:
        print(f"- {table}")