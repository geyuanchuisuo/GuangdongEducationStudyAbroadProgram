<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { register } from '../api/auth'

const router = useRouter()
const loading = ref(false)
const form = ref({ real_name: '', gender: '', age: '', phone: '', education: '', career: '', german: '', password: '', confirm: '', code: '' })

async function submit() {
  const f = form.value
  if (!f.real_name || !f.gender || !f.age || !f.phone || !f.education || !f.password) {
    ElMessage.warning('请填写所有必填项')
    return
  }
  if (f.password !== f.confirm) { ElMessage.warning('两次密码输入不一致'); return }
  loading.value = true
  try {
    await register({ username: f.phone, password: f.password, real_name: f.real_name, user_type: 'PROSPECT', contact_info: f.phone })
    ElMessage.success('注册成功，账号状态为待开通')
    router.push('/login')
  } catch {
    ElMessage.error('注册失败，请稍后重试')
  } finally { loading.value = false }
}
</script>

<template>
  <div class="register-shell">
    <section class="register-intro"><span class="badge">30秒注册</span><h1>开启专属<br />留学规划</h1><p>注册后账号进入待开通状态，由员工审核后开放完整服务。</p><ul><li>课程与项目预约</li><li>活动报名</li><li>咨询进度查询</li></ul></section>
    <main class="register-panel">
      <div class="register-card"><h2>创建账号</h2><p class="muted">必填 5 项基础资料 · 账号密码必填 · 选填 2 项</p>
        <el-form label-position="top" @submit.prevent="submit">
          <div class="form-grid">
            <el-form-item label="姓名" required><el-input v-model="form.real_name" /></el-form-item>
            <el-form-item label="性别" required><el-select v-model="form.gender" style="width:100%"><el-option label="男" value="男" /><el-option label="女" value="女" /></el-select></el-form-item>
            <el-form-item label="年龄" required><el-input v-model="form.age" /></el-form-item>
            <el-form-item label="手机号" required><el-input v-model="form.phone" /></el-form-item>
            <el-form-item label="最高学历" required><el-select v-model="form.education" style="width:100%"><el-option v-for="item in ['初中及以下','高中/中专','大专','本科','硕士','博士']" :key="item" :label="item" :value="item" /></el-select></el-form-item>

            <el-form-item label="职业 / 专业需求（选填）"><el-input v-model="form.career" /></el-form-item>
            <el-form-item label="德语能力（选填）"><el-select v-model="form.german" style="width:100%"><el-option v-for="item in ['零基础','A1-A2','B1-B2','C1及以上']" :key="item" :label="item" :value="item" /></el-select></el-form-item>
            <el-form-item label="设置密码" required><el-input v-model="form.password" type="password" show-password /></el-form-item>
            <el-form-item label="确认密码" required><el-input v-model="form.confirm" type="password" show-password /></el-form-item>
          </div>
          <el-button type="primary" size="large" :loading="loading" native-type="submit" style="width:100%">提交注册</el-button>
        </el-form>
        <p class="agreement">提交即表示同意《服务协议》与《隐私政策》。<router-link to="/login">已有账号，去登录</router-link></p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.register-shell { min-height: 100vh; display: grid; grid-template-columns: .75fr 1.25fr; }
.register-intro { padding: 70px; color: #fff; background: var(--ink); }
.register-intro h1 { margin: 26px 0 18px; font-family: Georgia, serif; font-size: 65px; line-height: 1.08; }
.register-intro p { color: #d2d1eb; line-height: 1.8; font-size: 18px; }
.register-intro ul { margin-top: 38px; padding: 0; list-style: none; display: grid; gap: 15px; }
.register-intro li::before { content: '✓'; display: inline-grid; place-items: center; width: 25px; height: 25px; margin-right: 10px; color: var(--ink); background: #8dd933; border-radius: 50%; }
.register-panel { display: grid; place-items: center; padding: 35px; }
.register-card { width: min(760px, 100%); padding: 36px; background: #fff; border-radius: 24px; box-shadow: var(--shadow); }
.register-card h2 { margin: 0; color: var(--ink-deep); font-size: 35px; }
.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 18px; margin: 22px 0; }
.agreement { color: var(--muted); text-align: center; font-size: 12px; }.agreement a { color: var(--violet); }
@media (max-width: 850px) { .register-shell { grid-template-columns: 1fr; }.register-intro { display: none; }.form-grid { grid-template-columns: 1fr; } }
</style>

