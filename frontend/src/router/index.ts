import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('../layouts/PublicLayout.vue'),
    children: [
      { path: '', name: 'Home', component: () => import('../views/public/Home.vue') },
      { path: 'company', name: 'Company', component: () => import('../views/public/Company.vue') },
      { path: 'projects', name: 'Projects', component: () => import('../views/public/Projects.vue') },
      { path: 'projects/:id', name: 'ProjectDetail', component: () => import('../views/public/ProjectDetail.vue') },
      { path: 'events', name: 'Events', component: () => import('../views/public/Events.vue') },
      { path: 'policies', name: 'Policies', component: () => import('../views/public/Policies.vue') },
      { path: 'faq', name: 'Faq', component: () => import('../views/public/Faq.vue') },
    ],
  },
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { guest: true } },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue'), meta: { guest: true } },
  {
    path: '/app/:role/:section?',
    component: () => import('../layouts/RoleLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'RoleWorkspace', component: () => import('../views/RoleWorkspace.vue') },
      { path: 'assessment-tool', name: 'AssessmentTool', component: () => import('../views/AssessmentTool.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFound.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// v6.11.52：发版后旧页面去动态加载已被删除的 chunk 会失败（Vite 构建会清空 dist 并更换 chunk 文件名），
// 表现就是「点击左侧导航没有任何反应」。这里统一捕获：先自动重载一次（10s 内不重复，避免死循环），
// 重载后仍失败则明确提示，避免这种静默失败让人误以为功能没接上。
const CHUNK_ERROR_RELOAD_KEY = 'chunk-error-reload-at'
router.onError((error: Error) => {
  const message = String(error?.message || '')
  if (!/dynamically imported module|Importing a module script failed|Failed to fetch/i.test(message)) return
  const lastReloadAt = Number(sessionStorage.getItem(CHUNK_ERROR_RELOAD_KEY) || 0)
  if (Date.now() - lastReloadAt > 10000) {
    sessionStorage.setItem(CHUNK_ERROR_RELOAD_KEY, String(Date.now()))
    window.location.reload()
    return
  }
  ElMessage.error('页面版本已更新，请刷新页面后重试')
})

router.beforeEach(async (to) => {
  const userStore = useUserStore()
  const requestedRole = String(to.params.role || '').toUpperCase()

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.meta.guest && userStore.isLoggedIn) {
    if (userStore.userType === 'ADMIN') {
      userStore.logout()
      return '/login'
    }
    return '/app/' + (userStore.userType || 'PROSPECT').toLowerCase() + '/home'
  }

  if (to.meta.requiresAuth && userStore.isLoggedIn && !userStore.userInfo) {
    try {
      await userStore.fetchUserInfo()
    } catch {
      return { name: 'Login' }
    }
  }

  if (to.meta.requiresAuth && userStore.userType === 'ADMIN') {
    userStore.logout()
    return '/login'
  }

  if (requestedRole && userStore.userType && requestedRole !== userStore.userType) {
    return '/app/' + userStore.userType.toLowerCase() + '/home'
  }

  return true
})

export default router