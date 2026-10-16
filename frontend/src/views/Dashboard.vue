<script setup lang="ts">
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
</script>

<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>工作台</span>
          </template>
          <p>欢迎使用粤教留学项目管理平台</p>
          <p>当前用户: {{ userStore.userInfo?.real_name }} ({{ userStore.userType }})</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  padding: 10px;
}
</style>
