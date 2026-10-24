<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { ChatDotRound, Promotion } from '@element-plus/icons-vue'
import SectionTitle from '../../components/SectionTitle.vue'

// v6.13.0：智能知识问答页（公开）。流式走 fetch+SSE（与 AgentDock 同模式、独立实现，
// 不依赖 axios 封装）；流式失败自动回退非流式 /knowledge/ask。单轮问答，仅展示历史不带上文。
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

interface SourceItem { category: string; source_file: string; section: string; doc_type: string; score?: number | null }
interface ChunkItem extends SourceItem { content: string }
interface Round {
  question: string
  answer: string
  answerSource: string // ''（进行中）/ model / retrieval_only / unavailable
  sources: SourceItem[]
  items: ChunkItem[]
  streaming: boolean
}

const question = ref('')
const asking = ref(false)
const rounds = ref<Round[]>([])
const listEl = ref<HTMLElement | null>(null)
const examples = [
  '公司简称是什么？',
  '德国双元制项目有什么优势？',
  '新加坡 2+2 国际本科班学费多少？',
  '去新加坡留学有什么政策要求？',
]

async function scrollBottom() {
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

function handleEvent(round: Round, name: string, raw: string) {
  let payload: any = null
  try { payload = JSON.parse(raw) } catch { return }
  if (payload === null) return
  if (name === 'token') {
    round.answer += payload.delta || ''
    scrollBottom()
  } else if (name === 'done') {
    round.answer = payload.answer ?? round.answer
    round.answerSource = payload.answer_source || 'model'
    round.sources = payload.sources || []
    round.items = payload.items || []
    scrollBottom()
  }
}

async function askViaStream(round: Round, text: string): Promise<boolean> {
  const resp = await fetch(API_BASE + '/knowledge/ask/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: text, top_k: 5 }),
  })
  if (!resp.ok || !resp.body) throw new Error('stream-unavailable')
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      let name = ''
      let data = ''
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) name = line.slice(7).trim()
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (name && data) handleEvent(round, name, data)
    }
  }
  return round.answerSource !== ''
}

async function askViaFallback(round: Round, text: string) {
  const body: any = await (
    await fetch(API_BASE + '/knowledge/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: text, top_k: 5 }),
    })
  ).json()
  const data = body?.data || {}
  round.answer = data.answer || '服务暂时不可用，请稍后再试。'
  round.answerSource = data.answer_source || 'unavailable'
  round.sources = data.sources || []
  round.items = data.items || []
}

async function ask(preset?: string) {
  const text = (preset ?? question.value).trim()
  if (!text || asking.value) return
  question.value = ''
  asking.value = true
  rounds.value.push({ question: text, answer: '', answerSource: '', sources: [], items: [], streaming: true })
  const round = rounds.value[rounds.value.length - 1]
  scrollBottom()
  try {
    if (!(await askViaStream(round, text))) throw new Error('no-done-event')
  } catch (error) {
    console.warn('[Knowledge] 流式不可用，回退非流式', error)
    try { await askViaFallback(round, text) } catch {
      round.answer = '服务暂时不可用，请稍后再试。'
      round.answerSource = 'unavailable'
    }
  }
  round.streaming = false
  asking.value = false
  scrollBottom()
}

function sourceLabel(s: SourceItem) {
  const section = s.section && s.section !== s.source_file ? ' › ' + s.section : ''
  return s.category + ' · ' + s.source_file + section
}
</script>

