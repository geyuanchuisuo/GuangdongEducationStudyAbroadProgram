<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import {
  House,
  User,
  Briefcase,
  Reading,
  DataAnalysis,
  SwitchButton,
} from '@element-plus/icons-vue'

const userStore = useUserStore()
const router = useRouter()

const menuItems = computed(() => {
  const all = [
    { path: '/dashboard', title: '工作台', icon: House, types: ['PROSPECT', 'STUDENT', 'EMPLOYEE', 'MANAGER', 'ADMIN'] },
    { path: '/customer', title: '客户中心', icon: User, types: ['PROSPECT', 'ADMIN'] },
    { path: '/employee', title: '员工中心', icon: Briefcase, types: ['EMPLOYEE', 'MANAGER', 'ADMIN'] },
    { path: '/student', title: '学生中心', icon: Reading, types: ['STUDENT', 'ADMIN'] },
    { path: '/manager', title: '管理驾驶舱', icon: DataAnalysis, types: ['MANAGER', 'ADMIN'] },
  ]
  const ut = userStore.userType
  return all.filter((item) => item.types.includes(ut))
})

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="main-layout">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <h2>粤教留学</h2>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="welcome">欢迎, {{ userStore.userInfo?.real_name || '用户' }}</span>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleLogout">
            <span class="el-dropdown-link">
              {{ userStore.userInfo?.user_type || '' }}
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item :icon="SwitchButton">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.main-layout {
  height: 100vh;
}
.sidebar {
  background-color: #304156;
  overflow-y: auto;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}
.logo h2 {
  margin: 0;
  font-size: 18px;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e6e6e6;
  background: #fff;
}
.content {
  background-color: #f5f7fa;
}
.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
}
</style>
