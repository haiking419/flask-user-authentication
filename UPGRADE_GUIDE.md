# 数据库升级指南

本文档提供了将应用从JSON文件存储升级到SQLite数据库的详细步骤。

## 升级前准备

在开始升级前，请确保：

1. 您已备份所有重要数据
2. 您的应用可以正常运行
3. 您安装了所有必要的依赖

## 升级步骤

### 1. 安装依赖

首先，确保安装了所有必要的依赖包：

```bash
pip install -r requirements.txt
```

### 2. 运行升级脚本

我们提供了一个自动升级脚本，它会处理所有升级步骤：

```bash
python upgrade_to_db.py
```

升级脚本将执行以下操作：

1. 备份现有的JSON数据文件
2. 创建SQLite数据库和表
3. 将数据从JSON文件迁移到数据库
4. 清理过期数据
5. 验证迁移是否成功

### 3. 验证升级结果

升级脚本会显示迁移统计信息，您可以查看以下内容确认升级成功：

```
迁移统计:
- 用户: X
- 验证码: Y
- 微信会话: Z
```

### 4. 启动应用

升级成功后，您可以正常启动应用：

```bash
python run.py
```

应用现在将使用SQLite数据库而不是JSON文件存储数据。

## 升级后变更

升级后，应用将使用以下新功能：

1. **SQLite数据库**：数据将存储在`data/app.db`文件中
2. **数据模型**：使用SQLAlchemy ORM管理数据
3. **自动迁移**：应用启动时自动创建表和迁移数据
4. **自动清理**：定期清理过期数据
5. **兼容性**：保留了与旧系统的完全兼容性

## 常见问题

### 升级脚本运行失败

如果升级脚本运行失败，请检查以下几点：

1. 确保您有足够的权限访问和修改数据目录
2. 确保所有依赖都已正确安装
3. 查看错误信息，它会告诉您问题所在
4. 您可以多次运行升级脚本，它不会重复迁移数据

### 应用启动失败

如果升级后应用无法正常启动：

1. 检查数据库文件`data/app.db`是否存在且有权限
2. 查看错误日志，特别是与数据库相关的错误
3. 如果需要，可以通过注释`app/__init__.py`中的数据库初始化代码回滚到JSON存储

### 如何回滚到JSON文件存储

如果您需要回滚到使用JSON文件存储：

1. 编辑`app/__init__.py`文件，注释掉以下部分：

```python
# 初始化数据库
from app.models.db import db, migrate_from_json, cleanup_expired_data
db.init_app(app)

# 数据库初始化
with app.app_context():
    # 创建数据库表
    db.create_all()
    
    # 仅在开发环境中执行数据迁移
    if app.config['APP_ENV'] == 'development':
        try:
            migrate_from_json()
        except Exception as e:
            print(f"数据迁移失败: {e}")
    
    # 清理过期数据
    cleanup_expired_data()
```

2. 从备份目录恢复JSON文件到data目录

3. 重启应用

## 性能提升

升级到数据库后，您应该会注意到以下性能提升：

1. **更快的查询速度**：特别是对于大量用户数据
2. **更好的并发处理**：不再有文件锁定问题
3. **更可靠的数据完整性**：使用事务确保数据一致性
4. **更易于维护**：使用ORM使代码更清晰

## 后续维护

### 定期清理数据

虽然系统会自动清理过期数据，但您可以手动运行以下代码进行深度清理：

```python
from app import app
from app.models.db import cleanup_expired_data

with app.app_context():
    cleanup_expired_data()
```

### 数据库备份

建议定期备份`data/app.db`文件，以防止数据丢失。

## 联系支持

如果您在升级过程中遇到任何问题，请参考详细的`DATABASE_MIGRATION.md`文档或联系技术支持。