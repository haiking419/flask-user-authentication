import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Home() {
  const [userInfo, setUserInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        const response = await fetch('/api/user_info')
        const data = await response.json()
        
        if (response.ok && data.success) {
          setUserInfo(data.user)
        } else {
          // 如果未登录，重定向到登录页
          navigate('/login')
        }
      } catch (err) {
        setError('获取用户信息失败')
        console.error('获取用户信息错误:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchUserInfo()
  }, [navigate])

  const handleLogout = async () => {
    try {
      await fetch('/api/logout', {
        method: 'POST'
      })
      // 清除用户信息并重定向到登录页
      setUserInfo(null)
      navigate('/login')
    } catch (err) {
      setError('登出失败')
      console.error('登出错误:', err)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <div className="loading-spinner"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container mx-auto mt-8">
        <div className="error-message">{error}</div>
        <button className="btn btn-primary mt-4" onClick={() => navigate('/login')}>
          返回登录
        </button>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <header className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800">
          <i className="fa fa-home mr-2"></i>欢迎回来
        </h1>
        <div className="flex items-center space-x-4">
          <div className="flex items-center">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
              <i className="fa fa-user"></i>
            </div>
            <span className="ml-2 font-medium">{userInfo?.username || '用户'}</span>
          </div>
          <button 
            onClick={handleLogout}
            className="text-gray-500 hover:text-gray-700 transition duration-200"
            title="退出登录"
          >
            <i className="fa fa-sign-out text-xl"></i>
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-lg text-gray-800">个人信息</h3>
            <span className="text-primary text-lg">
              <i className="fa fa-user-circle"></i>
            </span>
          </div>
          <div className="space-y-3">
            <p><span className="text-gray-500">显示名称:</span> {userInfo?.display_name || userInfo?.username || '未设置'}</p>
            <p><span className="text-gray-500">邮箱:</span> {userInfo?.email || '未设置'}</p>
            <p><span className="text-gray-500">注册时间:</span> {userInfo?.created_at ? new Date(userInfo.created_at).toLocaleString() : '未知'}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-lg text-gray-800">系统状态</h3>
            <span className="text-green-500 text-lg">
              <i className="fa fa-check-circle"></i>
            </span>
          </div>
          <div className="space-y-3">
            <p><span className="text-gray-500">状态:</span> 正常运行</p>
            <p><span className="text-gray-500">版本:</span> 1.0.0</p>
            <p><span className="text-gray-500">当前时间:</span> {new Date().toLocaleString()}</p>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 hover:shadow-md transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-lg text-gray-800">快速操作</h3>
            <span className="text-blue-500 text-lg">
              <i className="fa fa-bolt"></i>
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button className="btn btn-outline-secondary py-2 text-sm">
              <i className="fa fa-cog mr-1"></i> 设置
            </button>
            <button className="btn btn-outline-secondary py-2 text-sm">
              <i className="fa fa-question-circle mr-1"></i> 帮助
            </button>
            <button className="btn btn-outline-secondary py-2 text-sm">
              <i className="fa fa-history mr-1"></i> 历史
            </button>
            <button className="btn btn-outline-secondary py-2 text-sm">
              <i className="fa fa-envelope mr-1"></i> 消息
            </button>
          </div>
        </div>
      </div>

      <div className="mt-8 bg-white rounded-xl shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-800">欢迎使用系统</h2>
        <p className="text-gray-600 mb-4">
          您已成功登录系统。这是一个前后端分离的示例应用，使用React作为前端框架，
          后端提供RESTful API支持各种功能。
        </p>
        <div className="border-t pt-4">
          <h3 className="font-medium text-gray-700 mb-2">最近更新</h3>
          <ul className="space-y-2 text-gray-600">
            <li className="flex items-center">
              <i className="fa fa-check-circle text-green-500 mr-2"></i>
              前后端分离架构升级完成
            </li>
            <li className="flex items-center">
              <i className="fa fa-check-circle text-green-500 mr-2"></i>
              新增用户认证和授权功能
            </li>
            <li className="flex items-center">
              <i className="fa fa-check-circle text-green-500 mr-2"></i>
              系统性能优化和安全加固
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}

export default Home