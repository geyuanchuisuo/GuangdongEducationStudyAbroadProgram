<script setup lang="ts">
defineProps<{ label: string; value: string; note?: string; tone?: string }>()
</script>

<template>
  <article class="stat-card">
    <span class="stat-dot" :class="tone || 'lime'"></span>
    <small>{{ label }}</small>
    <strong>{{ value }}</strong>
    <p v-if="note">{{ note }}</p>
  </article>
</template>

<style scoped>
.stat-card { position: relative; background: #fff; border-radius: 18px; padding: 20px; min-height: 124px; box-shadow: 0 10px 28px rgba(38,35,82,.08); }
.stat-dot { position: absolute; left: 20px; top: 22px; width: 11px; height: 11px; border-radius: 4px; }
.stat-dot.lime { background: #80b717; }
.stat-dot.purple { background: #5a50b8; }
.stat-dot.amber { background: #ffc634; }
.stat-dot.coral { background: #f06d63; }
.stat-card small { display: block; margin-left: 20px; color: #7b7893; font-size: 13px; }
.stat-card strong { display: block; margin-top: 12px; color: #2d2b73; font-size: 34px; line-height: 1; }
.stat-card p { margin: 8px 0 0; color: #7b7893; font-size: 12px; }
</style>

