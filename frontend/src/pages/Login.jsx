import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

function Login() {
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    captcha: ''
  })
  const [errorMessage, setErrorMessage] = useState('')
  const [wechatQrcodeUrl, setWechatQrcodeUrl] = useState('')
  const [wechatLoginState, setWechatLoginState] = useState('')
  const [scanStatus, setScanStatus] = useState('init') // init, scanning, scanned, confirmed, expired
  const [qrcodeExpiryTimer, setQrcodeExpiryTimer] = useState(null)
  const [checkStatusTimer, setCheckStatusTimer] = useState(null)
  const [showPassword, setShowPassword] = useState(false) // 添加密码可见性切换
  const [isLoading, setIsLoading] = useState(false) // 添加加载状态
  const navigate = useNavigate()
  const qrcodeRef = useRef(null)

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
          setWechatLoginState(data.state)
          // 保存state参数到本地存储，用于后续验证
          if (data.state) {
            localStorage.setItem('wechat_login_state', data.state)
            console.log('保存企业微信登录state:', data.state)
          }
          // 设置扫描状态为等待扫描
          setScanStatus('scanning')
          // 启动二维码过期定时器（通常企业微信二维码有效期为5分钟）
          const expiryTimer = setTimeout(() => {
            setScanStatus('expired')
          }, 300000) // 5分钟后过期
          setQrcodeExpiryTimer(expiryTimer)
          
          // 启动登录状态检查定时器
          startStatusCheck(data.state)
        }
      })
      .catch(error => {
        console.error('获取企业微信登录链接失败:', error)
        // 错误处理，避免页面崩溃
      })
      
    // 清理函数
    return () => {
      if (qrcodeExpiryTimer) clearTimeout(qrcodeExpiryTimer)
      if (checkStatusTimer) clearInterval(checkStatusTimer)
    }
  }, [])
  
  // 启动登录状态检查
  const startStatusCheck = (state) => {
    // 清除之前可能存在的定时器
    if (checkStatusTimer) clearInterval(checkStatusTimer)
    
    // 每2秒检查一次登录状态
    const timer = setInterval(() => {
      checkLoginStatus(state)
    }, 2000)
    
    setCheckStatusTimer(timer)
  }
  
  // 检查登录状态
  const checkLoginStatus = async (state) => {
    try {
      // 修复API URL格式，使用正确的路径参数格式
      const response = await fetch(`/api/check_wechat_login/${state}`)
      const data = await response.json()
      
      if (data.success) {
        if (data.status === 'scanned') {
          setScanStatus('scanned')
          // 已扫码状态下，缩短检查间隔
          if (checkStatusTimer) {
            clearInterval(checkStatusTimer)
            const timer = setInterval(() => {
              checkLoginStatus(state)
            }, 1000) // 缩短到1秒检查一次
            setCheckStatusTimer(timer)
          }
        } else if (data.status === 'confirmed') {
          setScanStatus('confirmed')
          // 清除定时器
          if (checkStatusTimer) clearInterval(checkStatusTimer)
          if (qrcodeExpiryTimer) clearTimeout(qrcodeExpiryTimer)
          // 登录成功，跳转到首页
          setTimeout(() => {
            navigate('/')
          }, 1000)
        } else if (data.status === 'expired') {
          setScanStatus('expired')
          if (checkStatusTimer) clearInterval(checkStatusTimer)
        }
      }
    } catch (error) {
      console.error('检查登录状态失败:', error)
    }
  }
  
  // 刷新二维码
  const refreshQrcode = () => {
    // 清除之前的定时器
    if (qrcodeExpiryTimer) clearTimeout(qrcodeExpiryTimer)
    if (checkStatusTimer) clearInterval(checkStatusTimer)
    
    // 重新获取二维码
    fetch('/api/wechat_qrcode')
      .then(response => response.json())
      .then(data => {
        if (data.success && data.qrcode_url) {
          setWechatQrcodeUrl(data.qrcode_url)
          setWechatLoginState(data.state)
          localStorage.setItem('wechat_login_state', data.state)
          setScanStatus('scanning')
          
          // 重新设置过期定时器
          const expiryTimer = setTimeout(() => {
            setScanStatus('expired')
          }, 300000)
          setQrcodeExpiryTimer(expiryTimer)
          
          // 重新启动状态检查
          startStatusCheck(data.state)
        }
      })
      .catch(error => {
        console.error('刷新企业微信二维码失败:', error)
      })
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErrorMessage('')
    setIsLoading(true) // 显示加载状态

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
        // 登录成功，添加过渡效果
        setIsLoading(true)
        setTimeout(() => {
          navigate('/')
        }, 500)
      } else {
        setErrorMessage(data.message || '登录失败，请重试')
      }
    } catch (error) {
      setErrorMessage('网络错误，请稍后重试')
      console.error('登录错误:', error)
    } finally {
      setIsLoading(false) // 隐藏加载状态
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
          disabled={isLoading}
          className="btn btn-primary w-full flex items-center justify-center"
        >
          {isLoading ? (
            <>
              <i className="fa fa-spinner fa-spin mr-2"></i> 登录中...
            </>
          ) : (
            <>
              <i className="fa fa-sign-in mr-2"></i> 登录
            </>
          )}
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
          {/* 企业微信扫码登录区域 */}
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-100 transition-all duration-300 hover:shadow-lg">
            <div className="flex flex-col items-center">
              <div className="text-center mb-4">
                <h3 className="text-lg font-semibold text-gray-800">企业微信扫码登录</h3>
                <p className="text-sm text-gray-500 mt-1">使用企业微信扫描下方二维码</p>
              </div>
              
              <div className="relative mb-4 w-48 h-48 bg-gray-50 rounded-lg flex items-center justify-center">
                {scanStatus === 'init' && (
                  <div className="text-gray-400">
                    <i className="fa fa-refresh fa-spin text-2xl"></i>
                    <p className="mt-2 text-sm">加载中...</p>
                  </div>
                )}
                
                {scanStatus === 'scanning' && wechatQrcodeUrl && (
                  <>
                    <img 
                      ref={qrcodeRef}
                      src={wechatQrcodeUrl} 
                      alt="企业微信登录二维码" 
                      className="max-w-full max-h-full p-2"
                    />
                    <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 hover:opacity-100 transition-opacity duration-300">
                      <div className="text-white text-center p-2">
                        <i className="fa fa-refresh text-xl mb-1"></i>
                        <p className="text-xs">点击刷新</p>
                      </div>
                    </div>
                  </>
                )}
                
                {scanStatus === 'scanned' && (
                  <div className="text-green-600 text-center">
                    <i className="fa fa-check-circle text-4xl mb-2"></i>
                    <p>已扫码，请在企业微信中确认</p>
                  </div>
                )}
                
                {scanStatus === 'confirmed' && (
                  <div className="text-blue-600 text-center">
                    <i className="fa fa-arrow-right text-4xl mb-2"></i>
                    <p>登录成功，正在跳转...</p>
                  </div>
                )}
                
                {scanStatus === 'expired' && (
                  <div className="text-red-500 text-center">
                    <i className="fa fa-clock-o text-4xl mb-2"></i>
                    <p>二维码已过期</p>
                    <button 
                      onClick={refreshQrcode}
                      className="mt-2 px-3 py-1 text-sm bg-red-100 text-red-600 rounded hover:bg-red-200 transition-colors"
                    >
                      刷新二维码
                    </button>
                  </div>
                )}
              </div>
              
              {/* 状态提示 */}
              <div className="text-sm text-gray-500 text-center">
                {scanStatus === 'scanning' && (
                  <p className="flex items-center justify-center">
                    <i className="fa fa-info-circle mr-1"></i>
                    请使用企业微信扫描二维码登录
                  </p>
                )}
                {scanStatus === 'scanned' && (
                  <p className="text-green-600 flex items-center justify-center">
                    <i className="fa fa-check-circle mr-1"></i>
                    已扫描，请在手机上确认
                  </p>
                )}
              </div>
              
              {/* 刷新按钮 - 仅在扫描状态显示 */}
              {scanStatus === 'scanning' && (
                <button 
                  onClick={refreshQrcode}
                  className="mt-4 text-sm text-blue-600 hover:text-blue-800 transition-colors flex items-center"
                >
                  <i className="fa fa-refresh mr-1"></i>
                  刷新二维码
                </button>
              )}
            </div>
          </div>
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