import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function Login() {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    captcha: ''
  })
  const [errorMessage, setErrorMessage] = useState('')
  const [wechatQrcodeUrl, setWechatQrcodeUrl] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    // 获取企业微信登录二维码URL
    fetch('/api/wechat_qrcode')
      .then(response => {
        console.log('响应状态:', response.status)
        console.log('响应类型:', response.headers.get('content-type'))
        // 首先检查响应是否成功
        if (!response.ok) {
          throw new Error(`HTTP错误! 状态码: ${response.status}`)
        }
        // 然后检查响应类型是否为JSON
        const contentType = response.headers.get('content-type')
        if (!contentType || !contentType.includes('application/json')) {
          // 如果不是JSON，获取文本内容以便调试
          return response.text().then(text => {
            console.error('非JSON响应:', text.substring(0, 100) + '...')
            throw new Error('响应不是JSON格式')
          })
        }
        return response.json()
      })
      .then(data => {
        console.log('获取到的企业微信数据:', data)
        if (data.success && data.qrcode_url) {
          setWechatQrcodeUrl(data.qrcode_url)
        }
      })
      .catch(error => {
        console.error('获取企业微信登录链接失败:', error)
        // 错误处理，避免页面崩溃
      })
  }, [])

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      })
      
      const data = await response.json()
      
      if (data.success) {
        navigate('/')
      } else {
        setErrorMessage(data.message || '登录失败，请重试')
      }
    } catch (error) {
      setErrorMessage('网络错误，请稍后重试')
      console.error('登录错误:', error)
    }
  }

  const [captchaUrl, setCaptchaUrl] = useState('/api/captcha_image')
  
  const refreshCaptcha = async () => {
    try {
      const response = await fetch('/api/captcha')
      const data = await response.json()
      if (data.success && data.captcha_url) {
        setCaptchaUrl(data.captcha_url)
      }
    } catch (error) {
      console.error('刷新验证码失败:', error)
    }
  }
  
  useEffect(() => {
    refreshCaptcha()
  }, [])

  return (
    <div className="form-container">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 text-primary rounded-full mb-4">
          <i className="fa fa-user-circle text-2xl"></i>
        </div>
        <h1 className="text-3xl font-bold text-gray-800">欢迎回来</h1>
        <p className="text-gray-500 mt-2">请登录您的账号</p>
      </div>

      {errorMessage && (
        <div className="error-message">
          <i className="fa fa-exclamation-circle mr-2"></i>
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="form-group">
          <label htmlFor="username">用户名</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              <i className="fa fa-user"></i>
            </div>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              required
              className="pl-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
              placeholder="请输入用户名"
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="password">密码</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              <i className="fa fa-key"></i>
            </div>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="pl-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
              placeholder="请输入密码"
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="captcha">图形验证码</label>
          <div className="flex space-x-2">
            <div className="relative flex-grow">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                <i className="fa fa-shield"></i>
              </div>
              <input
                type="text"
                id="captcha"
                name="captcha"
                value={formData.captcha}
                onChange={handleChange}
                required
                className="pl-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                placeholder="请输入验证码"
                maxLength="4"
              />
            </div>
            <img
              id="captcha-img"
              src={captchaUrl}
              alt="验证码"
              className="w-32 h-12 border border-gray-300 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
              onClick={refreshCaptcha}
              title="点击刷新验证码"
            />
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary w-full"
        >
          <i className="fa fa-sign-in mr-2"></i> 登录
        </button>
      </form>

      <div className="mt-6">
        <div className="relative flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative bg-white px-4 text-sm text-gray-500">
            其他登录方式
          </div>
        </div>

        <div className="mt-6">
          <a href={wechatQrcodeUrl} className="w-full inline-flex justify-center items-center space-x-2 py-3 px-4 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
            <i className="fa fa-building text-blue-600 text-xl"></i>
            <span>企业微信登录</span>
          </a>
        </div>
      </div>

      <div className="mt-6 text-center">
        <p className="text-gray-600">
          还没有账号？ <a href="/register" className="text-primary hover:text-primary/80 font-medium transition duration-200">立即注册</a>
        </p>
      </div>
    </div>
  )
}

export default Login