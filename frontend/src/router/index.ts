import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
      },
      {
        path: 'customer',
        name: 'Customer',
        component: () => import('../views/customer/Index.vue'),
        meta: { userTypes: ['PROSPECT', 'ADMIN'] },
      },
      {
        path: 'employee',
        name: 'Employee',
        component: () => import('../views/employee/Index.vue'),
        meta: { userTypes: ['EMPLOYEE', 'MANAGER', 'ADMIN'] },
      },
      {
        path: 'student',
        name: 'Student',
        component: () => import('../views/student/Index.vue'),
        meta: { userTypes: ['STUDENT', 'ADMIN'] },
      },
      {
        path: 'manager',
        name: 'Manager',
        component: () => import('../views/manager/Index.vue'),
        meta: { userTypes: ['MANAGER', 'ADMIN'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  if (to.meta.guest && userStore.isLoggedIn) {
    next({ name: 'Dashboard' })
    return
  }

  if (to.meta.userTypes && Array.isArray(to.meta.userTypes)) {
    if (!userStore.userInfo) {
      userStore.fetchUserInfo().then(() => {
        if (userStore.userType && (to.meta.userTypes as string[]).includes(userStore.userType)) {
          next()
        } else {
          next({ name: 'Dashboard' })
        }
      }).catch(() => {
        next({ name: 'Login' })
      })
      return
    }
    if (!(to.meta.userTypes as string[]).includes(userStore.userType)) {
      next({ name: 'Dashboard' })
      return
    }
  }

  next()
})

export default router
