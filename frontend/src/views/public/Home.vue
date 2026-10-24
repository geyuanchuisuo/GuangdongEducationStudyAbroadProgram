<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Calendar, ChatDotRound, DataAnalysis, Document, School, TrendCharts } from '@element-plus/icons-vue'
import SectionTitle from '../../components/SectionTitle.vue'
import { events as mockEvents, projects as mockProjects } from '../../data/mock'
import { platformApi } from '../../api/platform'

const router = useRouter()
// v6.11.20：首页热门项目/近期活动接真实接口（/cs/courses + /events），失败降级 mock
const projects = ref<any[]>(mockProjects.slice(0, 3))
const events = ref<any[]>(mockEvents.slice(0, 3))
onMounted(async () => {
  try {
    const list: any[] = await platformApi.projects()
    if (list.length) projects.value = list.slice(0, 3)
  } catch { /* 保持 mock 兜底 */ }
  try {
    const list: any[] = await platformApi.events()
    if (list.length) events.value = list.slice(0, 3)
  } catch { /* 保持 mock 兜底 */ }
})
const businesses = [
  { title: '德国双元制职业教育', desc: '企业带薪实习与职业院校双轨培养，毕业衔接就业。', icon: School, tone: 'lime' },
  { title: '新加坡国际本硕升学', desc: '短学制、路径清晰的国际本科与硕士升学方案。', icon: TrendCharts, tone: 'amber' },
  { title: '国际留学项目', desc: '覆盖全球主流目的地的院校匹配与申请服务。', icon: DataAnalysis, tone: 'purple' },
  { title: '国际研学项目', desc: '面向不同学段的名校课堂、企业访学和文化浸润。', icon: Calendar, tone: 'coral' },
]
</script>

<template>
  <div>
    <section class="hero">
      <div class="hero-copy">
        <span class="badge">SINCE 1981 · 广东省教育服务有限公司</span>
        <h1>让每一次<br /><em>留学选择</em><br />都有专业支撑</h1>
        <p>国际教育、智慧教育、素质教育与实体教育四大板块，为学生提供从规划、申请到海外发展的全周期陪伴。</p>
        <div class="hero-actions">
          <el-button type="primary" size="large" round @click="router.push('/projects')">免费评估适配度 <el-icon><ArrowRight /></el-icon></el-button>
          <el-button size="large" round @click="router.push('/events')">查看近期活动</el-button>
        </div>
        <div class="hero-proof"><span>4大核心业务线</span><span>全球院校合作</span><span>AI + 专业顾问协同</span></div>
      </div>
      <div class="hero-visual">
        <img src="../../assets/hero.png" alt="粤教留学智能教育服务" />
        <div class="visual-card"><small>GLOBAL EDUCATION</small><strong>专业 · 透明 · 全程陪伴</strong><p>每个关键节点都有顾问和智能助手共同服务</p></div>
      </div>
    </section>

    <section class="page-wrap">
      <SectionTitle eyebrow="CORE BUSINESS" title="四大核心业务线" desc="为不同起点、不同目标的学生提供清晰可执行的教育路径。" />
      <div class="business-grid">
        <article v-for="item in businesses" :key="item.title" class="business-card">
          <div class="business-icon" :class="item.tone"><el-icon><component :is="item.icon" /></el-icon></div>
          <h3>{{ item.title }}</h3><p>{{ item.desc }}</p>
        </article>
      </div>

      <section class="section-block">
        <SectionTitle eyebrow="FEATURED PROGRAMS" title="热门项目" desc="公开浏览项目信息，报名咨询需登录。">
          <el-button round @click="router.push('/projects')">查看全部 <el-icon><ArrowRight /></el-icon></el-button>
        </SectionTitle>
        <div class="project-grid">
          <article v-for="project in projects.slice(0, 3)" :key="project.id" class="project-card" @click="router.push('/projects/' + project.id)">
            <div class="project-top"><span>{{ project.category }}</span><b v-if="project.tag">{{ project.tag }}</b></div>
            <h3>{{ project.title }}</h3><p>{{ project.summary }}</p>
            <div class="project-meta"><span>{{ project.duration }}</span><span>{{ project.fee }}</span></div>
            <button>查看详情 <el-icon><ArrowRight /></el-icon></button>
          </article>
        </div>
      </section>

      <!-- v6.13.0：智能知识问答入口（独立模块，不碰客服 AgentDock） -->
      <section class="section-block">
        <SectionTitle eyebrow="AI ASSISTANT" title="智能知识问答" desc="基于公司资料与留学政策知识库的 AI 问答，即问即答、来源可查。" />
        <div class="ai-banner" @click="router.push('/knowledge')">
          <div class="ai-icon"><el-icon><ChatDotRound /></el-icon></div>
          <div class="ai-copy">
            <h3>有疑问？直接问</h3>
            <p>公司信息、业务项目、各国留学政策——AI 从官方知识库检索并生成回答，每条回答附来源引用。</p>
          </div>
          <el-button type="primary" round>进入问答 <el-icon><ArrowRight /></el-icon></el-button>
        </div>
      </section>

      <section class="section-block split-section">
        <div>
          <SectionTitle eyebrow="EVENTS" title="近期活动" desc="未登录可以浏览，报名需要登录。" />
          <div class="event-list">
            <button v-for="event in events.slice(0, 3)" :key="event.id" @click="router.push('/events')">
              <span class="event-date">{{ event.date }}</span>
              <span><b>{{ event.title }}</b><small>{{ event.format }} · {{ event.speaker }}</small></span>
              <el-icon><ArrowRight /></el-icon>
            </button>
          </div>
        </div>
        <aside class="service-banner">
          <el-icon><Document /></el-icon>
          <h3>不知道从哪里开始？</h3>
          <p>用一分钟告诉我们你的学历、目标和时间规划，获得适合的项目建议。</p>
          <el-button type="primary" round @click="router.push('/register')">开始免费评估</el-button>
        </aside>
      </section>
    </section>
  </div>
