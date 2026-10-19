<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Bell, Fold, House, SwitchButton, User } from '@element-plus/icons-vue'
import AgentDock from '../components/AgentDock.vue'
import { platformApi } from '../api/platform'
import { navigation, type Role } from '../config/navigation'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const collapsed = ref(false)
const role = computed(() => String(route.params.role || 'PROSPECT').toUpperCase() as Role)
const section = computed(() => (route.params.section as string) || 'home')
const items = computed(() => navigation[role.value] || [])
const roleLabel = computed(() => ({ PROSPECT: '意向客户', STUDENT: '留学生', EMPLOYEE: '员工', MANAGER: '管理层' }[role.value]))

// v6.11.50：顶栏铃铛原来是个没有点击事件的空按钮。现接通知中心（GET /notifications）：
// 红点显示未读数，点击弹出通知抽屉，支持单条/全部标记已读。四类角色共用同一套接口。
const notifOpen = ref(false)
const notifLoading = ref(false)
const notifUnread = ref(0)
const notifItems = ref<any[]>([])

async function loadNotifUnread() {
  try {
    const data: any = await platformApi.notificationsUnread()
    notifUnread.value = Number(data?.count || 0)
  } catch {}
}

async function openNotifications() {
  notifOpen.value = true
  notifLoading.value = true
  try {
    const data: any = await platformApi.notifications({ page_size: 20 })
    notifItems.value = data?.items || []
    notifUnread.value = notifItems.value.filter((item: any) => !item.is_read).length
  } catch {
    notifItems.value = []
  } finally {
    notifLoading.value = false
  }
}

async function readNotification(item: any) {
  if (item.is_read) return
  try {
    await platformApi.markNotificationRead(item.id)
    item.is_read = true
    notifUnread.value = Math.max(0, notifUnread.value - 1)
  } catch {}
}

async function readAllNotifications() {
  if (!notifUnread.value) return
  try {
    await platformApi.markAllNotificationsRead()
    notifItems.value.forEach((item: any) => { item.is_read = true })
    notifUnread.value = 0
  } catch {}
}

onMounted(async () => {
  if (!userStore.userInfo && userStore.token) await userStore.fetchUserInfo()
  await loadNotifUnread()
})

function select(item: { section: string }) {
  router.push('/app/' + role.value + '/' + item.section)
}

