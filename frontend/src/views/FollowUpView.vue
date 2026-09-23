<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowRight, RefreshCw } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  compareFollowUpReports, fetchCarePlanHistory, fetchCarePlanLogs, fetchCurrentCarePlan,
  fetchFollowUpReminder, fetchLatestReport, fetchPlanRevision, fetchReports,
  getApiErrorMessage, putCarePlanLog, putFollowUpReminder, reviseCarePlan,
} from '@/services/api'
import type {
  AdherenceLog, AdherenceLogInput, CarePlan, FollowUpComparison, FollowUpReminder,
  FollowUpReminderInput, PlanRevision, ReportAnalysis, ReportSummary,
} from '@/types'

const plan = ref<CarePlan | null>(null)
const history = ref<CarePlan[]>([])
const reports = ref<ReportSummary[]>([])
const latestReport = ref<ReportAnalysis | null>(null)
const logs = ref<AdherenceLog[]>([])
const reminder = ref<FollowUpReminder | null>(null)
const comparison = ref<FollowUpComparison | null>(null)
const revision = ref<PlanRevision | null>(null)
const previousReportId = ref('')
const currentReportId = ref('')
const revisionCodes = ref<string[]>([])
const selectedDay = ref(1)
const feedback = reactive<AdherenceLogInput>({ status: 'completed', replacement: '', discomfort: false, note: '' })
const reminderForm = reactive<FollowUpReminderInput>({ remind_on: '', basis: 'personal', note: '', enabled: true })
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')

const confirmedReports = computed(() => reports.value.filter((item) => item.status === 'confirmed'))
const scheduledDay = computed(() => plan.value?.snapshot.schedule.find((item) => item.day === selectedDay.value))
const canRecord = computed(() => plan.value?.status === 'ACTIVE' && !!scheduledDay.value && scheduledDay.value.date <= localToday())
const latestConfirmedMetrics = computed(() => latestReport.value?.status === 'confirmed'
  ? latestReport.value.metrics.filter((item) => item.confirmed)
  : [])

