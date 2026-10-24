<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu, User } from '@element-plus/icons-vue'
import AgentDock from '../components/AgentDock.vue'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const mobileOpen = ref(false)

function goCenter() {
  mobileOpen.value = false
  const role = userStore.userType.toLowerCase()
  router.push("/app/" + role + "/home")
}

function logout() {
  mobileOpen.value = false
  userStore.logout()
  router.push("/login")
}

const links = [
  { path: '/', label: '首页' },
  { path: '/company', label: '公司介绍' },
  { path: '/projects', label: '业务项目' },
  { path: '/events', label: '课程与活动' },
  { path: '/policies', label: '留学政策' },
  { path: '/faq', label: '常见问题' },
  { path: '/knowledge', label: '智能问答' },
]

function go(path: string) {
  mobileOpen.value = false
  router.push(path)
}
</script>

<template>
  <div class="public-shell">
    <header class="public-header">
      <button class="brand" @click="go('/')">
        <span class="brand-mark">粤</span>
        <span><b>粤教留学</b><small>Guangdong Education</small></span>
      </button>
      <nav :class="{ open: mobileOpen }">
        <button v-for="item in links" :key="item.path" :class="{ active: route.path === item.path }" @click="go(item.path)">
          {{ item.label }}
        </button>
      <div class="mobile-auth">
        <el-button v-if="!userStore.isLoggedIn" @click="go('/login')">登录</el-button>
        <el-button v-if="!userStore.isLoggedIn" type="primary" @click="go('/register')">注册</el-button>
        <el-button v-if="userStore.isLoggedIn" @click="goCenter">我的中心</el-button>
        <el-button v-if="userStore.isLoggedIn" @click="logout">退出登录</el-button>
      </div>
      </nav>
      <div class="header-actions">
        <el-button v-if="!userStore.isLoggedIn" text @click="go('/login')">登录</el-button>
        <el-button v-if="!userStore.isLoggedIn" type="primary" round @click="go('/register')">注册</el-button>
        <el-button v-else text :icon="User" @click="goCenter()">我的中心</el-button>
        <el-button v-if="userStore.isLoggedIn" text @click="logout">退出登录</el-button>
        <el-button class="mobile-menu" text :icon="Menu" @click="mobileOpen = !mobileOpen" />
      </div>
    </header>
    <main><router-view /></main>
    <footer class="public-footer">
      <div><b>粤教留学</b><p>广东省教育服务有限公司 · 专业、可靠的国际教育综合服务平台</p></div>
      <div><b>联系我们</b><p>020-37628058 · postmaster@ges1981.com</p><p>广州市越秀区东风东路723号高教大厦二楼</p></div>
      <div><b>快速入口</b><button @click="go('/projects')">项目咨询</button><button @click="go('/events')">近期活动</button></div>
    </footer>
    <AgentDock type="public" :auto-open="route.path === '/'" />
  </div>
</template>

<style scoped>
.public-shell { min-height: 100vh; background: #f7f7fb; }
.public-header { position: sticky; top: 0; z-index: 20; height: 76px; display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 0 max(24px, calc((100vw - 1220px) / 2)); background: rgba(255,255,255,.95); border-bottom: 1px solid #e7e5ef; }
.brand { display: flex; align-items: center; gap: 11px; border: 0; background: transparent; cursor: pointer; text-align: left; color: #25235e; }
.brand-mark { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px; color: #fff; background: #2d2b73; font-size: 23px; font-weight: 900; }
.brand b { display: block; font-size: 19px; }
.brand small { display: block; margin-top: 2px; color: #8a87a3; font-size: 10px; letter-spacing: 1px; }
nav { display: flex; gap: 4px; }
nav button { padding: 11px 13px; border: 0; border-radius: 10px; color: #66627e; background: transparent; cursor: pointer; }
nav button:hover, nav button.active { color: #2d2b73; background: #efeff9; font-weight: 700; }
.header-actions { display: flex; align-items: center; gap: 6px; }
.mobile-menu { display: none; }
main { min-height: calc(100vh - 280px); }
.mobile-auth { display: none; }
.public-footer { display: grid; grid-template-columns: 1.2fr 1fr .6fr; gap: 30px; padding: 54px max(24px, calc((100vw - 1220px) / 2)); background: #25235e; color: #dcdcf1; }
.public-footer p { margin: 10px 0 0; line-height: 1.8; color: #b8b7d5; font-size: 14px; }
.public-footer button { display: block; margin: 8px 0; padding: 0; border: 0; color: #fff; background: transparent; cursor: pointer; }
@media (max-width: 980px) {
  .public-header { padding: 0 18px; }
  nav { position: absolute; top: 76px; left: 16px; right: 16px; display: none; flex-direction: column; padding: 12px; border: 1px solid #e6e4ef; border-radius: 16px; background: #fff; box-shadow: 0 18px 45px rgba(37,35,94,.14); }
  nav.open { display: flex; }
  .mobile-menu { display: inline-flex; }
  .header-actions .el-button:not(.mobile-menu) { display: none; }
  .mobile-auth { display: flex; gap: 8px; padding: 8px 4px 2px; border-top: 1px solid #eee; }
  .public-footer { grid-template-columns: 1fr; padding: 42px 22px; }
}
</style>

