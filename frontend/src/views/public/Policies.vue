<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SectionTitle from '../../components/SectionTitle.vue'
import { platformApi } from '../../api/platform'

// v6.11.23：政策资讯接库（GET /cs/policies），失败才降级演示数据
const country = ref('全部')
const countries = ['全部', '德国', '新加坡', '综合']
const list = ref<any[]>([])
onMounted(async () => {
  list.value = await platformApi.policies()
})
const filtered = computed(() => list.value.filter((item) => country.value === '全部' || item.country === country.value))
// 查看完整指南：展示 policy.content 全文（GET /cs/policies 已返回 content 字段，此前按钮无事件）
const detail = ref<any>(null)
const detailDialog = ref(false)
function openGuide(item: any) {
  detail.value = item
  detailDialog.value = true
}
</script>

<template>
  <div class="page-wrap">
    <SectionTitle eyebrow="POLICY INSIGHTS" title="留学政策资讯" desc="按国家和主题了解政策要点。详细申请要求以官方最新公告为准。" />
    <el-radio-group v-model="country" class="country-filter"><el-radio-button v-for="item in countries" :key="item" :value="item">{{ item }}</el-radio-button></el-radio-group>
    <div class="policy-grid">
      <article v-for="item in filtered" :key="item.title" class="surface policy">
        <div class="policy-head"><span>{{ item.country }}</span><time>{{ item.date }}</time></div>
        <h2>{{ item.title }}</h2><p>{{ item.summary }}</p>
        <el-button text type="primary" @click="openGuide(item)">查看完整指南</el-button>
      </article>
    </div>
    <el-dialog v-model="detailDialog" :title="detail?.title || '完整指南'" width="min(680px, 94vw)">
      <div class="policy-head"><span>{{ detail?.country }}</span><time>{{ detail?.date }}</time></div>
      <p class="policy-full">{{ detail?.content || detail?.summary }}</p>
    </el-dialog>
  </div>
</template>

<style scoped>
.country-filter { margin-bottom: 24px; }
.policy-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.policy { padding: 28px; border-top: 6px solid var(--lime); }
.policy:nth-child(2) { border-color: var(--amber); }.policy:nth-child(3) { border-color: var(--violet); }
.policy-head { display: flex; justify-content: space-between; color: var(--violet); font-weight: 800; }
.policy-head time { color: var(--muted); font-weight: 500; }
.policy h2 { margin: 26px 0 12px; font-size: 23px; color: var(--ink-deep); }
.policy p { min-height: 96px; color: var(--muted); line-height: 1.9; }
.policy-full { white-space: pre-wrap; line-height: 1.9; color: var(--muted); }
@media (max-width: 850px) { .policy-grid { grid-template-columns: 1fr; } }
</style>

