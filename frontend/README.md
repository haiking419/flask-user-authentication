# 前端应用

这是一个使用React构建的前端应用，与后端API进行交互。

## 技术栈

- React
- React Router
- Vite
- Axios (用于API调用)
- CSS (基础样式)

## 安装

1. 确保已安装Node.js (推荐v14或更高版本)
2. 安装依赖:

```bash
npm install
```

## 运行

### 开发模式

```bash
npm run dev
```

前端应用将在 http://localhost:3000 启动，并将所有API请求代理到 http://localhost:5000。

### 构建

```bash
npm run build
```

构建产物将输出到 `dist` 目录。

### 预览构建

```bash
npm run preview
```

## 项目结构

```
src/
  ├── components/      # 通用组件
  ├── pages/           # 页面组件
  ├── services/        # API服务
  ├── utils/           # 工具函数
  ├── App.jsx          # 应用入口组件
  ├── main.jsx         # React入口文件
  └── index.css        # 全局样式
```

## 环境配置

开发服务器配置在 `vite.config.js` 文件中，包含API代理设置。

## 功能

- 用户登录/注册
- 企业微信登录
- 用户信息展示
- 验证码功能