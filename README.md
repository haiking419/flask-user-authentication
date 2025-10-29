# 前后端分离应用

## 项目概述

这是一个使用Flask后端和React前端的前后端分离应用示例，提供用户注册、登录功能，支持普通账号登录和企业微信扫码登录。应用采用MySQL数据库存储数据。

## 技术栈

### 后端
- **后端框架**：Flask
- **数据存储**：MySQL（统一使用，包括开发环境和生产环境）
- **认证**：Flask会话机制
- **API**：RESTful风格

### 前端
- **框架**：React
- **构建工具**：Vite
- **路由**：React Router
- **样式**：CSS + Font Awesome + Tailwind CSS

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
├── app/                  # 后端Flask应用
│   ├── __init__.py      # 应用初始化
│   ├── models/          # 数据模型
│   │   ├── __init__.py
│   │   └── db.py        # 数据库模型和操作
│   ├── routes/          # 路由定义
│   │   ├── __init__.py
│   │   ├── auth.py      # 认证路由
│   │   └── api.py       # RESTful API路由
│   ├── static/          # 静态文件
│   ├── templates/       # HTML模板
│   └── utils/           # 工具函数
│       ├── __init__.py
│       └── config_manager.py  # 配置管理
├── frontend/            # 前端React应用
│   ├── src/             # 前端源代码
│   │   ├── pages/       # 页面组件
│   │   ├── App.jsx      # 应用入口组件
│   │   ├── main.jsx     # React入口文件
│   │   ├── App.css      # 应用样式
│   │   └── index.css    # 全局样式
│   ├── index.html       # HTML模板
│   ├── package.json     # 前端依赖
│   └── vite.config.js   # Vite配置
├── data/                # JSON数据存储
│   ├── users.json
│   ├── verifications.json
│   └── wechat_sessions.json
├── .env.development     # 开发环境配置
├── .env.production      # 生产环境配置
├── app.py               # Flask应用主文件
├── config.py            # 配置文件
├── run.py               # 后端启动脚本
└── requirements.txt     # 后端依赖
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

### 4. 数据模型模块 (app/models)

- `app/models/db.py` - MySQL数据库模型和操作
  - 定义用户、验证码和微信会话等数据模型
  - 提供数据库初始化和清理功能
  - 所有数据直接存储在MySQL数据库中，不再使用JSON文件

## 安装与运行

### 后端（Flask）

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 配置MySQL数据库:
   - 确保MySQL服务已安装并运行
   - 创建数据库：`CREATE DATABASE helloworld_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   - 创建用户：`CREATE USER 'helloworld_user'@'%' IDENTIFIED BY 'Helloworld@123';
   - 授权：`GRANT ALL PRIVILEGES ON helloworld_db.* TO 'helloworld_user'@'%';
   - 刷新权限：`FLUSH PRIVILEGES;

3. 配置环境变量:
   - 参考`.env.example`文件创建或修改`.env.development`文件
   - 填写数据库连接信息：DB_HOST、DB_PORT、DB_USER、DB_PASSWORD、DB_NAME
   - 所有环境统一使用MySQL数据库配置

3. 运行后端:
```bash
python run.py
```

后端服务将在 http://localhost:5000 启动。

### 前端（React）

1. 进入前端目录:
```bash
cd frontend
```

2. 安装依赖:
```bash
npm install
```

3. 运行开发服务器:
```bash
npm run dev
```

前端应用将在 http://localhost:3000 启动，并自动代理API请求到后端。

## API接口

### 认证相关
- POST `/api/login` - 用户登录
- POST `/api/register` - 用户注册
- POST `/api/logout` - 用户登出
- GET `/api/user_info` - 获取用户信息
- POST `/api/send_verification` - 发送验证码
- GET `/api/captcha` - 获取验证码

### 企业微信
- GET `/api/wechat_qrcode` - 获取企业微信登录二维码
- GET `/api/check_wechat_login/<session_key>` - 检查企业微信登录状态

## 部署

### 开发环境
1. 启动后端: `python run.py`
2. 启动前端: `cd frontend && npm run dev`

### 生产环境
1. 构建前端:
```bash
cd frontend
npm install
npm run build
```

2. 部署后端（可使用Gunicorn、uWSGI等WSGI服务器）
3. 配置Web服务器（如Nginx）提供静态文件和代理API请求

## 注意事项

1. 在生产环境中，务必修改默认密钥和数据库配置
2. 确保数据库连接安全，避免硬编码敏感信息
3. 前端构建后的文件应部署到静态文件服务器或CDN

在 `app/__init__.py` 或 `config.py` 中可以修改以下配置：

- 邮件服务器配置
- 企业微信应用信息
- 会话过期时间

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