<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ChatDotRound, Close, Promotion } from '@element-plus/icons-vue'
import { platformApi } from '../api/platform'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const props = defineProps<{ type?: 'public' | 'student' | 'employee' | 'manager'; autoOpen?: boolean }>()
const open = ref(false)
watch(() => props.autoOpen, (value) => {
  if (value) window.setTimeout(() => { open.value = true }, 450)
}, { immediate: true })
const input = ref('')
const sessionId = ref('new')
const messages = ref<Array<{ role: 'user' | 'agent'; text: string; recs?: AnyRec[]; faq?: any; register?: any }>>([])
// v6.10.3：客服窗（public 类型）首次打开时拉取后端开场白并插入消息流；
// 仅 public 分支启用，student/employee/manager 窗口行为不变
watch(open, async (value) => {
  if (!value || messages.value.length > 0) return
  if (props.type === 'student' || props.type === 'employee' || props.type === 'manager') return
  try {
    const data: any = await platformApi.csGreeting()
    if (data?.greeting) messages.value.push({ role: 'agent', text: data.greeting })
  } catch { /* 后端未就绪时静默降级，不阻塞正常聊天 */ }
})
const messageList = ref<HTMLElement | null>(null)
watch(messages, async () => {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}, { deep: true })
const name = computed(() => {
  if (props.type === 'student') return '粤伴 · 学生智能助手'
  if (props.type === 'employee' || props.type === 'manager') return '粤助 · 企业智能助手'
  return '小粤 · 智能留学顾问'
})

const quick = computed(() => {
  if (props.type === 'student') return ['帮我列个学习计划', '我想请个假', '查看最近DDL']
  if (props.type === 'employee' || props.type === 'manager') return ['看看今天待办', '帮我整理日报', '查询客户状态']
  return ['推荐适合我的项目', '近期有什么活动', '咨询报名条件']
})

interface AnyRec { name?: string; project?: string; type?: string }

function goRec(rec: AnyRec) {
  router.push(rec.type === 'event' ? '/events' : '/projects')
}

async function send(text = input.value) {
  const value = text.trim()
  if (!value) return
  messages.value.push({ role: 'user', text: value })
  input.value = ''
  try {
    let reply = ''
    let recs: AnyRec[] | undefined
    let faq: any = undefined
    let register: any = undefined
    if (props.type === 'student') {
      const result: any = await platformApi.student.agentChat({ message: value, session_id: sessionId.value })
      sessionId.value = result?.session_id || sessionId.value
      reply = result?.reply || reply
    } else if (props.type === 'employee' || props.type === 'manager') {
      const result: any = await platformApi.employee.agentChat({ message: value, session_id: sessionId.value })
      sessionId.value = result?.session_id || sessionId.value
      reply = result?.reply || reply
    } else {
      const result: any = await platformApi.csChat({
        message: value,
        conversation_id: sessionId.value === 'new' ? null : sessionId.value,
        user_id: userStore.userInfo?.id ?? null,
      })
      sessionId.value = result?.conversation_id || sessionId.value
      reply = result?.answer || reply
      recs = result?.recommendations || undefined
      const card: any = result?.card_data
      faq = card?.faq || undefined
      register = card?.register || undefined
    }
    if (!reply) reply = '当前助手服务未返回内容，请稍后重试。'
    messages.value.push({ role: 'agent', text: reply, recs, faq, register })
  } catch {
    messages.value.push({ role: 'agent', text: '当前助手服务暂不可用，请稍后重试。' })
  }
}
</script>

