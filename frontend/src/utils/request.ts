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
      ElMessage.error(data.message || '登录已过期，请重新登录')
      return Promise.reject(new Error(data.message || 'unauthorized'))
    }
    ElMessage.error(data.message || '请求失败')
    return Promise.reject(new Error(data.message || 'request failed'))
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

