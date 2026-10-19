<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check, Phone } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projects as mockProjects } from '../../data/mock'
import { platformApi } from '../../api/platform'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const dialog = ref(false)
const submitting = ref(false)
// v6.11.33：改为 ref 整体替换真实数据。原先是 computed 直接返回 mock 数组里的对象，
// onMounted 里 Object.assign 到该对象上（普通对象、非响应式）不会触发重渲染，
// 详情页因此一直显示 mock 写死的学制/费用/人群，真实项目数据永远不生效。
const project = ref<any>(mockProjects.find((item) => item.id === Number(route.params.id)) || mockProjects[0])
const form = ref({ name: '', phone: '', note: '' })

onMounted(async () => {
  try {
    const list: any[] = await platformApi.projects()
    const hit = list.find((p) => p.id === Number(route.params.id))
    if (hit) project.value = hit
  } catch { /* 兜底 mock 项目 */ }
})

function apply() {
  if (!userStore.isLoggedIn) {
    sessionStorage.setItem('redirect-after-login', route.fullPath)
    ElMessageBox.confirm('报名项目需要先登录，登录后会自动返回当前项目继续报名。', '需要登录', { confirmButtonText: '去登录', cancelButtonText: '暂不登录' })
      .then(() => router.push({ path: '/login', query: { redirect: route.fullPath } }))
      .catch(() => undefined)
    return
  }
  form.value.name = userStore.userInfo?.real_name || ''
  form.value.phone = userStore.userInfo?.contact_info || ''
  dialog.value = true
}

function submit() {
  if (!form.value.name || !form.value.phone) {
    ElMessage.warning('请补充联系人和手机号')
    return
  }
  ElMessageBox.confirm('确认提交该项目的报名咨询吗？', '二次确认', { type: 'warning' })
    .then(async () => {
      submitting.value = true
      try {
        // v6.11.20：咨询落库 pending_lead 待补全线索（员工端可查询并合并为客户）
        await platformApi.createPendingLead({
          name: form.value.name,
          raw_info: `项目咨询：${project.value.title}；联系电话：${form.value.phone}；备注：${form.value.note || '无'}`,
        })
        try {
          const saved = JSON.parse(localStorage.getItem('my_consultations') || '[]')
          saved.unshift({ project: project.value.title, name: form.value.name, phone: form.value.phone, note: form.value.note, time: new Date().toLocaleString() })
          localStorage.setItem('my_consultations', JSON.stringify(saved.slice(0, 20)))
        } catch { /* 回执仅本地展示，失败不影响主流程 */ }
        dialog.value = false
        ElMessage.success('报名信息已提交，顾问将尽快联系你')
      } catch {
        ElMessage.error('提交失败，请稍后重试')
      } finally {
        submitting.value = false
      }
    })
    .catch(() => undefined)
}
</script>

<template>
  <div class="page-wrap detail">
    <el-button text :icon="ArrowLeft" @click="router.push('/projects')">返回项目列表</el-button>
    <header>
      <div><span class="badge">{{ project.category }} · {{ project.tag }}</span><h1>{{ project.title }}</h1></div>
      <div class="apply-box"><small>费用说明</small><strong>{{ project.fee }}</strong><el-button type="primary" size="large" round @click="apply">立即报名咨询</el-button></div>
    </header>
    <section class="content-grid">
      <article class="surface main-content">
        <h2>项目介绍</h2><p>{{ project.summary || '项目详情请咨询顾问。' }}</p>
        <h2>适合人群</h2><p>{{ project.audience }}</p>
        <template v-if="project.highlights && project.highlights.length">
          <h2>项目优势</h2>
          <div class="check-list"><div v-for="item in project.highlights" :key="item"><el-icon><Check /></el-icon>{{ item }}</div></div>
        </template>
        <h2>办理流程</h2>
        <ol><li>提交基本资料并完成适配评估</li><li>顾问确认项目和费用方案</li><li>准备申请材料与相关测试</li><li>完成录取、签证或入学衔接</li></ol>
      </article>
      <aside>
        <div class="surface side-card"><h3>项目关键信息</h3><p><span>项目周期</span><b>{{ project.duration }}</b></p><p><span>适合人群</span><b>{{ project.audience }}</b></p><p><span>服务范围</span><b>评估 · 申请 · 入学衔接</b></p></div>
        <div class="surface contact-card"><el-icon><Phone /></el-icon><h3>需要进一步了解？</h3><p>提交报名后由专属顾问联系，也可以直接拨打 020-37628058。</p></div>
      </aside>
    </section>
    <el-dialog v-model="dialog" title="项目报名咨询" width="min(520px, 92vw)">
      <el-form label-position="top"><el-form-item label="联系人"><el-input v-model="form.name" /></el-form-item><el-form-item label="手机号"><el-input v-model="form.phone" /></el-form-item><el-form-item label="补充说明"><el-input v-model="form.note" type="textarea" :rows="4" /></el-form-item></el-form>
      <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" :loading="submitting" @click="submit">确认提交</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.detail header { display: grid; grid-template-columns: 1fr 300px; gap: 32px; margin: 28px 0; }
.detail h1 { margin: 18px 0 12px; color: var(--ink-deep); font-size: clamp(38px, 5vw, 64px); }
.detail header p { max-width: 720px; color: var(--muted); line-height: 1.9; font-size: 18px; }
.apply-box { padding: 26px; color: #fff; background: var(--ink); border-radius: 20px; }
.apply-box small, .apply-box strong { display: block; }
.apply-box strong { margin: 12px 0 22px; color: #8dd933; font-size: 22px; }
.content-grid { display: grid; grid-template-columns: 1fr 320px; gap: 22px; }
.main-content { padding: 38px; }
.main-content h2 { margin: 32px 0 12px; color: var(--ink-deep); }
.main-content h2:first-child { margin-top: 0; }
.main-content p, .main-content li { color: var(--muted); line-height: 1.9; }
.check-list { display: grid; gap: 11px; }
.check-list div { display: flex; gap: 9px; align-items: center; color: var(--ink-deep); }
.check-list .el-icon { color: var(--lime); }
.side-card, .contact-card { padding: 25px; margin-bottom: 18px; }
.side-card p { display: flex; justify-content: space-between; gap: 15px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.side-card span { color: var(--muted); }
.side-card b { text-align: right; color: var(--ink-deep); }
.contact-card .el-icon { color: var(--lime); font-size: 30px; }
.contact-card p { color: var(--muted); line-height: 1.8; }
@media (max-width: 850px) { .detail header, .content-grid { grid-template-columns: 1fr; } }
</style>

