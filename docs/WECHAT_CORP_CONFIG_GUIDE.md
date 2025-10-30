# 企业微信扫码登录配置指南

## 问题描述

当用户点击企业微信扫码登录时，页面显示"参数错误"，这通常是由于企业微信相关配置不正确导致的。

## 解决方案

### 1. 检查企业微信配置参数

在继续操作前，请确保以下参数已正确配置：

- `WECHAT_CORP_ID`：企业微信的企业ID
- `WECHAT_AGENT_ID`：企业微信应用的AgentId
- `WECHAT_APP_SECRET`：企业微信应用的Secret
- `WECHAT_REDIRECT_URI`：回调地址（必须与企业微信后台配置一致）

### 2. 如何正确配置这些参数

#### 方法一：通过环境变量配置（推荐）

在服务器或开发环境中设置以下环境变量：

```bash
# Windows 命令提示符
set WECHAT_CORP_ID=您的企业ID
set WECHAT_AGENT_ID=您的应用AgentId
set WECHAT_APP_SECRET=您的应用Secret
set WECHAT_REDIRECT_URI=https://您的域名/wechat_callback

# Windows PowerShell
$env:WECHAT_CORP_ID="您的企业ID"
$env:WECHAT_AGENT_ID="您的应用AgentId"
$env:WECHAT_APP_SECRET="您的应用Secret"
$env:WECHAT_REDIRECT_URI="https://您的域名/wechat_callback"
```

#### 方法二：通过.env.production文件配置

在项目根目录的 `.env.production` 文件中添加：

```
WECHAT_CORP_ID=您的企业ID
WECHAT_AGENT_ID=您的应用AgentId
WECHAT_APP_SECRET=您的应用Secret
WECHAT_REDIRECT_URI=https://您的域名/wechat_callback
```

### 3. 企业微信后台配置步骤

1. **登录企业微信管理后台**：访问 https://work.weixin.qq.com/
2. **进入应用管理**：
   - 点击左侧菜单「应用管理」
   - 选择或创建一个应用
3. **配置应用信息**：
   - 记录下「AgentId」和「Secret」（需要点击获取）
   - 记录下「企业ID」（在「我的企业」->「企业信息」中获取）
4. **配置回调域名**：
   - 在应用详情页面，找到「企业微信授权登录」
   - 配置「可信域名」为您的服务器域名（例如：example.com）
   - 确保回调URL格式为：`https://您的域名/wechat_callback`

### 4. 常见错误及解决方法

#### 错误：参数错误
- **原因**：企业ID、AgentId或回调地址不正确
- **解决**：确认所有配置参数与企业微信后台完全一致

#### 错误：redirect_uri参数错误
- **原因**：回调地址未在企业微信后台配置
- **解决**：在企业微信后台添加回调域名

#### 错误：访问受限
- **原因**：IP白名单限制或网络问题
- **解决**：检查企业微信应用的IP白名单设置

### 5. 测试模式使用

如果您只是想测试功能或在开发环境中绕过IP限制（错误码60020），可以使用测试模式：

1. 访问：`http://您的域名/wechat_corp_login?mode=test`（开发环境）或 `https://您的域名/wechat_corp_login?mode=test`（生产环境）
2. 在测试模式页面点击模拟扫码链接

测试模式会：
- 生成模拟的企业微信回调URL
- 创建测试用户
- 绕过真实的企业微信API调用
- 直接完成登录流程

此功能特别适用于：
- 开发环境测试
- 解决IP访问受限问题（错误码60020）
- 在没有真实企业微信配置的情况下验证登录流程

## 重要提示

1. 生产环境必须使用HTTPS协议的回调地址
2. 所有配置参数区分大小写
3. 回调地址必须与企业微信后台配置完全一致（包括协议、域名、路径）
4. 企业微信应用必须启用「网页授权及JS-SDK」功能

## 联系支持

如果您按照以上步骤配置后仍然遇到问题，请检查应用日志获取详细错误信息，或联系技术支持。