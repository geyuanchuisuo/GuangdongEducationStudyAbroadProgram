<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SectionTitle from '../../components/SectionTitle.vue'
import { platformApi } from '../../api/platform'

// v6.11.23：政策资讯接库（GET /cs/policies），失败才降级演示数据
// v6.11.33：「查看完整指南」原先是个没有绑定任何事件的裸按钮，点了必然没反应。
// 政策正文 content 本来就随列表接口一起返回（platform.ts 已映射），因此直接弹窗展示，
// 不新增详情接口。
const country = ref('全部')
const list = ref<any[]>([])
onMounted(async () => {
  list.value = await platformApi.policies()
})
// 筛选项按接口实际返回的国家动态生成，避免写死口径与数据不一致（与业务项目页同一处理方式）
const countries = computed(() => {
  const names: string[] = []
  for (const item of list.value) {
    if (item.country && !names.includes(item.country)) names.push(item.country)
  }
  return ['全部', ...names]
})
const filtered = computed(() => list.value.filter((item) => country.value === '全部' || item.country === country.value))
const active = ref<any>(null)
const dialogVisible = computed({
  get: () => !!active.value,
  set: (value: boolean) => { if (!value) active.value = null },
})
</script>

<template>
  <div class="page-wrap">
    <SectionTitle eyebrow="POLICY INSIGHTS" title="留学政策资讯" desc="按国家和主题了解政策要点。详细申请要求以官方最新公告为准。" />
    <el-radio-group v-model="country" class="country-filter"><el-radio-button v-for="item in countries" :key="item" :value="item">{{ item }}</el-radio-button></el-radio-group>
    <el-empty v-if="!filtered.length" description="暂无政策资讯" />
    <div class="policy-grid">
      <article v-for="item in filtered" :key="item.title" class="surface policy">
        <div class="policy-head"><span>{{ item.country }}</span><time>{{ item.date }}</time></div>
        <h2>{{ item.title }}</h2><p>{{ item.summary }}</p>
        <el-button text type="primary" @click="active = item">查看完整指南</el-button>
      </article>
    </div>
    <el-dialog v-model="dialogVisible" :title="active?.title" width="720px" top="8vh">
      <div class="policy-dialog-head"><span>{{ active?.country }}</span><time>{{ active?.date }}</time></div>
      <p class="policy-dialog-body">{{ active?.content || '该政策的完整指南暂未提供，请联系顾问获取官方原文。' }}</p>
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
.policy-dialog-head { display: flex; justify-content: space-between; margin-bottom: 12px; color: var(--violet); font-weight: 800; }
.policy-dialog-head time { color: var(--muted); font-weight: 500; }
.policy-dialog-body { margin: 0; color: var(--ink-deep); line-height: 2; }
@media (max-width: 850px) { .policy-grid { grid-template-columns: 1fr; } }
</style>

