<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, Phone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const form = ref({ phone: '', password: '' })

async function login() {
  if (!form.value.phone || !form.value.password) return
  loading.value = true
  try {
    await userStore.login(form.value.phone, form.value.password)
    const redirect = (route.query.redirect as string) || sessionStorage.getItem('redirect-after-login') || '/app/' + userStore.userType.toLowerCase()
    sessionStorage.removeItem('redirect-after-login')
    router.push(redirect)
    ElMessage.success('登录成功')
  } catch {
    ElMessage.error('登录失败，请检查手机号和密码')
  } finally {
    loading.value = false
  }
}

</script>

<template>
  <div class="auth-shell">
    <aside class="auth-art"><div><small>WELCOME BACK</small><h1>专业服务<br />从一次登录开始</h1><p>登录后继续项目报名、学生服务或企业工作流。</p></div></aside>
    <main class="auth-panel">
      <div class="auth-card"><router-link to="/" class="back-home">← 返回官网首页</router-link><span class="badge">粤教留学 · 统一登录</span><h2>欢迎回来</h2><p class="muted">使用手机号和密码登录。</p>
        <el-form label-position="top" @submit.prevent="login">
          <el-form-item label="手机号"><el-input v-model="form.phone" size="large" :prefix-icon="Phone" placeholder="请输入手机号" /></el-form-item>
          <el-form-item label="密码"><el-input v-model="form.password" size="large" :prefix-icon="Lock" type="password" show-password placeholder="请输入密码" /></el-form-item>

          <el-button type="primary" size="large" :loading="loading" native-type="submit" style="width:100%">登录</el-button>
        </el-form>
        <div class="auth-foot"><router-link to="/register">还没有账号？立即注册</router-link></div>

      </div>
    </main>
  </div>
</template>

<style scoped>
.auth-shell { min-height: 100vh; display: grid; grid-template-columns: 1.05fr .95fr; background: #f3f3f8; }
.auth-art { display: flex; align-items: flex-end; padding: 70px; color: #fff; background: var(--ink); position: relative; overflow: hidden; }
.auth-art::before, .auth-art::after { content: ''; position: absolute; border: 3px solid #6c67c1; transform: rotate(38deg); }
.auth-art::before { width: 440px; height: 440px; right: -100px; top: 70px; }
.auth-art::after { width: 250px; height: 250px; left: 70px; top: 110px; border-color: #8dd933; }
.auth-art small { color: #8dd933; letter-spacing: 4px; font-weight: 900; }
.auth-art h1 { margin: 18px 0; font-family: Georgia, serif; font-size: clamp(50px, 6vw, 82px); line-height: 1.05; }
.auth-art p { color: #d5d4ec; font-size: 18px; line-height: 1.8; }
.auth-panel { display: grid; place-items: center; padding: 32px; }
.auth-card { width: min(470px, 100%); padding: 38px; background: #fff; border-radius: 24px; box-shadow: var(--shadow); }
.auth-card h2 { margin: 18px 0 8px; color: var(--ink-deep); font-size: 36px; }
.auth-foot { margin-top: 18px; display: flex; align-items: center; justify-content: center; gap: 10px; text-align: center; color: var(--violet); }
/* v6.11.42：返回官网首页改为卡片顶部实心胶囊按钮，原页脚小字链接太不显眼 */
.back-home { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 14px; padding: 9px 20px; font-size: 14px; font-weight: 800; color: #fff; background: var(--violet); border-radius: 999px; box-shadow: 0 8px 20px rgba(108, 103, 193, .35); transition: transform .2s, box-shadow .2s; }
.back-home:hover { color: #fff; transform: translateY(-1px); box-shadow: 0 12px 26px rgba(108, 103, 193, .45); }
@media (max-width: 850px) { .auth-shell { grid-template-columns: 1fr; }.auth-art { display: none; } }
</style>

