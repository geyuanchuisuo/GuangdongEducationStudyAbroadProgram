import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { getMe, login as loginApi } from '../api/auth'

export interface UserInfo {
  id: number
  username: string
  real_name: string
  user_type: string
  employee_role?: string
  department?: string
  contact_info?: string
  status?: string
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

  function loginDemo(role: string, name: string) {
    token.value = 'demo-token'
    userInfo.value = { id: 1, username: 'demo', real_name: name, user_type: role }
    localStorage.setItem('token', token.value)
    localStorage.setItem('demo-user', JSON.stringify(userInfo.value))
  }

  async function fetchUserInfo() {
    if (token.value === 'demo-token') {
      const saved = localStorage.getItem('demo-user')
      if (saved) userInfo.value = JSON.parse(saved)
      return
    }
    const res: any = await getMe()
    userInfo.value = res.data || res
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('demo-user')
  }

  return { token, userInfo, isLoggedIn, userType, login, loginDemo, fetchUserInfo, logout }
})

