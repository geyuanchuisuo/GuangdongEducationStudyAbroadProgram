import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import router from '../router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
})

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    // 统一响应约定：HTTP 200，业务码 code:200 表示成功（见接口契约 §0.2）
    if (data.code === 200 || data.code === undefined) {
      return data
    }
    // 业务层未登录/Token 失效（后端以 HTTP 200 + 业务码返回）
    if (data.code === 40101 || data.code === 40102) {
      const userStore = useUserStore()
      userStore.logout()
      router.push('/login')
      ElMessage.error(data.message || '登录已过期，请重新登录')
      return Promise.reject(new Error(data.message || 'unauthorized'))
    }
    ElMessage.error(data.message || '请求失败')
    return Promise.reject(new Error(data.message || 'request failed'))
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const data = error.response.data
      if (status === 401 || data?.code === 40101) {
        const userStore = useUserStore()
        userStore.logout()
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
      } else if (status === 403) {
        ElMessage.error('没有权限执行此操作')
      } else {
        ElMessage.error(data?.message || `请求失败 (${status})`)
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    return Promise.reject(error)
  },
)

export default request
