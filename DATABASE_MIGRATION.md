# 数据库迁移指南

本文档描述了从 JSON 文件存储到 SQLite 数据库的迁移过程。

## 迁移概述

本项目已从使用 JSON 文件存储数据升级到使用 SQLite 数据库存储数据。迁移过程设计为无缝过渡，包含以下关键组件：

1. **数据模型定义**：使用 SQLAlchemy ORM 定义了用户、验证码和微信会话的数据模型
2. **自动数据迁移**：首次启动应用时自动从 JSON 文件迁移数据到数据库
3. **兼容层**：保留原有的数据访问 API，确保现有代码无需修改即可运行
4. **降级机制**：如果数据库操作失败，系统会自动降级到使用 JSON 文件

## 数据库模型

### 用户表 (users)
- `id`: 主键
- `username`: 用户名（唯一索引）
- `password`: 密码（SHA-256 哈希）
- `email`: 邮箱（唯一索引）
- `created_at`: 创建时间戳
- `login_type`: 登录类型（'default' 或 'wechat'）
- `wechat_userid`: 企业微信用户 ID（唯一索引）

### 验证码表 (verifications)
- `id`: 主键
- `email`: 邮箱（唯一索引）
- `code`: 验证码
- `created_at`: 创建时间戳

### 微信会话表 (wechat_sessions)
- `id`: 主键
- `state`: 微信登录状态码（唯一索引）
- `created_at`: 创建时间戳

## 迁移过程

### 1. 安装依赖

确保已安装所需的依赖包：

```bash
pip install -r requirements.txt
```

### 2. 自动迁移

首次启动应用时，系统会自动执行以下操作：

1. 创建数据库表（如果不存在）
2. 从 JSON 文件迁移数据到数据库（仅在开发环境）
3. 清理过期数据

### 3. 手动触发迁移

如果需要手动触发数据迁移，可以使用以下脚本：

```python
from app import app
from app.models.db import migrate_from_json

with app.app_context():
    migrate_from_json()
```

## 数据清理

系统会自动清理过期的数据：

- 过期的验证码（超过 10 分钟）
- 过期的微信会话（超过 5 分钟）

## 配置选项

在 `config.py` 文件中，可以配置数据库相关的选项：

```python
# 数据库 URI
SQLALCHEMY_DATABASE_URI = 'sqlite:///data/app.db'

# 是否追踪数据库修改（开发环境推荐开启，生产环境应关闭）
SQLALCHEMY_TRACK_MODIFICATIONS = False
```

### 生产环境配置

在生产环境中，可以通过环境变量配置数据库：

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/mydatabase"
export FLASK_ENV="production"
```

## 回滚方案

如果需要回滚到使用 JSON 文件：

1. 在 `app/__init__.py` 中注释掉数据库初始化相关代码
2. 在 `app/models/__init__.py` 中使用原始的 JSON 文件操作函数

## 性能考虑

与使用 JSON 文件相比，使用数据库可以提供以下优势：

1. **更好的并发性能**：避免文件锁定问题
2. **更快的查询速度**：支持索引和高效查询
3. **更好的数据完整性**：支持约束和事务
4. **可扩展性**：更容易迁移到更大的数据库系统

## 常见问题

### 迁移失败

如果迁移过程中出现错误，可以检查以下几点：

1. 确保数据目录存在并有写入权限
2. 检查 JSON 文件格式是否正确
3. 查看应用日志中的错误信息

### 数据不一致

如果发现数据库和 JSON 文件中的数据不一致，系统会优先使用数据库中的数据。可以通过手动执行迁移脚本来同步数据。