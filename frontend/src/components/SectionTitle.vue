<script setup lang="ts">
defineProps<{ eyebrow?: string; title: string; desc?: string }>()
</script>

<template>
  <div class="section-title">
    <div>
      <p v-if="eyebrow">{{ eyebrow }}</p>
      <h2>{{ title }}</h2>
      <span v-if="desc">{{ desc }}</span>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.section-title { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; margin-bottom: 22px; }
.section-title p { margin: 0 0 7px; color: #80b717; font-weight: 800; letter-spacing: 2px; font-size: 12px; }
.section-title h2 { margin: 0; color: #25235e; font-size: clamp(26px, 3vw, 38px); }
.section-title span { display: block; margin-top: 8px; color: #7b7893; line-height: 1.7; }
@media (max-width: 700px) { .section-title { align-items: flex-start; flex-direction: column; } }
</style>