<template>
  <div class="page-wrap knowledge-page">
    <SectionTitle
      eyebrow="AI KNOWLEDGE"
      title="智能知识问答"
      desc="基于公司信息、业务项目与留学政策知识库的 AI 问答——即问即答，回答附来源引用。"
    />

    <div class="qa-shell">
      <div ref="listEl" class="qa-list">
        <div v-if="!rounds.length" class="qa-empty">
          <el-icon><ChatDotRound /></el-icon>
          <h3>问问看吧</h3>
          <p>例如：</p>
          <div class="qa-examples">
            <button v-for="item in examples" :key="item" :disabled="asking" @click="ask(item)">{{ item }}</button>
          </div>
        </div>

        <div v-for="(round, i) in rounds" :key="i" class="qa-round">
          <div class="qa-question">{{ round.question }}</div>
          <div class="qa-answer">
            <template v-if="round.answer">{{ round.answer }}</template>
            <span v-else-if="round.streaming" class="qa-typing">正在检索知识库并生成回答…</span>

            <el-alert
              v-if="round.answerSource === 'retrieval_only' && round.answer"
              class="qa-note"
              type="info"
              :closable="false"
              title="未匹配到可直接生成的回答，以下为知识库中最相关的资料片段"
            />
            <div v-if="round.answerSource === 'retrieval_only' && round.items.length" class="qa-chunks">
              <article v-for="(chunk, j) in round.items" :key="j" class="qa-chunk">
                <header>
                  <el-tag size="small" effect="plain">{{ chunk.category }}</el-tag>
                  <span>{{ chunk.source_file }}<template v-if="chunk.section && chunk.section !== chunk.source_file"> › {{ chunk.section }}</template></span>
                </header>
                <p>{{ chunk.content }}</p>
              </article>
            </div>
            <el-alert
              v-else-if="round.answerSource === 'unavailable'"
              class="qa-note"
              type="warning"
              :closable="false"
              title="知识库暂时无法访问，请稍后再试"
            />

            <footer v-if="round.sources.length" class="qa-sources">
              <span class="qa-sources-title">来源：</span>
              <el-tag v-for="(s, j) in round.sources" :key="j" size="small" type="info" effect="plain">
                {{ sourceLabel(s) }}
              </el-tag>
            </footer>
          </div>
        </div>
      </div>

      <div class="qa-input">
        <div class="qa-examples qa-examples--inline">
          <button v-for="item in examples" :key="item" :disabled="asking" @click="ask(item)">{{ item }}</button>
        </div>
        <div class="qa-input-bar">
          <el-input
            v-model="question"
            type="textarea"
            :rows="2"
            resize="none"
            maxlength="512"
            placeholder="输入你的问题，例如：新加坡本硕连读学费多少？"
            @keydown.enter.exact.prevent="ask()"
          />
          <el-button type="primary" size="large" round :loading="asking" :disabled="!question.trim()" @click="ask()">
            提问 <el-icon v-if="!asking"><Promotion /></el-icon>
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-page { padding-bottom: 70px; }
.qa-shell { overflow: hidden; background: #fff; border: 1px solid var(--line); border-radius: 22px; box-shadow: var(--shadow); }
.qa-list { max-height: 560px; min-height: 320px; overflow-y: auto; padding: 26px; }
.qa-empty { display: grid; place-items: center; gap: 6px; padding: 46px 0; color: var(--muted); text-align: center; }
.qa-empty .el-icon { font-size: 44px; color: var(--violet); }
.qa-empty h3 { margin: 6px 0 0; color: var(--ink-deep); }
.qa-empty p { margin: 4px 0 10px; font-size: 13px; }
.qa-round { margin-bottom: 22px; }
.qa-question { width: fit-content; max-width: 78%; margin-left: auto; padding: 12px 16px; color: #fff; background: var(--violet); border-radius: 16px 16px 4px 16px; line-height: 1.7; }
.qa-answer { max-width: 92%; margin-top: 12px; padding: 16px 18px; background: #f8f8fc; border: 1px solid var(--line); border-radius: 16px 16px 16px 4px; color: var(--ink-deep); line-height: 1.9; white-space: pre-wrap; word-break: break-word; }
.qa-typing { color: var(--muted); animation: qa-blink 1.2s infinite; }
@keyframes qa-blink { 50% { opacity: .4; } }
.qa-note { margin-top: 12px; }
.qa-chunks { display: grid; gap: 10px; margin-top: 12px; }
.qa-chunk { padding: 12px 14px; background: #fff; border: 1px solid var(--line); border-radius: 12px; }
.qa-chunk header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; color: var(--violet); font-size: 12px; }
.qa-chunk p { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.8; }
.qa-sources { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 14px; padding-top: 10px; border-top: 1px dashed var(--line); }
.qa-sources-title { color: var(--muted); font-size: 12px; }
.qa-examples { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.qa-examples button { padding: 7px 14px; color: var(--violet); background: #efeff9; border: 0; border-radius: 999px; cursor: pointer; font-size: 13px; }
.qa-examples button:hover:not(:disabled) { background: #e2e2f5; }
.qa-examples button:disabled { opacity: .5; cursor: not-allowed; }
.qa-input { padding: 16px 26px 22px; background: #fcfcfe; border-top: 1px solid var(--line); }
.qa-examples--inline { justify-content: flex-start; margin-bottom: 10px; }
.qa-input-bar { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: end; }
@media (max-width: 620px) {
  .qa-input-bar { grid-template-columns: 1fr; }
  .qa-question, .qa-answer { max-width: 100%; }
}
</style>