function localToday(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function showError(caught: unknown) {
  error.value = getApiErrorMessage(caught)
  notice.value = ''
}

function loadSelectedFeedback() {
  const existing = logs.value.find((item) => item.day === selectedDay.value)
  feedback.status = existing?.status ?? 'completed'
  feedback.replacement = existing?.replacement ?? ''
  feedback.discomfort = existing?.discomfort ?? false
  feedback.note = existing?.note ?? ''
}

async function load() {
  loading.value = true
  error.value = ''
  const results = await Promise.allSettled([
    fetchCurrentCarePlan(), fetchCarePlanHistory(), fetchReports(100), fetchLatestReport(),
  ] as const)
  if (results[0].status === 'fulfilled') plan.value = results[0].value
  else showError(results[0].reason)
  if (results[1].status === 'fulfilled') history.value = results[1].value
  else showError(results[1].reason)
  if (results[2].status === 'fulfilled') reports.value = results[2].value.items
  else showError(results[2].reason)
  latestReport.value = results[3].status === 'fulfilled' ? results[3].value : null
  if (plan.value) {
    const details = await Promise.allSettled([
      fetchCarePlanLogs(plan.value.id), fetchFollowUpReminder(plan.value.id), fetchPlanRevision(plan.value.id),
    ] as const)
    logs.value = details[0].status === 'fulfilled' ? details[0].value : []
    reminder.value = details[1].status === 'fulfilled' ? details[1].value : null
    revision.value = details[2].status === 'fulfilled' ? details[2].value : null
    Object.assign(reminderForm, reminder.value ? {
      remind_on: reminder.value.remind_on, basis: reminder.value.basis,
      note: reminder.value.note, enabled: reminder.value.enabled,
    } : { remind_on: '', basis: 'personal', note: '', enabled: true })
    previousReportId.value = plan.value.previous_plan_id
      ? history.value.find((item) => item.id === plan.value?.previous_plan_id)?.report_id ?? plan.value.report_id
      : plan.value.report_id
    currentReportId.value = latestReport.value?.report_id ?? ''
    revisionCodes.value = latestConfirmedMetrics.value
      .filter((item) => item.flag === 'attention').slice(0, 3).map((item) => item.code)
    const eligible = plan.value.snapshot.schedule.find((item) => item.date <= localToday())
    selectedDay.value = eligible?.day ?? 1
    loadSelectedFeedback()
  } else {
    logs.value = []
    reminder.value = null
    revision.value = null
  }
  loading.value = false
}

async function saveFeedback() {
  if (!plan.value || !canRecord.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const saved = await putCarePlanLog(plan.value.id, selectedDay.value, { ...feedback })
    logs.value = [...logs.value.filter((item) => item.day !== saved.day), saved].sort((a, b) => a.day - b.day)
    notice.value = saved.discomfort ? '已记录不适并暂停方案。请停止执行并寻求专业评估。' : '执行记录已保存。'
    if (saved.discomfort) await load()
  } catch (caught) {
    showError(caught)
  } finally {
    saving.value = false
  }
}

async function saveReminder() {
  if (!plan.value || !reminderForm.remind_on || saving.value) return
  saving.value = true
  error.value = ''
  try {
    reminder.value = await putFollowUpReminder(plan.value.id, { ...reminderForm })
    notice.value = '复查提醒已保存；到期提示会在打开本页时显示。'
  } catch (caught) {
    showError(caught)
  } finally {
    saving.value = false
  }
}

async function compare() {
  if (!previousReportId.value || !currentReportId.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    comparison.value = await compareFollowUpReports(previousReportId.value, currentReportId.value)
  } catch (caught) {
    showError(caught)
  } finally {
    saving.value = false
  }
}

async function revise() {
  if (!plan.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const constraints = plan.value.snapshot.constraints
    plan.value = await reviseCarePlan(plan.value.id, {
      ...constraints, start_on: localToday(), selected_metric_codes: [...revisionCodes.value],
    })
    revision.value = await fetchPlanRevision(plan.value.id)
    notice.value = '新方案草案与变更记录已生成。请核对后到食养方案页确认。'
    await load()
  } catch (caught) {
    showError(caught)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <PageHeader eyebrow="V2 · M6 执行与复查" title="记录执行，核对复查变化"
      description="按已确认报告和当前约束追踪方案版本；指标算术变化不代表食谱效果。">
      <button class="icon-button" title="刷新执行与复查数据" :disabled="loading" @click="load"><RefreshCw :size="18" :class="{ spinning: loading }" /></button>
    </PageHeader>

    <div v-if="error" class="message error-message" role="alert">{{ error }}</div>
    <div v-if="notice" class="message" role="status">{{ notice }}</div>
    <div v-if="loading" class="loading-block">正在读取执行与复查记录…</div>
    <template v-else>
      <div v-if="!plan" class="panel empty-state">尚无方案。请先在 <RouterLink to="/care-plan">食养方案</RouterLink> 页生成并确认草案。</div>
      <template v-else>
        <section class="panel">
          <span class="section-kicker">当前方案 · 第 {{ plan.version }} 版</span>
          <h2>{{ plan.status === 'ACTIVE' ? '正在执行' : plan.status === 'READY' ? '待确认草案' : plan.status === 'PAUSED' ? '已暂停' : '历史版本' }}</h2>
          <p class="panel-note">来源报告：{{ plan.snapshot.report_date }} · 方案编号 {{ plan.id }}</p>
          <p v-if="plan.pause_reason === 'adverse_feedback'" class="message error-message">因不适反馈暂停。请停止执行并先寻求专业评估；系统不会自动恢复或修订。</p>
          <p v-else-if="plan.pause_reason === 'new_report'" class="message">检测到新报告。请先完成整份核对，再查看保守对比和新方案草案。</p>
          <RouterLink v-if="plan.status === 'READY'" class="button secondary" to="/care-plan">查看并确认方案 <ArrowRight :size="16" /></RouterLink>
        </section>

        <section class="panel">
          <span class="section-kicker">第一步 · 7 天执行反馈</span><h2>完成、跳过、替换与不适</h2>
          <p class="panel-note">只记录实际发生的行为。自行替换的食物仅作为个人记录，不视为系统审核推荐。不适会立即暂停方案。</p>
          <div class="follow-fields">
            <label>安排日期
              <select v-model.number="selectedDay" @change="loadSelectedFeedback">
                <option v-for="day in plan.snapshot.schedule" :key="day.day" :value="day.day">第 {{ day.day }} 天 · {{ day.date }}</option>
              </select>
            </label>
            <label>执行情况
              <select v-model="feedback.status" :disabled="!canRecord">
                <option value="completed">已完成</option><option value="skipped">已跳过</option><option value="replaced">自行替换</option>
              </select>
            </label>
            <label v-if="feedback.status === 'replaced'">实际替换内容
              <input v-model="feedback.replacement" :disabled="!canRecord" maxlength="120" placeholder="仅记录事实，不生成新的推荐" />
            </label>
            <label class="follow-wide">备注（可选）
              <textarea v-model="feedback.note" :disabled="!canRecord" maxlength="500" rows="2" placeholder="可简要记录执行障碍；请勿填写不必要的敏感信息"></textarea>
            </label>
            <label class="follow-check"><input v-model="feedback.discomfort" type="checkbox" :disabled="!canRecord" /> 出现不适，需要暂停方案</label>
          </div>
          <button class="button primary" :disabled="!canRecord || saving" @click="saveFeedback">保存当天记录</button>
          <p v-if="!canRecord" class="panel-note">仅活动方案可记录已到日期；未来日期不可提前填写。</p>
          <div v-if="logs.length" class="follow-records">
            <div v-for="item in logs" :key="item.id"><strong>第 {{ item.day }} 天</strong><span>{{ item.status === 'completed' ? '已完成' : item.status === 'skipped' ? '已跳过' : `自行替换：${item.replacement}` }}{{ item.discomfort ? ' · 出现不适' : '' }}</span></div>
          </div>
        </section>

        <section class="panel">
          <span class="section-kicker">第二步 · 复查提醒</span><h2>依据已有安排设置日期</h2>
          <p class="panel-note">请按医生、报告或自己的既定体检计划填写日期。系统不会决定医学复查周期，也不会发送外部通知。</p>
          <div v-if="reminder?.due" class="message" role="status">你设置的复查日期已到。请按原依据安排复查并上传报告。</div>
          <div class="follow-fields">
            <label>复查提醒日期 <input v-model="reminderForm.remind_on" type="date" :disabled="plan.status === 'SUPERSEDED'" /></label>
            <label>日期依据
              <select v-model="reminderForm.basis" :disabled="plan.status === 'SUPERSEDED'">
                <option value="doctor">医生建议</option><option value="report">体检报告</option><option value="personal">既定个人计划</option>
              </select>
            </label>
            <label class="follow-wide">依据说明
              <input v-model="reminderForm.note" maxlength="240" :disabled="plan.status === 'SUPERSEDED'" placeholder="如报告备注或既定体检安排；不需要填写诊断" />
            </label>
            <label class="follow-check"><input v-model="reminderForm.enabled" type="checkbox" :disabled="plan.status === 'SUPERSEDED'" /> 启用应用内到期提示</label>
          </div>
          <button class="button secondary" :disabled="!reminderForm.remind_on || plan.status === 'SUPERSEDED' || saving" @click="saveReminder">保存提醒</button>
        </section>

        <section class="panel">
          <span class="section-kicker">第三步 · 两份报告对比</span><h2>查看已确认指标与可比性</h2>
          <div class="account-actions"><RouterLink class="button secondary" to="/report">上传或核对复查报告 <ArrowRight :size="16" /></RouterLink></div>
          <div class="follow-fields">
            <label>第一次报告
              <select v-model="previousReportId"><option value="">请选择</option><option v-for="item in confirmedReports" :key="item.report_id" :value="item.report_id">{{ item.filename }} · {{ item.created_at.slice(0, 10) }}</option></select>
            </label>
            <label>第二次报告
              <select v-model="currentReportId"><option value="">请选择</option><option v-for="item in confirmedReports" :key="item.report_id" :value="item.report_id">{{ item.filename }} · {{ item.created_at.slice(0, 10) }}</option></select>
            </label>
          </div>
          <button class="button secondary" :disabled="!previousReportId || !currentReportId || previousReportId === currentReportId || saving" @click="compare">对比两份报告</button>
          <div v-if="comparison" class="follow-comparison">
            <p class="panel-note">{{ comparison.limitation }}<span v-if="comparison.days_between !== null"> 两次检查间隔 {{ comparison.days_between }} 天。</span></p>
            <div v-for="item in comparison.metrics" :key="item.code" class="follow-compare-row">
              <strong>{{ item.name }}</strong>
              <span>{{ item.previous ? `${item.previous.value} ${item.previous.unit}` : '旧报告无记录' }} → {{ item.current ? `${item.current.value} ${item.current.unit}` : '新报告无记录' }}</span>
              <span v-if="item.pair?.arithmetic_change !== null && item.pair?.arithmetic_change !== undefined">标准单位算术差：{{ item.pair.arithmetic_change }} {{ item.standard_unit }}</span>
              <span v-else>暂不计算差值</span>
              <small>{{ item.pair?.limitations.join('；') || '该指标仅见于一份报告，无法配对。' }}</small>
            </div>
          </div>
        </section>

        <section class="panel">
          <span class="section-kicker">第四步 · 方案迭代</span><h2>保留旧快照，生成新草案</h2>
          <p class="panel-note">新方案只使用第二次报告已确认的指标及当前有效的专业审核内容。模板变化是重新匹配结果，不表示饮食造成了指标变化。</p>
          <template v-if="plan.status === 'PAUSED' && plan.pause_reason === 'new_report' && latestReport?.status === 'confirmed'">
            <fieldset class="plan-metric-options"><legend>本期关注指标（最多 3 项）</legend>
              <label v-for="metric in latestConfirmedMetrics" :key="metric.code"><input v-model="revisionCodes" type="checkbox" :value="metric.code" :disabled="!revisionCodes.includes(metric.code) && revisionCodes.length >= 3" />{{ metric.name }} · {{ metric.value }} {{ metric.unit }}</label>
            </fieldset>
            <button class="button primary" :disabled="!revisionCodes.length || saving" @click="revise">生成新版本草案</button>
          </template>
          <p v-else-if="plan.pause_reason === 'adverse_feedback'" class="panel-note">不适后需专业评估，暂不提供自动修订。</p>
          <p v-else class="panel-note">新报告确认且旧方案因报告变化暂停后，可在这里生成修订草案。</p>
          <div v-if="revision" class="follow-records">
            <h3>从旧版到第 {{ plan.version }} 版的变更</h3>
            <p v-if="revision.comparison.adherence_summary" class="panel-note">
              旧方案已记录 {{ revision.comparison.adherence_summary.logged_days }}/{{ revision.comparison.adherence_summary.scheduled_days }} 天；
              完成 {{ revision.comparison.adherence_summary.completed_days }}、跳过 {{ revision.comparison.adherence_summary.skipped_days }}、自行替换 {{ revision.comparison.adherence_summary.replaced_days }}。
              {{ revision.comparison.adherence_summary.limitation }}
            </p>
            <div v-for="change in revision.changes" :key="`${change.type}-${change.subject}`"><strong>{{ change.type }}</strong><span>{{ change.subject }} · {{ change.reason }}</span></div>
          </div>
          <div v-if="history.length" class="follow-history">
            <h3>方案版本快照</h3>
            <details v-for="item in history" :key="item.id"><summary>第 {{ item.version }} 版 · {{ item.status }} · 报告 {{ item.snapshot.report_date }}</summary>
              <p>关注指标：{{ item.snapshot.goals.map((goal) => goal.name).join('、') }}</p>
              <p>食谱版本：{{ item.snapshot.recipes.map((recipe) => `${recipe.code}@${recipe.version}`).join('、') }}</p>
              <p>方案编号：{{ item.id }}</p>
            </details>
          </div>
        </section>
      </template>
    </template>
  </div>
</template>
