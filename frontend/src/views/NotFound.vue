<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template><div class="not-found"><b>404</b><h1>页面不存在</h1><p>你访问的页面暂时找不到。</p><el-button type="primary" round @click="router.push('/')">返回首页</el-button></div></template>

<style scoped>
.not-found { min-height: 100vh; display: grid; place-items: center; align-content: center; background: var(--ink); color: #fff; text-align: center; }
.not-found b { color: #8dd933; font-size: 110px; line-height: 1; }.not-found h1 { margin: 12px 0; }.not-found p { color: #cfcee7; }
</style>