<template>
  <div class="agent-dock">
    <transition name="fade">
      <section v-if="open" class="agent-panel">
        <header>
          <div>
            <strong>{{ name }}</strong>
            <small>在线 · 实时服务</small>
          </div>
          <el-button text :icon="Close" @click="open = false" />
        </header>
        <div ref="messageList" class="messages">
          <div v-for="(item, index) in messages" :key="index" class="message" :class="[item.role, { latest: index === messages.length - 1 }]">
            {{ item.text }}
            <div v-if="item.recs?.length" class="rec-cards">
              <button v-for="(rec, ri) in item.recs" :key="ri" class="rec-card" @click="goRec(rec)">
                <el-tag size="small" :type="rec.type === 'event' ? 'warning' : 'success'" effect="plain">{{ rec.type === 'event' ? '活动' : '课程' }}</el-tag>
                <span>{{ rec.name || rec.project }}</span>
              </button>
            </div>
            <div v-if="item.faq" class="faq-card">
              <div class="faq-tag">常见问题</div>
              <div class="faq-q">{{ item.faq.question }}</div>
              <div class="faq-a">{{ item.faq.answer }}</div>
            </div>
            <div v-if="item.register" class="register-card" :class="item.register.status">
              <div class="reg-title">
                <el-tag size="small" :type="item.register.status === 'success' ? 'success' : item.register.status === 'need_login' ? 'warning' : item.register.status === 'incomplete' ? 'info' : 'danger'">
                  {{ item.register.status === 'success' ? '报名成功' : item.register.status === 'need_login' ? '需登录' : item.register.status === 'incomplete' ? '信息不全' : '报名失败' }}
                </el-tag>
              </div>
              <div class="reg-msg">{{ item.register.message }}</div>
              <el-button v-if="item.register.status === 'need_login'" size="small" type="primary" @click="router.push('/login')">去登录</el-button>
            </div>
          </div>
        </div>
        <div class="quick">
          <el-button v-for="item in quick" :key="item" size="small" round @click="send(item)">{{ item }}</el-button>
        </div>
        <div class="composer">
          <el-input v-model="input" placeholder="输入你的问题..." @keyup.enter="send()" />
          <el-button type="primary" :icon="Promotion" @click="send()" />
        </div>
      </section>
    </transition>
    <el-button class="agent-trigger" type="primary" :icon="ChatDotRound" circle size="large" @click="open = !open" />
  </div>
</template>

<style scoped>
.agent-dock { position: fixed; right: 24px; bottom: 24px; z-index: 1000; }
.agent-trigger { width: 58px; height: 58px; box-shadow: 0 12px 30px rgba(45,43,115,.28); }
.agent-panel {
  position: absolute;
  right: 0;
  bottom: 72px;
  width: min(380px, calc(100vw - 32px));
  height: 540px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e4e2ef;
  border-radius: 22px;
  box-shadow: 0 24px 60px rgba(37,35,94,.22);
  overflow: hidden;
}
header { display: flex; justify-content: space-between; align-items: center; padding: 18px 20px; background: #2d2b73; color: #fff; }
header small { display: block; margin-top: 4px; color: #cfcdf1; }
.messages { flex: 1; padding: 18px; overflow: auto; background: #f7f7fb; }
.message { max-width: 82%; margin: 10px 0; padding: 11px 14px; border-radius: 14px; line-height: 1.65; font-size: 14px; }
.message.agent { background: #fff; border: 1px solid #e8e6f1; }
.message.user { margin-left: auto; background: #5a50b8; color: #fff; }
.message.latest { box-shadow: 0 8px 20px rgba(45,43,115,.12); }
.message.latest::after { content: "最新"; display: block; margin-top: 5px; font-size: 10px; opacity: .65; }
.rec-cards { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
.rec-card {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  background: #f7f7fb; border: 1px solid #e8e6f1; border-radius: 10px;
  font-size: 13px; cursor: pointer; text-align: left; color: inherit;
}
.rec-card:hover { border-color: #5a50b8; }
.faq-card { margin-top: 10px; padding: 10px 12px; background: #f0f9eb; border: 1px solid #e1f3d8; border-radius: 10px; }
.faq-tag { display: inline-block; font-size: 11px; color: #67c23a; font-weight: 600; margin-bottom: 4px; }
.faq-q { font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.faq-a { font-size: 13px; color: #606266; line-height: 1.6; }
.register-card { margin-top: 10px; padding: 10px 12px; border-radius: 10px; border: 1px solid; }
.register-card.success { background: #f0f9eb; border-color: #e1f3d8; }
.register-card.need_login { background: #fdf6ec; border-color: #faecd8; }
.register-card.incomplete { background: #f4f4f5; border-color: #e9e9eb; }
.register-card.failed, .register-card.error { background: #fef0f0; border-color: #fde2e2; }
.reg-title { margin-bottom: 6px; }
.reg-msg { font-size: 13px; color: #606266; line-height: 1.6; }
.quick { display: flex; gap: 8px; padding: 10px 14px; overflow-x: auto; }
.composer { display: flex; gap: 8px; padding: 12px 14px 16px; border-top: 1px solid #eeeef4; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s, transform .2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(12px); }
</style>

