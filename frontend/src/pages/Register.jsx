import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Register() {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    verification_code: '',
    password: '',
    confirm_password: ''
  })
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [countdown, setCountdown] = useState(0)
  const [showPassword, setShowPassword] = useState(false) // 密码可见性切换
  const [isLoading, setIsLoading] = useState(false) // 加载状态
  const navigate = useNavigate()

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const sendVerificationCode = async () => {
    if (!formData.email) {
      alert('请先输入邮箱地址')
      return
    }

    // 开始倒计时
    setCountdown(60)
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    try {
      const response = await fetch('/api/send_verification', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email: formData.email })
      })
      
      const data = await response.json()
      
      if (data.success) {
        setSuccessMessage('验证码已发送，请查收邮箱')
        setErrorMessage('')
      } else {
        setErrorMessage(data.message || '发送验证码失败')
        setSuccessMessage('')
        clearInterval(timer)
        setCountdown(0)
      }
    } catch (error) {
      setErrorMessage('网络错误，请稍后重试')
      setSuccessMessage('')
      clearInterval(timer)
      setCountdown(0)
      console.error('发送验证码错误:', error)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')
    setIsLoading(true) // 显示加载状态

    // 表单验证
    if (formData.password !== formData.confirm_password) {
      setErrorMessage('两次输入的密码不一致')
      setIsLoading(false)
      return
    }

    try {
      const response = await fetch('/api/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      })
      
      const data = await response.json()
      
      if (data.success) {
        setSuccessMessage('注册成功，正在跳转到首页...')
        setTimeout(() => {
          navigate('/')
        }, 1500) // 缩短跳转时间，提升体验
      } else {
        setErrorMessage(data.message || '注册失败，请重试')
      }
    } catch (error) {
      setErrorMessage('网络错误，请稍后重试')
      console.error('注册错误:', error)
    } finally {
      setIsLoading(false) // 隐藏加载状态
    }
  }

  return (
    <div className="form-container">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-secondary/10 text-secondary rounded-full mb-4">
          <i className="fa fa-user-plus text-2xl"></i>
        </div>
        <h1 className="text-3xl font-bold text-gray-800">创建账号</h1>
        <p className="text-gray-500 mt-2">请填写以下信息完成注册</p>
      </div>

      {errorMessage && (
        <div className="error-message">
          <i className="fa fa-exclamation-circle mr-2"></i>
          {errorMessage}
        </div>
      )}

      {successMessage && (
        <div className="success-message">
          <i className="fa fa-check-circle mr-2"></i>
          {successMessage}
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
          <label htmlFor="email">邮箱</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              <i className="fa fa-envelope"></i>
            </div>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              className="pl-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
              placeholder="请输入邮箱"
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="verification_code">验证码</label>
          <div className="flex space-x-2">
            <div className="relative flex-grow">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                <i className="fa fa-shield"></i>
              </div>
              <input
                type="text"
                id="verification_code"
                name="verification_code"
                value={formData.verification_code}
                onChange={handleChange}
                required
                className="pl-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
                placeholder="请输入验证码"
              />
            </div>
            <button
              type="button"
              onClick={sendVerificationCode}
              disabled={countdown > 0}
              className="bg-primary hover:bg-primary/90 text-white font-medium py-3 px-4 rounded-lg transition-colors whitespace-nowrap"
            >
              {countdown > 0 ? `${countdown}秒后重试` : '发送验证码'}
            </button>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="password">密码</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              <i className="fa fa-key"></i>
            </div>
            <input
              type={showPassword ? "text" : "password"}
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              required
              className="pl-10 pr-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
              placeholder="请输入密码"
            />
            {/* 添加密码可见性切换按钮 */}
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title={showPassword ? "隐藏密码" : "显示密码"}
              >
                <i className={showPassword ? "fa fa-eye-slash" : "fa fa-eye"}></i>
              </button>
            </div>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="confirm_password">确认密码</label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              <i className="fa fa-check-circle"></i>
            </div>
            <input
              type={showPassword ? "text" : "password"}
              id="confirm_password"
              name="confirm_password"
              value={formData.confirm_password}
              onChange={handleChange}
              required
              className="pl-10 pr-10 w-full px-3 py-3 border border-gray-300 rounded-lg shadow-sm focus:outline-none input-focus transition duration-200"
              placeholder="请再次输入密码"
            />
            {/* 共享密码可见性切换按钮 */}
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title={showPassword ? "隐藏密码" : "显示密码"}
              >
                <i className={showPassword ? "fa fa-eye-slash" : "fa fa-eye"}></i>
              </button>
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading}
          className="btn btn-secondary w-full flex items-center justify-center"
        >
          {isLoading ? (
            <>
              <i className="fa fa-spinner fa-spin mr-2"></i> 注册中...
            </>
          ) : (
            <>
              <i className="fa fa-user-plus mr-2"></i> 注册
            </>
          )}
        </button>
      </form>

      <div className="mt-6 text-center">
        <p className="text-gray-600">
          已有账号？ <a href="/login" className="text-primary hover:text-primary/80 font-medium transition duration-200">立即登录</a>
        </p>
      </div>
    </div>
  )
}

export default Register