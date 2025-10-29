# Hello World Web 应用

## 项目概述

这是一个基于 Flask 框架开发的简单 Web 应用，提供用户注册、登录功能，支持普通账号登录和企业微信扫码登录。应用采用 JSON 文件存储数据，适合学习和小型应用部署。

## 技术栈

- **后端框架**：Flask
- **数据存储**：JSON 文件
- **前端技术**：HTML、Tailwind CSS、Font Awesome
- **认证方式**：账号密码认证、企业微信 OAuth2.0
- **验证码系统**：邮箱验证码

## 功能特点

### 1. 用户注册
- 支持邮箱验证的用户注册流程
- 6位数字验证码，有效期10分钟
- 密码加密存储（SHA-256）
- 开发环境下自动在控制台显示验证码

### 2. 用户登录
- 传统用户名密码登录
- 企业微信扫码登录
- 会话持久化（1天有效期）

### 3. 验证码服务
- 邮件验证码发送
- 验证码有效性验证
- 开发环境适配（控制台显示验证码）

## 项目结构

```
helloworld/
├── app/
│   ├── __init__.py      # 应用初始化和配置
│   ├── models/          # 数据模型层
│   │   └── __init__.py
│   ├── routes/          # 路由控制器
│   │   ├── __init__.py
│   │   └── auth.py      # 认证相关路由
│   ├── utils/           # 工具函数
│   │   └── __init__.py
│   ├── static/          # 静态资源（CSS、JS等）
│   └── templates/       # HTML模板
├── data/                # 数据存储目录
│   ├── users.json       # 用户数据
│   ├── verifications.json  # 验证码数据
│   └── wechat_sessions.json  # 微信会话数据
├── app.py               # 应用主文件（已迁移到__init__.py）
├── run.py               # 应用入口
├── run_tests.py         # 测试运行器
├── test_models.py       # 模型层测试
├── test_routes.py       # 路由层测试
├── test_utils.py        # 工具函数测试
└── requirements.txt     # 项目依赖
```

## 关键模块说明

### 1. 应用初始化模块 (app/__init__.py)

负责 Flask 应用的创建、配置和蓝图注册。包含邮件服务器配置、微信企业号配置、会话设置和数据存储路径定义。

### 2. 路由模块 (app/routes/auth.py)

处理所有认证相关的 HTTP 请求，包括：
- `/` - 首页，显示用户信息或重定向到登录页
- `/login` - 登录页面和登录处理
- `/register` - 注册页面和注册处理
- `/send_verification` - 发送验证码API
- `/wechat_callback` - 企业微信登录回调

### 3. 工具模块 (app/utils/__init__.py)

提供各种辅助功能：
- `generate_verification_code()` - 生成6位数字验证码
- `generate_wechat_state()` - 生成微信登录状态码
- `send_email()` - 发送邮件（开发环境优化）
- `verify_code()` - 验证验证码有效性

### 4. 数据模型模块 (app/models/__init__.py)

处理 JSON 文件的读写操作：
- `get_users()/save_users()` - 用户数据操作
- `get_verifications()/save_verifications()` - 验证码数据操作
- `get_wechat_sessions()/save_wechat_sessions()` - 微信会话数据操作

## 开发环境配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置修改

在 `app/__init__.py` 中可以修改以下配置：

- 邮件服务器配置
- 企业微信应用信息
- 会话过期时间

### 3. 运行应用

```bash
python run.py
```

应用将在 `http://localhost:5000` 启动。

## 验证码测试说明

在开发环境中，邮件不会实际发送，但验证码会在控制台输出。当请求 `/send_verification` 端点时，控制台会显示类似以下信息：

```
开发环境：模拟发送邮件到 test@example.com
主题：Hello World 注册验证码
========== 验证码提示 ==========
开发环境验证码：123456 (邮箱: test@example.com)
请复制此验证码到注册页面
=============================
```

## 测试用例

项目包含完整的测试套件，覆盖以下测试场景：

1. **模型层测试** - 验证数据读写功能
2. **路由层测试** - 验证 HTTP 请求处理和响应
3. **工具函数测试** - 验证辅助功能的正确性

运行测试：

```bash
python run_tests.py
```

## 生产环境部署

### 1. 配置调整

在生产环境中，请确保：
- 正确配置邮件服务器信息
- 更改 `app.secret_key` 为安全的随机值
- 关闭调试模式 `debug=False`

### 2. 部署建议

- 使用 Gunicorn/uWSGI 作为 WSGI 服务器
- 配置 Nginx 作为反向代理
- 设置环境变量存储敏感信息

## 企业微信登录配置

要启用企业微信登录，需要：

1. 在企业微信管理后台创建应用
2. 获取企业 ID (corpid)、应用 ID (agentid) 和应用密钥 (appsecret)
3. 在 `app/__init__.py` 中更新相应配置
4. 配置回调域名 (需与企业微信应用中设置一致)

## 安全注意事项

1. 生产环境中请勿使用示例的默认配置
2. 确保敏感信息（如密码、密钥）不被提交到代码仓库
3. 定期清理过期的验证码和微信会话数据
4. 考虑增加登录失败次数限制和其他安全措施

## 许可证

本项目仅供学习和演示使用。