</template>

<style scoped>
.hero { min-height: 690px; display: grid; grid-template-columns: 1.05fr .95fr; align-items: center; gap: 56px; padding: 70px max(24px, calc((100vw - 1220px) / 2)); background: #2d2b73; color: #fff; overflow: hidden; }
.hero-copy h1 { margin: 22px 0; font-family: Georgia, "Times New Roman", serif; font-size: clamp(54px, 7vw, 92px); line-height: 1.03; }
.hero-copy h1 em { color: #8dd933; font-style: normal; }
.hero-copy > p { max-width: 610px; color: #d7d6f1; line-height: 1.9; font-size: 18px; }
.hero-actions { display: flex; gap: 12px; margin-top: 30px; }
.hero-proof { display: flex; flex-wrap: wrap; gap: 22px; margin-top: 38px; color: #bbb9df; font-size: 13px; }
.hero-proof span::before { content: ''; display: inline-block; width: 7px; height: 7px; margin-right: 8px; border-radius: 2px; background: #ffc634; }
.hero-visual { position: relative; min-height: 530px; display: grid; place-items: center; }
.hero-visual::before, .hero-visual::after { content: ''; position: absolute; border: 2px solid #6d68c4; transform: rotate(42deg); }
.hero-visual::before { width: 390px; height: 390px; right: -30px; top: 35px; }
.hero-visual::after { width: 230px; height: 230px; left: 25px; bottom: 35px; border-color: #8dd933; }
.hero-visual img { position: relative; z-index: 1; width: min(430px, 78%); filter: drop-shadow(0 24px 32px rgba(0,0,0,.18)); }
.visual-card { position: absolute; z-index: 2; right: 4%; bottom: 8%; width: 260px; padding: 20px; color: #25235e; background: #fff; border-radius: 18px; box-shadow: 0 22px 55px rgba(0,0,0,.2); }
.visual-card small { color: #80b717; font-weight: 900; letter-spacing: 2px; }
.visual-card strong { display: block; margin: 8px 0; font-size: 19px; }
.visual-card p { margin: 0; color: #7b7893; line-height: 1.6; font-size: 13px; }
.business-grid, .project-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.business-card { padding: 25px; background: #fff; border: 1px solid var(--line); border-radius: 20px; transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease; }
.business-card:hover { transform: translateY(-5px); box-shadow: var(--shadow); border-color: #c9c6ec; }
.business-icon { display: grid; place-items: center; width: 48px; height: 48px; border-radius: 14px; transition: transform .25s ease; }
.business-card:hover .business-icon { transform: scale(1.08) rotate(-4deg); }
.business-icon.lime { background: var(--mint); color: #5e8c0d; }
.business-icon.amber { background: var(--yellow-soft); color: #a36e00; }
.business-icon.purple { background: #efeffa; color: var(--violet); }
.business-icon.coral { background: #fdebea; color: var(--danger); }
.business-card h3 { margin: 18px 0 10px; color: var(--ink-deep); }
.business-card p { margin: 0; color: var(--muted); line-height: 1.8; font-size: 14px; }
.project-grid { grid-template-columns: repeat(3, 1fr); }
.ai-banner { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 22px; padding: 30px 34px; background: linear-gradient(120deg, #2d2b73, #4a44a8); border-radius: 22px; cursor: pointer; transition: transform .2s, box-shadow .2s; }
.ai-banner:hover { transform: translateY(-3px); box-shadow: 0 18px 40px rgba(45, 43, 115, .28); }
.ai-icon { display: grid; place-items: center; width: 62px; height: 62px; color: #2d2b73; background: #fff; border-radius: 18px; font-size: 30px; }
.ai-copy h3 { margin: 0 0 6px; color: #fff; font-size: 24px; }
.ai-copy p { margin: 0; max-width: 640px; color: #d7d6f1; line-height: 1.8; font-size: 14px; }
.project-card { padding: 26px; background: #fff; border: 1px solid var(--line); border-radius: 20px; cursor: pointer; transition: transform .2s, box-shadow .2s, border-color .2s; }
.project-card:hover { transform: translateY(-4px); box-shadow: var(--shadow); border-color: #c9c6ec; }
.project-card button .el-icon { transition: transform .2s ease; }
.project-card:hover button .el-icon { transform: translateX(3px); }
.project-top { display: flex; justify-content: space-between; color: var(--violet); font-size: 13px; }
.project-top b { padding: 5px 9px; color: var(--ink-deep); background: var(--mint); border-radius: 999px; }
.project-card h3 { margin: 22px 0 10px; font-size: 21px; color: var(--ink-deep); }
.project-card p { min-height: 72px; color: var(--muted); line-height: 1.8; }
.project-meta { display: flex; justify-content: space-between; padding: 15px 0; border-top: 1px solid var(--line); color: var(--ink-deep); font-size: 13px; }
.project-card button { display: flex; align-items: center; gap: 7px; padding: 0; border: 0; color: var(--violet); background: transparent; font-weight: 800; cursor: pointer; }
.split-section { display: grid; grid-template-columns: 1.4fr .6fr; gap: 26px; }
.event-list { display: grid; gap: 12px; }
.event-list button { display: grid; grid-template-columns: 80px 1fr 30px; align-items: center; gap: 18px; padding: 18px; border: 1px solid var(--line); border-radius: 16px; color: var(--ink-deep); background: #fff; text-align: left; cursor: pointer; transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
.event-list button:hover { transform: translateX(4px); border-color: #c9c6ec; box-shadow: 0 10px 26px rgba(45, 43, 115, .08); }
.event-list button .el-icon { transition: transform .2s ease; }
.event-list button:hover .el-icon { transform: translateX(3px); }
.event-date { color: var(--violet); font-weight: 900; }
.event-list b, .event-list small { display: block; }
.event-list small { margin-top: 5px; color: var(--muted); }
.service-banner { padding: 32px; color: #fff; background: var(--ink-deep); border-radius: 22px; transition: transform .25s ease, box-shadow .25s ease; }
.service-banner:hover { transform: translateY(-4px); box-shadow: var(--shadow); }
.service-banner > .el-icon { font-size: 35px; color: #8dd933; }
.service-banner h3 { font-size: 25px; }
.service-banner p { color: #d4d3ed; line-height: 1.8; }
@media (max-width: 1000px) {
  .hero { grid-template-columns: 1fr; }
  .business-grid { grid-template-columns: repeat(2, 1fr); }
  .project-grid { grid-template-columns: 1fr; }
  .split-section { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .hero { min-height: auto; padding: 50px 18px; }
  .hero-actions { flex-direction: column; align-items: stretch; }
  .hero-visual { min-height: 390px; }
  .business-grid { grid-template-columns: 1fr; }
  .ai-banner { grid-template-columns: 1fr; justify-items: center; text-align: center; }
}
</style>

