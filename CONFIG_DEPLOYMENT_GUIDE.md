# 配置部署指南

本文档提供了应用配置管理和部署的详细说明，帮助运营人员统一管理不同环境的配置。

## 配置管理架构

应用采用了统一的配置管理机制，具有以下特点：

1. **集中化配置管理**：通过 `app/utils/config_manager.py` 提供统一的配置获取接口
2. **环境分离**：使用不同的环境配置文件管理开发、测试和生产环境
3. **配置验证**：自动验证必要配置项的有效性
4. **优先级机制**：环境变量 > Flask配置对象 > 默认值

## 配置文件结构

应用使用以下配置文件：

1. **`.env.development`**：开发环境配置
2. **`.env.production`**：生产环境配置

这两个文件包含了应用所需的所有配置项，格式为 `KEY=VALUE`。

## 如何更新配置

### 开发环境

1. 编辑 `.env.development` 文件
2. 修改相应的配置值
3. 重启应用以应用新配置

### 生产环境

1. 编辑 `.env.production` 文件
2. 修改相应的配置值
3. 重启应用以应用新配置

### 环境变量配置（推荐用于生产）

对于生产环境，建议直接设置环境变量而不是修改配置文件，这样可以避免配置文件被意外提交到代码仓库：

```bash
# Linux/Mac
set WECHAT_CORP_ID=your_wechat_corp_id
set WECHAT_AGENT_ID=your_agent_id
set WECHAT_APP_SECRET=your_app_secret
set WECHAT_REDIRECT_URI=https://your-domain.com/wechat_callback
set SECRET_KEY=your_secure_secret_key
set DEBUG=False
set APP_ENV=production
set DATABASE_URL=mysql+pymysql://username:password@host:port/dbname?charset=utf8mb4
```

## 必需配置项

以下是应用运行必需的配置项：

| 配置项 | 说明 | 示例值 |
|-------|------|--------|
| SECRET_KEY | 应用密钥，生产环境必须设置 | helloworld_production_secret_key_2024 |
| WECHAT_CORP_ID | 企业微信CorpID | wx1234567890abcdef |
| WECHAT_AGENT_ID | 企业微信应用ID | 1000001 |
| WECHAT_APP_SECRET | 企业微信应用密钥 | abcdef1234567890abcdef1234567890 |
| WECHAT_REDIRECT_URI | 回调地址 | http://your-domain.com/wechat_callback |
| DATABASE_URL | 数据库连接字符串 | mysql+pymysql://username:password@host:port/dbname?charset=utf8mb4 |
| APP_ENV | 应用环境 | development/production/testing |

## 数据库配置

数据库配置通过 `DATABASE_URL` 环境变量设置，格式为：

```
mysql+pymysql://username:password@host:port/dbname?charset=utf8mb4
```

注意：密码中如果包含特殊字符，需要进行URL编码，例如 `@` 编码为 `%40`。

## 应用端口配置

应用端口可以通过 `PORT` 环境变量设置，默认为5000：

```bash
set PORT=8080
```

## 调试模式控制

调试模式通过 `DEBUG` 环境变量控制：

```bash
# 开发环境启用调试模式
set DEBUG=True

# 生产环境禁用调试模式
set DEBUG=False
```

## 配置验证

应用启动时会自动验证必需的配置项，如果配置不正确，会在日志中显示错误信息。

## 多环境部署最佳实践

1. **使用环境变量**：生产环境优先使用环境变量，避免配置文件泄露
2. **配置备份**：定期备份配置文件
3. **变更记录**：记录所有配置变更，便于问题排查
4. **权限控制**：限制配置文件的访问权限

## 常见问题

1. **配置不生效**：确保重启了应用，检查环境变量是否正确设置
2. **数据库连接失败**：检查 `DATABASE_URL` 是否正确，特别是密码中的特殊字符是否编码
3. **企业微信登录失败**：检查企业微信相关配置，确保回调地址已在企业微信后台配置

## 紧急回滚

如果新配置导致问题，可以通过以下步骤快速回滚：

1. 恢复之前的配置文件
2. 或设置正确的环境变量
3. 重启应用

---

**注意**：配置文件包含敏感信息，请确保安全存储，不要提交到代码仓库。