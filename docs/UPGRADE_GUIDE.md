# MySQL数据库配置与维护指南

本文档提供了应用使用MySQL数据库的配置、维护和迁移指南。

## 环境要求

1. Python 3.6+ 环境
2. MySQL 5.7+ 或 MariaDB 10.2+
3. 安装所有必要的依赖

## MySQL数据库配置

### 1. 安装依赖

首先，确保安装了所有必要的依赖包：

```bash
pip install -r requirements.txt
```

### 2. 数据库连接配置

在应用根目录创建或修改`.env`文件，配置MySQL数据库连接信息：

```
# 数据库连接信息
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_username
DB_PASSWORD=your_password
DB_NAME=your_database
DB_CHARSET=utf8mb4
DB_TIMEZONE=+8:00

# 应用环境
APP_ENV=development  # development, production
```

请根据您的实际MySQL配置修改以上参数。

### 3. 创建数据库（首次使用）

您需要在MySQL中创建一个新的数据库：

```sql
CREATE DATABASE your_database DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. 启动应用

应用启动时会自动创建所需的表结构：

```bash
python run.py
```

## 数据库迁移

### 手动执行数据迁移

如果您需要手动执行数据迁移，可以使用以下命令：

```python
from app import app
from app.models.db import db, migrate_from_json, cleanup_expired_data

with app.app_context():
    # 创建数据库表（如果不存在）
    db.create_all()
    
    # 执行数据迁移
    migrate_from_json()
    
    # 清理过期数据
    cleanup_expired_data()
```

## 数据库维护

### 定期清理数据

系统会自动清理过期数据，您也可以手动运行以下代码进行深度清理：

```python
from app import app
from app.models.db import cleanup_expired_data

with app.app_context():
    cleanup_expired_data()
```

### 数据库备份

建议定期备份MySQL数据库：

```bash
# 使用mysqldump备份整个数据库
mysqldump -h localhost -u your_username -p your_database > backup_$(date +%Y%m%d).sql
```

### 数据库恢复

使用备份文件恢复数据库：

```bash
mysql -h localhost -u your_username -p your_database < backup_file.sql
```

## 版本迁移指南

### 从v1.1.1升级到v1.1.2

v1.1.2版本主要进行了项目清理和文档更新，不涉及数据库结构变更。升级步骤：

1. 更新代码到v1.1.2版本
2. 无需修改数据库结构
3. 启动应用即可使用

## 常见问题

### 数据库连接失败

如果应用无法连接到MySQL数据库，请检查以下几点：

1. 确保MySQL服务正在运行
2. 验证`.env`文件中的数据库配置是否正确
3. 检查数据库用户是否有足够的权限
4. 查看应用日志中的具体错误信息

### 表创建失败

如果表创建失败，请检查：

1. 数据库用户是否有创建表的权限
2. 数据库是否已创建
3. 数据库连接是否正常

## 安全建议

1. 使用强密码保护数据库账户
2. 避免在生产环境中使用root账户
3. 定期更新数据库密码
4. 限制数据库访问IP
5. 定期备份数据库

## 联系支持

如果您在配置或维护过程中遇到任何问题，请联系技术支持。