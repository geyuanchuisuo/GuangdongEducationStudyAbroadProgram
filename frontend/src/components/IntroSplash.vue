<script setup lang="ts">
import { onMounted, ref } from 'vue'
const emit = defineEmits<{ done: [] }>()
const leaving = ref(false)

onMounted(() => {
  if (sessionStorage.getItem("introSeen")) {
    emit("done")
    return
  }
  sessionStorage.setItem("introSeen","1")
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const delay = reduce ? 80 : 1850
  window.setTimeout(() => {
    leaving.value = true
    window.setTimeout(() => emit('done'), reduce ? 20 : 320)
  }, delay)
})
</script>

<template>
  <div class="intro" :class="{ leaving }">
    <div class="intro-grid"></div>
    <div class="intro-mark">
      <span class="mark-a"></span>
      <span class="mark-b"></span>
      <span class="mark-c"></span>
    </div>
    <p class="intro-kicker">GUANGDONG EDUCATION · SINCE 1981</p>
    <h1>粤教留学</h1>
    <p class="intro-sub">让每一次留学选择，都有专业支撑</p>
    <div class="intro-line"><span></span></div>
  </div>
</template>

<style scoped>
.intro {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  color: #fff;
  background: #2d2b73;
  transition: opacity .32s ease, transform .32s ease;
}
.intro.leaving { opacity: 0; transform: scale(1.03); pointer-events: none; }
.intro-grid {
  position: absolute;
  inset: 0;
  opacity: .18;
  background-image: linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: linear-gradient(to bottom, transparent, black 35%, transparent);
}
.intro-mark {
  width: 82px;
  height: 82px;
  position: relative;
  margin-bottom: 8px;
}
.mark-a, .mark-b, .mark-c { position: absolute; border: 3px solid #8dd933; transform: rotate(45deg); }
.mark-a { inset: 11px; }
.mark-b { inset: 22px; border-color: #fff; }
.mark-c { inset: 33px; border-color: #ffc634; }
.intro-kicker { margin: 0; letter-spacing: 4px; font-size: 12px; color: #c9c8ee; }
h1 { margin: 0; font-size: clamp(44px, 8vw, 88px); letter-spacing: 8px; }
.intro-sub { margin: 0; color: #dcdcf7; font-size: 18px; }
.intro-line { width: 220px; height: 3px; background: #4b4889; overflow: hidden; margin-top: 18px; }
.intro-line span { display: block; width: 45%; height: 100%; background: #8dd933; animation: move 1.2s ease-in-out infinite; }
@keyframes move { 0% { transform: translateX(-110%); } 100% { transform: translateX(250%); } }
@media (prefers-reduced-motion: reduce) {
  .intro-line span { animation: none; width: 100%; }
}
</style>

