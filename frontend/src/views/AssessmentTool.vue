<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { Search, Loading, UploadFilled } from '@element-plus/icons-vue'
import { platformApi as api } from '../api/platform'

type SourceType = 'text' | 'dialogue' | 'registration' | 'file'

const source = ref<SourceType>('text')
const content = ref('')
const loading = ref(false)
const result = ref<any>(null)
const selectedFile = ref<File | null>(null)

const samples: Record<SourceType, string> = {
  text: '姓名 张三 性别 男 年龄 19岁 家里很有钱 电话 13800138000',
  dialogue: '客服：您好请问想了解哪方面？客户：我儿子今年17岁，高二在读，想送他去德国。客户：他电话13711112222，我叫王五。',
  registration: '',
  file: '',
}

const fileAccept = '.txt,.md,.csv,.docx,.xlsx,.pdf'

function onFileChange(uploadFile: UploadFile) {
  selectedFile.value = uploadFile.raw || null
}

function clearFile() {
  selectedFile.value = null
}

const conclusionMap: Record<string, { label: string; type: string }> = {
  matched: { label: '符合', type: 'success' },
  partial: { label: '部分符合', type: 'warning' },
  pending: { label: '待确认', type: 'info' },
  not_matched: { label: '不符合', type: 'danger' },
  valid: { label: '有效', type: 'success' },
  invalid_input: { label: '无效输入', type: 'info' },
  invalid_phone: { label: '电话无效', type: 'danger' },
}

const resultTag = (c: string) => conclusionMap[c] || { label: c, type: 'info' }

const dimResultMap: Record<string, string> = {
  satisfied: '满足',
  unsatisfied: '不满足',
  insufficient: '信息不足',
}

const customerFieldLabels: Record<string, string> = {
  name: '姓名', phone: '电话', gender: '性别', age: '年龄',
  education: '学历', economy: '家庭经济', needs: '需求',
  study_intent: '留学意向', german_ability: '德语能力',
  english_ability: '英语能力', closed_training: '封闭式实训',
  criminal_record: '犯罪记录', belt_and_road: '政策关注', other_info: '其他信息',
}

const productLabel: Record<string, string> = { singapore: '新加坡', germany: '中德' }

function useSample() {
  if (source.value === 'file') return
  content.value = samples[source.value]
}

async function runAssess() {
  if (source.value === 'file') {
    if (!selectedFile.value) { ElMessage.warning('请选择文件'); return }
  } else if (source.value !== 'registration' && !content.value.trim()) {
    ElMessage.warning('请输入客户信息')
    return
  }
  loading.value = true
  result.value = null
  try {
    if (source.value === 'file') {
      result.value = await api.assessFile(selectedFile.value!)
    } else {
      const payload: any = { source_type: source.value, content: content.value }
      if (source.value === 'registration') {
        payload.registration = { 姓名: '李四', 性别: '女', 年龄: '22', 联系方式: '13912345678', 学历: '本科毕业（2026年6月毕业）', 职业需求: '希望提升就业竞争力、获得稳定工作', 德语能力: '零基础' }
      }
      result.value = await api.assessText(payload)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '研判失败')
  } finally {
    loading.value = false
  }
}

