<script setup lang="ts">
import { ref } from 'vue'
import IntroSplash from './components/IntroSplash.vue'

const introVisible = ref(true)
</script>

<template>
  <IntroSplash v-if="introVisible" @done="introVisible = false" />
  <router-view v-else />
</template>

