import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, getMe } from '../api/auth'

export interface UserInfo {
  id: number
  username: string
  real_name: string
  user_type: string
  employee_role?: string
  department?: string
}

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const userType = computed(() => userInfo.value?.user_type || '')

  async function login(username: string, password: string) {
    const res: any = await loginApi(username, password)
    token.value = res.access_token || res.data?.access_token
    localStorage.setItem('token', token.value)
    await fetchUserInfo()
  }

  async function fetchUserInfo() {
    const res: any = await getMe()
    userInfo.value = res.data || res
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
  }

  return { token, userInfo, isLoggedIn, userType, login, fetchUserInfo, logout }
})
