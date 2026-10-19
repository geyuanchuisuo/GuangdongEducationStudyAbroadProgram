import axios, { type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import router from '../router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
})

// v6.11.47：统一提示出口。拦截器与页面 catch 都会报同一条业务错误（如 40901），
// 此前会弹成两条一模一样的提示；这里按文案做短时窗口去重，相同文案只弹一次。
let lastMessage = ''
let lastMessageAt = 0
const MESSAGE_DEDUPE_WINDOW = 1500

export function showMessage(type: 'success' | 'info' | 'warning' | 'error', message: string) {
  const now = Date.now()
  if (message === lastMessage && now - lastMessageAt < MESSAGE_DEDUPE_WINDOW) return
  lastMessage = message
  lastMessageAt = now
  ElMessage[type](message)
}

request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const userStore = useUserStore()
    if (userStore.token) config.headers.Authorization = 'Bearer ' + userStore.token
    return config
  },
  (error) => Promise.reject(error),
)

request.interceptors.response.use(
  (response: AxiosResponse) => {
    const data = response.data
    if (data.code === 200 || data.code === undefined) return data
    if (data.code === 40101 || data.code === 40102) {
      useUserStore().logout()
      router.push('/login')
      showMessage('error', data.message || '登录已过期，请重新登录')
      return Promise.reject(new Error(data.message || 'unauthorized'))
    }
    showMessage('error', data.message || '请求失败')
    // v6.11.52：给业务错误打上标记，便于页面 catch 区分「业务错误」（拦截器已弹出真实原因）
    // 与「网络/超时异常」，避免页面再用「接口未就绪」把真实原因覆盖掉。
    const businessError = new Error(data.message || 'request failed') as Error & { bizCode?: number }
    businessError.bizCode = data.code
    return Promise.reject(businessError)
  },
  (error) => {
    if (error.response?.status === 401) {
      useUserStore().logout()
      router.push('/login')
    }
    return Promise.reject(error)
  },
)

export default request

