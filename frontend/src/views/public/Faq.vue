<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import SectionTitle from '../../components/SectionTitle.vue'
import { faqs } from '../../data/mock'

const keyword = ref('')
const filtered = computed(() => faqs.filter((item) => !keyword.value || item.q.includes(keyword.value) || item.a.includes(keyword.value)))
</script>

<template>
  <div class="page-wrap faq-page">
    <SectionTitle eyebrow="FAQ" title="常见问题" desc="快速了解公司、项目、报名和学生服务。" />
    <el-input v-model="keyword" :prefix-icon="Search" size="large" placeholder="搜索问题关键词" clearable />
    <div class="faq-list surface">
      <el-collapse>
        <el-collapse-item v-for="(item, index) in filtered" :key="item.q" :name="index">
          <template #title><span class="q-index">0{{ index + 1 }}</span><b>{{ item.q }}</b></template>
          <p>{{ item.a }}</p>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<style scoped>
.faq-page { max-width: 960px; }
.faq-list { margin-top: 22px; padding: 12px 28px; }
.q-index { margin-right: 18px; color: var(--lime); font-weight: 900; }
.faq-list :deep(.el-collapse-item__content) p { color: var(--muted); line-height: 1.9; padding: 0 38px 12px; }
</style>