// v6.11.20：研判结果显式落库（POST /crm/assessments/save）
const saving = ref(false)
async function saveResult() {
  if (!result.value) { ElMessage.warning('请先执行研判'); return }
  saving.value = true
  try {
    await api.saveAssessment({ record: result.value, source_type: source.value })
    ElMessage.success('研判记录已保存')
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// v6.11.20：批量研判（POST /crm/assessments/batch，按行拆分输入）
const batchLoading = ref(false)
const batchResults = ref<any[]>([])
async function runBatch() {
  const lines = content.value.split('\n').map((s) => s.trim()).filter(Boolean)
  if (!lines.length) { ElMessage.warning('请输入客户信息（每行一条）'); return }
  if (lines.length > 500) { ElMessage.warning('单次最多 500 条'); return }
  batchLoading.value = true
  try {
    const res: any = await api.batchAssess({ records: lines.map((line) => ({ source_type: 'text', content: line })) })
    batchResults.value = Array.isArray(res) ? res : (res?.items || [])
    ElMessage.success(`批量研判完成：${batchResults.value.length} 条`)
  } catch (e: any) {
    ElMessage.error(e?.message || '批量研判失败')
  } finally {
    batchLoading.value = false
  }
}
</script>

<template>
  <div class="assessment-tool">
    <div class="at-layout">
      <el-card class="at-input" shadow="never">
        <template #header>
          <div class="at-card-title"><el-icon><Search /></el-icon><span>输入客户信息</span></div>
        </template>
        <el-radio-group v-model="source" class="at-source" size="large">
          <el-radio-button value="text">纯文本</el-radio-button>
          <el-radio-button value="dialogue">对话记录</el-radio-button>
          <el-radio-button value="registration">注册信息</el-radio-button>
          <el-radio-button value="file">文件</el-radio-button>
        </el-radio-group>
        <el-input
          v-if="source === 'text' || source === 'dialogue'"
          v-model="content"
          type="textarea"
          :rows="8"
          placeholder="粘贴客户信息，如：姓名 张三 性别 男 年龄 19岁 家里很有钱 电话 13800138000"
        />
        <el-alert v-else-if="source === 'registration'" title="注册信息渠道" type="info" :closable="false" show-icon style="margin-bottom: 12px">
          <template #default>将使用结构化注册字段示例（李四，22岁本科）进行研判。</template>
        </el-alert>
        <div v-else class="at-file-zone">
          <el-upload
            :auto-upload="false"
            :show-file-list="false"
            :accept="fileAccept"
            :on-change="onFileChange"
            drag
          >
            <el-icon class="at-upload-icon"><UploadFilled /></el-icon>
            <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 PDF / Excel(.xlsx) / Word(.docx) / TXT / MD / CSV，单个文件</div>
            </template>
          </el-upload>
          <div v-if="selectedFile" class="at-file-selected">
            <el-icon><UploadFilled /></el-icon>
            <span>{{ selectedFile.name }}</span>
            <el-button link type="primary" size="small" @click="clearFile">移除</el-button>
          </div>
        </div>
        <div class="at-actions">
          <el-button type="primary" :icon="loading ? Loading : Search" :loading="loading" @click="runAssess">立即研判</el-button>
          <el-button @click="useSample" :disabled="source === 'file'">填入示例</el-button>
          <el-button v-if="source === 'text'" :loading="batchLoading" @click="runBatch">批量研判（按行）</el-button>
          <el-button v-if="result" type="success" :loading="saving" @click="saveResult">保存研判</el-button>
        </div>
        <p class="at-hint">后端 POST /crm/assessments/text，纯规则引擎，秒级返回，不调用 AI。</p>
        <div v-if="batchResults.length" class="at-batch">
          <p class="at-hint">批量研判结果（{{ batchResults.length }} 条）：</p>
          <el-table :data="batchResults.slice(0, 20)" size="small">
            <el-table-column prop="index" label="#" width="50" />
            <el-table-column label="状态" width="110"><template #default="{ row }"><el-tag size="small" :type="resultTag(row.status).type">{{ resultTag(row.status).label }}</el-tag></template></el-table-column>
            <el-table-column label="姓名" width="90"><template #default="{ row }">{{ row.customer?.name || '—' }}</template></el-table-column>
            <el-table-column label="电话" width="120"><template #default="{ row }">{{ row.customer?.phone || '—' }}</template></el-table-column>
          </el-table>
        </div>
      </el-card>

      <el-card class="at-result" shadow="never">
        <template #header>
          <div class="at-card-title"><span>研判结果</span>
            <el-tag v-if="result" :type="resultTag(result.status).type" size="small">{{ resultTag(result.status).label }}</el-tag>
          </div>
        </template>
        <el-empty v-if="!result" description="点击「立即研判」查看双产品独立研判结果" />

        <template v-else>
          <!-- 提取到的客户信息 -->
          <div class="at-section" v-if="result.customer">
            <div class="at-section-title">📋 提取到的客户信息</div>
            <div class="at-customer-grid">
              <div class="at-field" v-for="(val, key) in result.customer" :key="key" v-show="val !== null && val !== '' && val !== undefined">
                <span class="at-field-label">{{ customerFieldLabels[key] || key }}</span>
                <span class="at-field-value">{{ val }}</span>
              </div>
            </div>
          </div>

          <!-- 冲突项 -->
          <el-alert v-if="result.conflicts?.length" type="warning" :closable="false" show-icon style="margin: 12px 0">
            <template #title>需人工确认的冲突项</template>
            <div v-for="c in result.conflicts" :key="c">• {{ c }}</div>
          </el-alert>

          <template v-if="result.status === 'valid'">
            <!-- 双产品研判 -->
            <div class="at-section-title">🔍 双产品独立研判</div>
            <div class="at-product-grid">
              <div class="at-pcard" v-for="prod in ['singapore', 'germany']" :key="prod">
                <div class="at-phead">
                  <span class="at-pname">{{ prod === 'singapore' ? '🇸🇬 新加坡' : '🇩🇪 中德' }}</span>
                  <el-tag :type="resultTag(result.assessments[prod].conclusion).type" size="small">
                    {{ resultTag(result.assessments[prod].conclusion).label }}
                  </el-tag>
                </div>
                <div class="at-dim" v-for="d in result.assessments[prod].dimensions" :key="d.dimension">
                  <span class="at-dim-name">
                    <span class="at-dot" :class="d.result" />{{ d.dimension }}
                  </span>
                  <span class="at-dim-res">{{ dimResultMap[d.result] || d.result }}</span>
                </div>
                <div class="at-evidence" v-if="result.assessments[prod].dimensions?.filter((d:any) => d.evidence).length">
                  <div class="at-evidence-title">维度证据：</div>
                  <div class="at-evidence-item" v-for="d in result.assessments[prod].dimensions.filter((x:any) => x.evidence)" :key="'ev-'+d.dimension">
                    <b>{{ d.dimension }}：</b>{{ d.evidence }}
                  </div>
                </div>
                <div class="at-programs" v-if="result.assessments[prod].matched_programs?.length">
                  <span class="at-label">适配班型：</span>
                  <el-tag v-for="p in result.assessments[prod].matched_programs" :key="p" size="small" style="margin: 2px">{{ p }}</el-tag>
                </div>
                <p class="at-summary">{{ result.assessments[prod].summary }}</p>
              </div>
            </div>

            <!-- 推荐项目 -->
            <div class="at-section" v-if="result.recommended_projects?.length">
              <div class="at-section-title">⭐ 推荐项目（按匹配度排序，第一为主推）</div>
              <div class="at-recommend-list">
                <div class="at-recommend-item" v-for="(r, i) in result.recommended_projects" :key="r.project">
                  <span class="at-rank">{{ Number(i) + 1 }}</span>
                  <span class="at-prod-name">{{ productLabel[r.project] || r.project }}</span>
                  <span class="at-reason">{{ r.reason }}</span>
                </div>
              </div>
            </div>
            <el-alert v-else type="info" :closable="false" show-icon title="暂无可推荐项目（两个产品均不符合或信息不足）" style="margin-bottom: 12px" />

            <div class="at-overview">
              <b>客户速览：</b>{{ result.customer_overview }}
            </div>
            <div class="at-advice">
              <b>跟进建议：</b>{{ result.follow_up_advice }}
            </div>
            <div class="at-missing" v-if="result.missing_info?.length">
              <b>缺失信息：</b>
              <el-tag v-for="m in result.missing_info" :key="m" size="small" type="info" style="margin: 2px">{{ m }}</el-tag>
            </div>
          </template>

          <el-alert v-else :title="result.invalid_reason || '无效输入'" type="warning" :closable="false" show-icon style="margin-top: 12px">
            <template #default>已提取的客户信息见上方，研判未执行。</template>
          </el-alert>
        </template>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.assessment-tool { max-width: 1200px; margin: 0 auto; }
.at-layout { display: grid; grid-template-columns: 360px 1fr; gap: 20px; }
.at-card-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.at-source { margin-bottom: 14px; }
.at-actions { margin-top: 14px; display: flex; gap: 10px; }
.at-hint { color: #909399; font-size: 12px; margin: 10px 0 0; }
.at-file-zone { border: 1px dashed #dcdfe6; border-radius: 8px; padding: 20px; text-align: center; }
.at-upload-icon { font-size: 48px; color: #c0c4cc; }
.at-file-selected { margin-top: 12px; display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; background: #f5f7fa; border-radius: 6px; font-size: 13px; }
.at-product-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.at-pcard { border: 1px solid #ebeef5; border-radius: 8px; padding: 14px; }
.at-phead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.at-pname { font-weight: 600; }
.at-dim { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dashed #ebeef5; font-size: 13px; }
.at-dim:last-child { border: none; }
.at-dim-name { display: flex; align-items: center; gap: 6px; color: #606266; }
.at-dim-res { color: #909399; }
.at-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.at-dot.satisfied { background: #67c23a; }
.at-dot.unsatisfied { background: #f56c6c; }
.at-dot.insufficient { background: #909399; }
.at-programs { margin: 10px 0; font-size: 13px; }
.at-label { color: #606266; }
.at-summary { color: #909399; font-size: 12px; margin: 8px 0 0; }
.at-overview { background: #f5f7fa; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; font-size: 14px; line-height: 1.6; }
.at-advice { color: #606266; font-size: 13px; line-height: 1.7; margin-bottom: 10px; }
.at-missing { font-size: 13px; }
.at-section { margin-bottom: 16px; }
.at-section-title { font-weight: 600; font-size: 15px; color: #303133; margin: 14px 0 10px; }
.at-customer-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px 16px; background: #f5f7fa; border-radius: 8px; padding: 12px 14px; }
.at-field { display: flex; flex-direction: column; gap: 2px; }
.at-field-label { font-size: 12px; color: #909399; }
.at-field-value { font-size: 14px; color: #303133; font-weight: 500; }
.at-evidence { margin: 10px 0; padding: 8px 10px; background: #fafafa; border-radius: 6px; }
.at-evidence-title { font-size: 12px; color: #909399; margin-bottom: 4px; }
.at-evidence-item { font-size: 12px; color: #606266; line-height: 1.6; }
.at-recommend-list { display: flex; flex-direction: column; gap: 8px; }
.at-recommend-item { display: flex; align-items: center; gap: 12px; padding: 10px 14px; background: #f0f9eb; border-radius: 8px; }
.at-rank { display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: #67c23a; color: #fff; font-weight: 700; font-size: 13px; flex-shrink: 0; }
.at-prod-name { font-weight: 600; color: #303133; min-width: 50px; }
.at-reason { color: #606266; font-size: 13px; }
@media (max-width: 900px) {
  .at-layout { grid-template-columns: 1fr; }
  .at-product-grid { grid-template-columns: 1fr; }
  .at-customer-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
