import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
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