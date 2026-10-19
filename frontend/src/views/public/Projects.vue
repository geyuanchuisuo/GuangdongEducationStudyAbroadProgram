<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Search } from '@element-plus/icons-vue'
import SectionTitle from '../../components/SectionTitle.vue'
import { platformApi } from '../../api/platform'

const router = useRouter()
const keyword = ref('')
const category = ref('全部')
const projects = ref<any[]>([])

// v6.11.33：分类筛选项改为按接口返回的分类动态生成。
// 原先写死 ['全部','德国双元制','新加坡本硕','国际留学','国际研学']，一旦后端分类口径变化
// （例如返回"语言培训/学科辅导"），点了筛选必然为空，页面看起来像"没数据"。
const categories = computed(() => {
  const firstId = new Map<string, number>()
  for (const item of projects.value) {
    if (!item.category) continue
    const id = Number(item.id ?? 0)
    firstId.set(item.category, Math.min(firstId.get(item.category) ?? id, id))
  }
  return ['全部', ...[...firstId.entries()].sort((a, b) => a[1] - b[1]).map(([name]) => name)]
})

// v6.10.0：课程列表接真实 GET /cs/courses（platformApi 内映射页面形状、失败回落演示数据）
onMounted(async () => {
  projects.value = await platformApi.projects()
})

const filtered = computed(() => projects.value.filter((item) =>
  (category.value === '全部' || item.category === category.value) &&
  (!keyword.value || item.title.includes(keyword.value) || item.summary.includes(keyword.value)),
))
</script>

<template>
  <div class="page-wrap">
    <SectionTitle eyebrow="PROGRAMS" title="业务项目" desc="按目标、学历和时间规划查看适合的教育路径。" />
    <div class="filter-bar surface">
      <el-input v-model="keyword" :prefix-icon="Search" placeholder="搜索项目名称或关键词" clearable />
      <el-radio-group v-model="category">
        <el-radio-button v-for="item in categories" :key="item" :value="item">{{ item }}</el-radio-button>
      </el-radio-group>
    </div>
    <div class="projects">
      <article v-for="item in filtered" :key="item.id" class="surface project">
        <div class="project-head"><span>{{ item.category }}</span><b>{{ item.tag }}</b></div>
        <h2>{{ item.title }}</h2><p>{{ item.summary }}</p>
        <dl><div><dt>适合人群</dt><dd>{{ item.audience }}</dd></div><div><dt>项目周期</dt><dd>{{ item.duration }}</dd></div><div><dt>费用说明</dt><dd>{{ item.fee }}</dd></div></dl>
        <div class="highlights"><span v-for="text in item.highlights" :key="text">{{ text }}</span></div>
        <el-button type="primary" round @click="router.push('/projects/' + item.id)">查看项目详情 <el-icon><ArrowRight /></el-icon></el-button>
      </article>
    </div>
  </div>
</template>

<style scoped>
.filter-bar { display: flex; gap: 18px; align-items: center; padding: 18px; margin-bottom: 24px; }
.projects { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.project { padding: 30px; }
.project-head { display: flex; justify-content: space-between; color: var(--violet); }
.project-head b { padding: 5px 10px; color: var(--ink-deep); background: var(--mint); border-radius: 999px; }
.project h2 { margin: 22px 0 12px; color: var(--ink-deep); }
.project > p { min-height: 58px; color: var(--muted); line-height: 1.8; }
.project dl { margin: 22px 0; border-top: 1px solid var(--line); }
.project dl div { display: grid; grid-template-columns: 100px 1fr; gap: 15px; padding: 13px 0; border-bottom: 1px solid var(--line); }
.project dt { color: var(--muted); }
.project dd { margin: 0; color: var(--ink-deep); font-weight: 700; }
.highlights { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 22px; }
.highlights span { padding: 7px 10px; color: var(--violet); background: #efeffa; border-radius: 8px; font-size: 12px; }
@media (max-width: 850px) { .filter-bar, .projects { grid-template-columns: 1fr; flex-direction: column; align-items: stretch; } }
</style>