function logout() {
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="role-shell" :class="{ collapsed }">
    <aside class="role-sidebar">
      <div class="role-brand" @click="router.push('/')">
        <span>粤</span>
        <div v-if="!collapsed"><b>粤教留学</b><small>{{ roleLabel }}工作空间</small></div>
        <el-button v-else text :icon="Fold" @click="collapsed = false" />
      </div>
      <button class="collapse" @click="collapsed = !collapsed"><el-icon><Fold /></el-icon><span v-if="!collapsed">收起导航</span></button>
      <div class="role-menu">
        <button v-for="item in items" :key="item.key" :class="{ active: section === item.section }" @click="select(item)">
          <el-icon><component :is="item.icon" /></el-icon><span v-if="!collapsed">{{ item.label }}</span>
        </button>
      </div>
      <button class="logout" @click="logout"><el-icon><SwitchButton /></el-icon><span v-if="!collapsed">退出登录</span></button>
    </aside>
    <section class="role-content">
      <header class="role-topbar">
        <div><p>{{ roleLabel }} · {{ items.find((item) => item.section === section)?.label || '工作空间' }}</p><h1>{{ userStore.userInfo?.real_name || '欢迎回来' }}</h1></div>
        <div class="top-actions">
          <el-button text :icon="House" @click="router.push('/')">返回官网</el-button><el-badge :value="notifUnread" :hidden="!notifUnread" :max="99"><el-button text :icon="Bell" @click="openNotifications" /></el-badge>
          <el-avatar :size="38"><el-icon><User /></el-icon></el-avatar>
        </div>
      </header>
      <main class="role-main"><router-view /></main>
    </section>
    <el-drawer v-model="notifOpen" title="通知中心" size="380px">
      <div class="notif-head"><span>共 {{ notifItems.length }} 条，未读 {{ notifUnread }} 条</span><el-button size="small" :disabled="!notifUnread" @click="readAllNotifications">全部标记已读</el-button></div>
      <div v-loading="notifLoading" class="notif-list">
        <div v-for="item in notifItems" :key="item.id" class="notif-row" :class="{ unread: !item.is_read }" @click="readNotification(item)">
          <div class="notif-row-head"><b>{{ item.title || '系统通知' }}</b><el-tag v-if="!item.is_read" type="danger" size="small" effect="light">未读</el-tag></div>
          <p>{{ item.content || '—' }}</p>
          <small>{{ item.type || 'system' }} · {{ String(item.created_at || '').replace('T', ' ').slice(0, 16) || '—' }}</small>
        </div>
        <el-empty v-if="!notifLoading && !notifItems.length" description="暂无通知" :image-size="70" />
      </div>
    </el-drawer>
    <AgentDock :type="role === 'STUDENT' ? 'student' : role === 'EMPLOYEE' ? 'employee' : role === 'MANAGER' ? 'manager' : 'public'" />
  </div>
</template>

<style scoped>
.role-shell { display: flex; min-height: 100vh; background: #f3f3f8; }
.role-sidebar { width: 248px; flex: 0 0 248px; display: flex; flex-direction: column; padding: 22px 16px; background: #fff; border-right: 1px solid #e4e4ed; transition: width .2s; }
.collapsed .role-sidebar { width: 82px; flex-basis: 82px; }
.role-brand { display: flex; align-items: center; gap: 11px; min-height: 54px; padding: 0 8px; color: #25235e; }
.role-brand > span { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px; color: #fff; background: #2d2b73; font-size: 21px; font-weight: 900; }
.role-brand b { display: block; }
.role-brand small { display: block; color: #8c89a1; margin-top: 3px; }
.collapse, .logout, .role-menu button { display: flex; align-items: center; gap: 11px; border: 0; cursor: pointer; color: #6c6982; background: transparent; }
.collapse { margin: 18px 8px 12px; padding: 9px; border-radius: 10px; }
.role-menu { display: grid; gap: 5px; margin-top: 8px; }
.role-menu button { width: 100%; padding: 12px 13px; border-radius: 12px; text-align: left; }
.role-menu button:hover, .role-menu button.active { color: #2d2b73; background: #efeff9; font-weight: 800; }
.logout { margin: auto 8px 6px; padding: 11px 13px; border-radius: 12px; }
.role-content { min-width: 0; flex: 1; }
.role-topbar { display: flex; justify-content: space-between; align-items: center; min-height: 92px; padding: 18px 32px; background: #fff; border-bottom: 1px solid #e6e5ee; }
.role-topbar p { margin: 0; color: #8b88a1; font-size: 13px; }
.role-topbar h1 { margin: 5px 0 0; color: #25235e; font-size: 25px; }
.top-actions { display: flex; align-items: center; gap: 13px; }
.role-main { padding: 30px 32px 60px; }
.notif-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; color: #8b88a1; font-size: 13px; }
.notif-list { display: grid; gap: 10px; }
.notif-row { padding: 12px 14px; border: 1px solid #e6e5ee; border-radius: 12px; cursor: pointer; background: #fff; }
.notif-row:hover { border-color: #c9c7ea; }
.notif-row.unread { background: #f6f5ff; border-color: #d6d3f2; }
.notif-row-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.notif-row p { margin: 6px 0 6px; color: #5f5c78; font-size: 13px; }
.notif-row small { color: #9a97ad; }
@media (max-width: 900px) {
  .role-sidebar { width: 82px; flex-basis: 82px; padding: 18px 10px; }
  .role-brand div, .collapse span, .role-menu span, .logout span { display: none; }
  .role-topbar, .role-main { padding-left: 18px; padding-right: 18px; }
}
</style>

