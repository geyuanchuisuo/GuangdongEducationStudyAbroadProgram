<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Location, User } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SectionTitle from '../../components/SectionTitle.vue'
import { events } from '../../data/mock'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const userStore = useUserStore()
const selected = ref<any>(null)

function apply(event: any) {
  if (event.status === '已结束' || event.status === '已满员' || event.status === '已取消') return
  if (!userStore.isLoggedIn) {
    sessionStorage.setItem('event-intent', String(event.id))
    ElMessageBox.confirm('活动报名需要登录，登录后会自动返回并恢复报名。', '需要登录', { confirmButtonText: '去登录', cancelButtonText: '暂不登录' })
      .then(() => router.push({ path: '/login', query: { redirect: '/events' } }))
      .catch(() => undefined)
    return
  }
  selected.value = event
}

function confirmApply() {
  ElMessageBox.confirm('确认报名“' + selected.value.title + '”吗？', '二次确认', { type: 'warning' })
    .then(() => { ElMessage.success('报名成功，可在个人中心查看'); selected.value = null })
    .catch(() => undefined)
}
</script>

<template>
  <div class="page-wrap">
    <SectionTitle eyebrow="EVENTS & LECTURES" title="课程活动" desc="查看近期讲座、开放日和招生说明会。所有报名均需登录。" />
    <div class="event-grid">
      <article v-for="item in events" :key="item.id" class="surface event-card">
        <div class="date"><b>{{ item.date.split('月')[1]?.replace('日','') || item.date }}</b><span>{{ item.date.includes('月') ? item.date.split('月')[0] + '月' : item.date }}</span></div>
        <div class="event-content">
          <el-tag effect="plain" :type="item.status === '已结束' ? 'info' : 'success'">{{ item.status }}</el-tag>
          <h2>{{ item.title }}</h2>
          <p><el-icon><Location /></el-icon>{{ item.format }}</p><p><el-icon><User /></el-icon>{{ item.speaker }}</p>
          <div class="capacity"><span>已报名 {{ item.joined }} / {{ item.capacity }}</span><el-progress :percentage="Math.round(item.joined / item.capacity * 100)" :show-text="false" /></div>
          <el-button type="primary" round :disabled="item.status === '已结束'" @click="apply(item)">{{ item.status === '已结束' ? '已结束' : '立即报名' }}</el-button>
        </div>
      </article>
    </div>
    <el-dialog v-model="selected" title="活动报名确认" width="min(520px, 92vw)">
      <div v-if="selected"><h3>{{ selected.title }}</h3><p class="muted">{{ selected.format }} · {{ selected.date }}</p><p>系统将使用你的账号资料生成本次报名记录，提交前可以修改。</p></div>
      <template #footer><el-button @click="selected = null">取消</el-button><el-button type="primary" @click="confirmApply">确认报名</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.event-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.event-card { display: grid; grid-template-columns: 92px 1fr; gap: 22px; padding: 26px; }
.date { display: grid; place-items: center; align-content: center; height: 100px; color: #fff; background: var(--ink); border-radius: 17px; }
.date b { font-size: 38px; line-height: 1; }.date span { color: #c9c8e5; margin-top: 5px; }
.event-content h2 { margin: 14px 0; color: var(--ink-deep); }
.event-content p { display: flex; align-items: center; gap: 7px; color: var(--muted); }
.capacity { margin: 18px 0; }.capacity span { display: block; margin-bottom: 6px; color: var(--muted); font-size: 12px; }
@media (max-width: 850px) { .event-grid { grid-template-columns: 1fr; } }
</style>

