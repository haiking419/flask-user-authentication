# v0.1 版本发布说明

## 主要功能

1. **登录日志记录功能**
   - 添加了 `LoginLog` 数据库模型，用于记录所有登录尝试
   - 记录关键信息：用户名、IP地址、登录状态、错误信息、时间戳
   - 支持多种失败场景的日志记录：验证码错误、密码错误、用户不存在

2. **登录安全性增强**
   - 实现了完整的登录审计能力
   - 遵循安全规范，确保敏感信息不被记录
   - 提供详细的登录状态追踪

## 技术实现

### 数据库扩展
- 在 `app/models/db.py` 中添加了 `LoginLog` 模型
- 自动创建 `login_log` 表，无需手动数据库迁移

### 功能增强
- 登录路由(`app/routes/auth.py`)集成日志记录功能
- 支持成功和失败登录的全面记录
- 提供丰富的错误信息分类

### 测试完善
- 创建了全面的集成测试套件
- 覆盖多种登录场景和边缘情况
- 优化测试环境配置

## 文件变更

- `app/models/db.py` - 添加 LoginLog 模型
- `app/routes/auth.py` - 增强登录功能，添加日志记录
- `app/models/__init__.py` - 更新模型导出配置
- `tests/integration/check_login_logs.py` - 登录日志检查工具
- `tests/integration/test_login_log.py` - 登录日志测试
- `tests/integration/generate_captcha_test.py` - 验证码测试

## 兼容性

- 与之前版本完全兼容
- 无需修改现有数据库结构
- 所有现有功能保持不变，仅增强了日志记录能力