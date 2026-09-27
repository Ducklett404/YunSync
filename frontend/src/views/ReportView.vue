<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  Check,
  Download,
  FileSearch,
  FileUp,
  Keyboard,
  LoaderCircle,
  Plus,
  RotateCcw,
  ShieldCheck,
  Trash2,
  TriangleAlert,
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  analyzeReport,
  confirmReport,
  confirmReportMetric,
  correctReportMetric,
  createManualReport,
  deleteReport,
  downloadReportSource,
  fetchLatestReport,
  fetchMetricHistory,
  fetchReport,
  fetchReports,
  getApiErrorMessage,
  retryReport,
  updateReportCriticalMarker,
  updateReportMetadata,
} from '@/services/api'
import type { HealthMetric, MetricHistory, ReportAnalysis, ReportSummary } from '@/types'

interface MetricDraft {
  name: string
  value: number
  reported_precision: number | null
  unit: string
  reference_range: string
  method: string
}

interface ManualMetricDraft {
  name: string
  value: number | null
  reported_precision: number | null
  unit: string
  reference_range: string
  method: string
}

const now = new Date()
const localToday = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
const emptyManualMetric = (): ManualMetricDraft => ({ name: '', value: null, reported_precision: null, unit: '', reference_range: '', method: '' })

const report = ref<ReportAnalysis | null>(null)
const reportEntries = ref<ReportSummary[]>([])
const reportTotal = ref(0)
const historyLoading = ref(false)
const historyError = ref('')
const metricHistory = ref<MetricHistory | null>(null)
const metricHistoryError = ref('')
const reportLoading = ref(false)
const drafts = ref<Record<string, MetricDraft>>({})
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const manualOpen = ref(false)
const manualSaving = ref(false)
const manualTitle = ref(`手工录入 ${localToday}`)
const manualInstitution = ref('')
const manualMeasuredOn = ref(localToday)
const manualMetrics = ref<ManualMetricDraft[]>([emptyManualMetric()])
const busyMetricId = ref('')
const markerChoice = ref<ReportAnalysis['critical_marker_status']>('unknown')
const markerSaving = ref(false)
const institutionDraft = ref('')
const examinedOnDraft = ref('')
const metadataSaving = ref(false)
const error = ref('')
const success = ref('')
const sourcePreviewUrl = ref('')
const sourcePreviewLoading = ref(false)
const deletingReport = ref(false)
const sourcePreviewError = ref('')
const sourcePreviewElement = ref<HTMLElement | null>(null)
const focusedMetricId = ref('')
let sourcePreviewRequestId = 0

const confirmedCount = computed(
  () => report.value?.metrics.filter((metric) => metric.confirmed).length ?? 0,
)
const allFieldsConfirmed = computed(
  () => Boolean(report.value?.metrics.length) && confirmedCount.value === report.value?.metrics.length,
)
const unresolvedUnitCount = computed(() => report.value?.metrics.filter((metric) =>
  ['unsupported_unit', 'identity_conflict', 'invalid_value'].includes(metric.unit_projection?.status ?? ''),
).length ?? 0)
const isLatestReport = computed(
  () => report.value?.report_id === reportEntries.value[0]?.report_id,
)
const historyRows = computed(() => metricHistory.value?.series.map((series) => {
  const pair = series.latest_pair
  return {
    series,
    pair,
    previous: pair ? [...series.points].reverse().find((point) => point.report_id === pair.previous_report_id) : undefined,
    current: pair ? [...series.points].reverse().find((point) => point.report_id === pair.current_report_id) : series.points.at(-1),
  }
}) ?? [])
const focusedMetric = computed(() => {
  if (!report.value?.metrics.length) return null
  return report.value.metrics.find((metric) => metric.id === focusedMetricId.value) ?? report.value.metrics[0]
})
const sourcePreviewTargetUrl = computed(() => {
  if (!sourcePreviewUrl.value) return ''
  if (report.value?.content_type !== 'application/pdf' || !focusedMetric.value) return sourcePreviewUrl.value
  return `${sourcePreviewUrl.value}#page=${focusedMetric.value.source_page}&zoom=page-width`
})
const sourceHighlightStyle = computed(() => {
  if (report.value?.content_type === 'application/pdf' || !focusedMetric.value) return undefined
  const [x = 0, y = 0, width = 0, height = 0] = focusedMetric.value.source_bbox
  return {
    left: `${Math.max(0, Math.min(1, x)) * 100}%`,
    top: `${Math.max(0, Math.min(1, y)) * 100}%`,
    width: `${Math.max(0, Math.min(1 - x, width)) * 100}%`,
    height: `${Math.max(0, Math.min(1 - y, height)) * 100}%`,
  }
})

onMounted(async () => {
  try {
    const loaded = await loadReports()
    if (loaded && reportEntries.value.length) {
      setReport(await fetchReport(reportEntries.value[0].report_id))
    } else if (!loaded) {
      setReport(await fetchLatestReport())
    }
  } catch (requestError) {
    const message = getApiErrorMessage(requestError)
    if (message !== '尚无体检报告') error.value = message
  }
  await loadMetricHistory()
})

onBeforeUnmount(() => clearSourcePreview())

async function loadMetricHistory() {
  metricHistoryError.value = ''
  try {
    metricHistory.value = await fetchMetricHistory()
  } catch (requestError) {
    metricHistoryError.value = getApiErrorMessage(requestError)
  }
}

async function loadReports(append = false): Promise<boolean> {
  historyLoading.value = true
  historyError.value = ''
  try {
    const result = await fetchReports(20, append ? reportEntries.value.length : 0)
    reportEntries.value = append ? [...reportEntries.value, ...result.items] : result.items
    reportTotal.value = result.total
    return true
  } catch (requestError) {
    historyError.value = getApiErrorMessage(requestError)
    return false
  } finally {
    historyLoading.value = false
  }
}

async function openReport(reportId: string) {
  if (reportLoading.value || report.value?.report_id === reportId) return
  reportLoading.value = true
  error.value = ''
  success.value = ''
  try {
    setReport(await fetchReport(reportId))
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    reportLoading.value = false
  }
}

function setReport(value: ReportAnalysis) {
  const reportChanged = report.value?.report_id !== value.report_id
  report.value = value
  markerChoice.value = value.critical_marker_status
  institutionDraft.value = value.institution
  examinedOnDraft.value = value.examined_at ? toDateInput(value.examined_at) : ''
  reportEntries.value = reportEntries.value.map((entry) =>
    entry.report_id === value.report_id
      ? {
          ...entry,
          status: value.status,
          ocr_status: value.ocr_status,
          critical_marker_status: value.critical_marker_status,
        }
      : entry,
  )
  drafts.value = Object.fromEntries(
    value.metrics.map((metric) => [
      metric.id,
      {
        name: metric.name,
        value: metric.value,
        reported_precision: metric.reported_precision,
        unit: metric.unit,
        reference_range: metric.reference_range,
        method: metric.method,
      },
    ]),
  )
  if (reportChanged) {
    focusedMetricId.value = value.metrics[0]?.id ?? ''
    void loadSourcePreview(value)
  }
}

function clearSourcePreview() {
  sourcePreviewRequestId += 1
  if (sourcePreviewUrl.value) URL.revokeObjectURL(sourcePreviewUrl.value)
  sourcePreviewUrl.value = ''
  sourcePreviewLoading.value = false
  sourcePreviewError.value = ''
}

async function loadSourcePreview(value: ReportAnalysis) {
  clearSourcePreview()
  if (!value.source_available) return

  const requestId = sourcePreviewRequestId
  sourcePreviewLoading.value = true
  try {
    const blob = await downloadReportSource(value.report_id)
    if (requestId !== sourcePreviewRequestId) return
    sourcePreviewUrl.value = URL.createObjectURL(blob)
  } catch (requestError) {
    if (requestId === sourcePreviewRequestId) {
      sourcePreviewError.value = getApiErrorMessage(requestError)
    }
  } finally {
    if (requestId === sourcePreviewRequestId) sourcePreviewLoading.value = false
  }
}

async function focusSource(metric: HealthMetric) {
  focusedMetricId.value = metric.id
  await nextTick()
  sourcePreviewElement.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

function toDateInput(value: string) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

function reportMetadataChanged() {
  if (!report.value) return false
  const currentDate = report.value.examined_at ? toDateInput(report.value.examined_at) : ''
  return institutionDraft.value.trim() !== report.value.institution || examinedOnDraft.value !== currentDate
}

async function saveReportMetadata() {
  if (!report.value || !examinedOnDraft.value) {
    error.value = '请填写报告检查日期。'
    return
  }
  metadataSaving.value = true
  error.value = ''
  success.value = ''
  try {
    const wasFinalized = report.value.status === 'confirmed'
    const examinedAt = examinedOnDraft.value === localToday
      ? new Date().toISOString()
      : new Date(`${examinedOnDraft.value}T12:00:00`).toISOString()
    setReport(await updateReportMetadata(report.value.report_id, {
      institution: institutionDraft.value.trim(),
      examined_at: examinedAt,
    }))
    if (wasFinalized) await loadMetricHistory()
    success.value = wasFinalized
      ? '报告信息已更新，请重新完成报告确认。'
      : '报告检查日期和机构已保存。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    metadataSaving.value = false
  }
}

async function saveCriticalMarker() {
  if (!report.value) return
  markerSaving.value = true
  error.value = ''
  success.value = ''
  try {
    setReport(await updateReportCriticalMarker(report.value.report_id, markerChoice.value))
    success.value = markerChoice.value === 'yes'
      ? '已记录报告的危急值标记，请尽快联系出具报告的机构或医生核实。'
      : '报告危急值标记核对结果已保存。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    markerSaving.value = false
  }
}

function replaceMetric(updated: HealthMetric) {
  if (!report.value) return
  report.value.metrics = report.value.metrics.map((metric) =>
    metric.id === updated.id ? updated : metric,
  )
  drafts.value[updated.id] = {
    name: updated.name,
    value: updated.value,
    reported_precision: updated.reported_precision,
    unit: updated.unit,
    reference_range: updated.reference_range,
    method: updated.method,
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
  success.value = ''
  error.value = ''
  if (selectedFile.value && selectedFile.value.size > 5 * 1024 * 1024) {
    error.value = '文件不能超过 5 MB'
    selectedFile.value = null
  }
}

async function runAnalysis() {
  if (!selectedFile.value) return
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    setReport(await analyzeReport(selectedFile.value))
    await loadReports()
    success.value = '已生成合成 OCR 候选字段，请逐项核对后再完成报告确认。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
    try {
      setReport(await fetchLatestReport())
      await loadReports()
    } catch {
      // Keep the actionable upload error when no failed report was persisted.
    }
  } finally {
    loading.value = false
  }
}

function addManualMetric() {
  if (manualMetrics.value.length < 30) manualMetrics.value.push(emptyManualMetric())
}

function removeManualMetric(index: number) {
  if (manualMetrics.value.length > 1) manualMetrics.value.splice(index, 1)
}

function normalizedPrecision(value: number | null): number | null {
  return Number.isInteger(value) && value !== null && value >= 0 && value <= 6 ? value : null
}

async function saveManualReport() {
  if (!manualTitle.value.trim() || !manualMeasuredOn.value) {
    error.value = '请填写批次名称和检查日期。'
    return
  }
  if (manualMetrics.value.some((metric) =>
    !metric.name.trim() || !metric.unit.trim() || !Number.isFinite(Number(metric.value)),
  )) {
    error.value = '每项指标都需要有效的名称、数值和单位。'
    return
  }
  manualSaving.value = true
  error.value = ''
  success.value = ''
  try {
    const measuredAt = manualMeasuredOn.value === localToday
      ? new Date().toISOString()
      : new Date(`${manualMeasuredOn.value}T12:00:00`).toISOString()
    setReport(await createManualReport({
      title: manualTitle.value.trim(),
      institution: manualInstitution.value.trim(),
      measured_at: measuredAt,
      metrics: manualMetrics.value.map((metric) => ({
        name: metric.name.trim(),
        value: Number(metric.value),
        reported_precision: normalizedPrecision(metric.reported_precision),
        unit: metric.unit.trim(),
        reference_range: metric.reference_range.trim(),
        method: metric.method.trim(),
      })),
    }))
    await loadReports()
    manualMetrics.value = [emptyManualMetric()]
    manualTitle.value = `手工录入 ${localToday}`
    manualInstitution.value = ''
    manualMeasuredOn.value = localToday
    manualOpen.value = false
    success.value = '手工录入批次已建立，请逐项核对后完成报告确认。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    manualSaving.value = false
  }
}

async function retryAnalysis() {
  if (!report.value) return
  loading.value = true
  error.value = ''
  try {
    setReport(await retryReport(report.value.report_id))
    success.value = '重试成功，请继续逐项核对。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
    try {
      setReport(await fetchLatestReport())
      await loadReports()
    } catch {
      // Preserve the retry error.
    }
  } finally {
    loading.value = false
  }
}

async function confirmOne(metric: HealthMetric) {
  if (!report.value) return
  busyMetricId.value = metric.id
  error.value = ''
  try {
    replaceMetric(await confirmReportMetric(report.value.report_id, metric.id))
    success.value = `已确认“${metric.name}”。`
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    busyMetricId.value = ''
  }
}

function draftChanged(metric: HealthMetric) {
  const draft = drafts.value[metric.id]
  return Boolean(
    draft &&
      (draft.name !== metric.name ||
        Number(draft.value) !== metric.value ||
        draft.reported_precision !== metric.reported_precision ||
        draft.unit !== metric.unit ||
        draft.reference_range !== metric.reference_range ||
        draft.method !== metric.method),
  )
}

function canEditMetricContent(metric: HealthMetric) {
  return report.value?.status !== 'confirmed' ||
    ['unsupported_unit', 'identity_conflict', 'invalid_value'].includes(metric.unit_projection?.status ?? '')
}

async function saveCorrection(metric: HealthMetric) {
  if (!report.value) return
  const draft = drafts.value[metric.id]
  if (!draft || !draft.name.trim() || !draft.unit.trim() || !Number.isFinite(Number(draft.value))) {
    error.value = '名称、数值和单位必须填写有效内容。'
    return
  }
  busyMetricId.value = metric.id
  error.value = ''
  try {
    const wasFinalized = report.value.status === 'confirmed'
    replaceMetric(
      await correctReportMetric(report.value.report_id, metric.id, {
        name: draft.name.trim(),
        value: Number(draft.value),
        reported_precision: normalizedPrecision(draft.reported_precision),
        unit: draft.unit.trim(),
        reference_range: draft.reference_range.trim(),
        method: draft.method.trim(),
      }),
    )
    if (wasFinalized) {
      report.value.status = 'needs_confirmation'
      setReport(report.value)
      await loadMetricHistory()
    }
    success.value = `已保存并确认“${draft.name}”的修正。`
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    busyMetricId.value = ''
  }
}

async function finalizeReport() {
  if (!report.value || !allFieldsConfirmed.value || unresolvedUnitCount.value) return
  loading.value = true
  error.value = ''
  try {
    await confirmReport(report.value.report_id)
    report.value.status = 'confirmed'
    setReport(report.value)
    await loadMetricHistory()
    success.value = '报告字段已逐项确认。请继续完善安全档案；方案仅使用已审核发布的内容。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function downloadSource() {
  if (!report.value) return
  error.value = ''
  try {
    const blob = await downloadReportSource(report.value.report_id)
    const href = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = href
    link.download = report.value.filename
    link.click()
    URL.revokeObjectURL(href)
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  }
}

async function removeCurrentReport() {
  if (!report.value) return
  const reportId = report.value.report_id
  if (!window.confirm('永久删除这份报告、指标和关联照护方案/反馈记录？此操作无法撤销。')) return
  deletingReport.value = true
  error.value = ''
  success.value = ''
  try {
    await deleteReport(reportId)
    clearSourcePreview()
    report.value = null
    await Promise.all([loadReports(), loadMetricHistory()])
    if (reportEntries.value.length) setReport(await fetchReport(reportEntries.value[0].report_id))
    success.value = '报告及其关联数据已删除。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    deletingReport.value = false
  }
}

function sourcePosition(metric: HealthMetric) {
  if (report.value?.source === 'manual') {
    return `手工录入 · 检查日期 ${new Date(metric.measured_at).toLocaleDateString('zh-CN')}`
  }
  const [x = 0, y = 0] = metric.source_bbox
  return `第 ${metric.source_page} 页 · ${Math.round(x * 100)}%, ${Math.round(y * 100)}%`
}

function formatHistoryPoint(point: { value: number; unit: string; examined_at: string | null } | undefined) {
  if (!point) return '—'
  const date = point.examined_at ? new Date(point.examined_at).toLocaleDateString('zh-CN') : '检查日期待补'
  return `${point.value} ${point.unit} · ${date}`
}

function formatArithmeticChange(change: number) {
  return `${change > 0 ? '+' : ''}${Number(change.toPrecision(4))}`
}
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="步骤 1"
      title="报告解析与确认"
      description="每个 OCR 候选字段都必须由用户确认或修正。报告确认是后续食养方案的前置步骤。"
    />

    <div class="content-grid report-grid">
      <section class="panel upload-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">数据接入</span>
            <h2>上传或手工录入</h2>
          </div>
          <FileUp :size="22" class="muted-icon" />
        </div>
        <label class="upload-zone">
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" @change="onFileChange" />
          <FileSearch :size="34" />
          <strong>{{ selectedFile?.name ?? '选择 PDF 或图片' }}</strong>
          <span>最大 5 MB；扩展名、MIME 与文件签名需一致</span>
        </label>
        <button class="button primary full-width" :disabled="!selectedFile || loading" @click="runAnalysis">
          <LoaderCircle v-if="loading" :size="17" class="spinning" />
          <FileSearch v-else :size="17" />
          解析报告
        </button>
        <button class="button secondary full-width manual-toggle" type="button" :disabled="manualSaving" @click="manualOpen = !manualOpen">
          <Keyboard :size="17" />
          {{ manualOpen ? '收起手工录入' : '手工录入指标' }}
        </button>
        <div v-if="manualOpen" class="manual-entry-form">
          <label class="inline-field">
            <span>批次名称</span>
            <input v-model.trim="manualTitle" maxlength="120" />
          </label>
          <label class="inline-field">
            <span>检查日期</span>
            <input v-model="manualMeasuredOn" type="date" min="1900-01-01" :max="localToday" />
          </label>
          <label class="inline-field">
            <span>检测机构（可不填）</span>
            <input v-model.trim="manualInstitution" maxlength="120" placeholder="按报告原件填写" />
          </label>
          <div class="manual-metric-list">
            <div v-for="(metric, index) in manualMetrics" :key="index" class="manual-metric-card">
              <div class="manual-metric-heading">
                <strong>指标 {{ index + 1 }}</strong>
                <button type="button" class="icon-button" aria-label="删除这一项" :disabled="manualMetrics.length === 1" @click="removeManualMetric(index)">
                  <Trash2 :size="15" />
                </button>
              </div>
              <label class="inline-field">
                <span>指标名称</span>
                <input v-model.trim="metric.name" maxlength="80" placeholder="例如：空腹血糖" />
              </label>
              <div class="manual-metric-value-row">
                <label class="inline-field">
                  <span>结果数值</span>
                  <input v-model.number="metric.value" type="number" step="any" />
                </label>
                <label class="inline-field">
                  <span>单位</span>
                  <input v-model.trim="metric.unit" maxlength="32" placeholder="例如：mmol/L" />
                </label>
              </div>
              <label class="inline-field">
                <span>报告显示小数位（可不填）</span>
                <input v-model.number="metric.reported_precision" type="number" min="0" max="6" step="1" placeholder="例如：1" />
              </label>
              <label class="inline-field">
                <span>参考范围（可不填）</span>
                <input v-model.trim="metric.reference_range" maxlength="64" placeholder="例如：3.9-6.1" />
              </label>
              <label class="inline-field">
                <span>检测方法（可不填）</span>
                <input v-model.trim="metric.method" maxlength="120" placeholder="按报告原件填写" />
              </label>
            </div>
          </div>
          <button type="button" class="button secondary full-width" :disabled="manualMetrics.length >= 30" @click="addManualMetric">
            <Plus :size="16" /> 添加指标
          </button>
          <button type="button" class="button primary full-width" :disabled="manualSaving" @click="saveManualReport">
            <LoaderCircle v-if="manualSaving" :size="16" class="spinning" />
            <Check v-else :size="16" />
            {{ manualSaving ? '创建中…' : '创建待确认批次' }}
          </button>
        </div>
        <div class="privacy-note">
          <ShieldCheck :size="18" />
          <span>文件仅进入本地私有目录并通过登录接口访问；当前仅使用合成或经批准的脱敏数据，也不要手工录入真实健康信息。</span>
        </div>
        <div class="report-history">
          <h3>我的报告批次 <span v-if="reportTotal">({{ reportTotal }})</span></h3>
          <p v-if="historyError" class="message error-message">历史报告读取失败：{{ historyError }}</p>
          <p v-if="!reportEntries.length && !historyError" class="panel-note">{{ historyLoading ? '正在读取…' : '尚无报告批次。' }}</p>
          <div v-if="reportEntries.length" class="report-history-list">
            <button
              v-for="(entry, index) in reportEntries"
              :key="entry.report_id"
              type="button"
              class="report-history-item"
              :class="{ selected: report?.report_id === entry.report_id }"
              :aria-current="report?.report_id === entry.report_id ? 'true' : undefined"
              :disabled="reportLoading"
              @click="openReport(entry.report_id)"
            >
              <strong>{{ entry.filename }}</strong>
              <small>{{ new Date(entry.created_at).toLocaleDateString('zh-CN') }} · {{ index === 0 ? '最新' : '历史' }} · {{ entry.status === 'confirmed' ? '已确认' : entry.ocr_status === 'failed' ? '识别失败' : '待确认' }}</small>
            </button>
          </div>
          <button v-if="reportEntries.length < reportTotal" class="text-link button-reset" type="button" :disabled="historyLoading" @click="loadReports(true)">
            {{ historyLoading ? '读取中…' : '加载更多报告' }}
          </button>
        </div>
      </section>

      <section class="panel metrics-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">识别与校对</span>
            <h2>{{ report?.filename ?? '尚无报告' }}</h2>
          </div>
          <span
            v-if="report"
            class="status-badge"
            :class="report.status === 'confirmed' ? 'safe' : report.ocr_status === 'failed' ? 'danger' : 'pending'"
          >
            {{ report.status === 'confirmed' ? '已确认' : report.ocr_status === 'failed' ? '识别失败' : '待逐项确认' }}
          </span>
        </div>

        <div v-if="error" class="message error-message">{{ error }}</div>
        <div v-if="success" class="message success-message">{{ success }}</div>
        <div v-if="report && reportEntries.length && !isLatestReport" class="report-notice">
          当前查看的是历史报告；安全分流以最新报告为准。
        </div>

        <div v-if="report" class="report-metadata-review">
          <div>
            <strong>核对检查信息</strong>
            <p>检查日期用于排列历次结果；机构与检测方法用于提示可比性限制。请按报告原件填写。</p>
          </div>
          <div class="report-metadata-fields">
            <label class="inline-field">
              <span>检查日期</span>
              <input v-model="examinedOnDraft" type="date" min="1900-01-01" :max="localToday" />
            </label>
            <label class="inline-field">
              <span>检测机构（可不填）</span>
              <input v-model.trim="institutionDraft" maxlength="120" placeholder="按报告原件填写" />
            </label>
          </div>
          <button class="button secondary" type="button" :disabled="metadataSaving || !reportMetadataChanged()" @click="saveReportMetadata">
            {{ metadataSaving ? '保存中…' : '保存检查信息' }}
          </button>
        </div>

        <div v-if="report" class="critical-marker-review">
          <div class="critical-marker-heading">
            <div>
              <strong>核对报告上的危急值标记</strong>
              <p>请对照报告原件和出具机构的通知确认；不要仅凭数值高低或红色箭头推断。</p>
            </div>
            <span class="status-badge" :class="report.critical_marker_status === 'yes' ? 'danger' : report.critical_marker_status === 'no' ? 'safe' : 'pending'">
              {{ report.critical_marker_status === 'yes' ? '已标注危急值' : report.critical_marker_status === 'no' ? '已确认无标记' : '尚未核对' }}
            </span>
          </div>
          <div class="critical-marker-options" role="radiogroup" aria-label="报告危急值标记核对结果">
            <label><input v-model="markerChoice" type="radio" name="critical-marker" value="unknown" /> 尚未确认</label>
            <label><input v-model="markerChoice" type="radio" name="critical-marker" value="no" /> 原件未明确标注</label>
            <label><input v-model="markerChoice" type="radio" name="critical-marker" value="yes" /> 原件明确标注</label>
          </div>
          <div class="critical-marker-actions">
            <button class="button secondary" type="button" :disabled="markerSaving || markerChoice === report.critical_marker_status" @click="saveCriticalMarker">
              {{ markerSaving ? '保存中…' : '保存核对结果' }}
            </button>
            <RouterLink v-if="report.critical_marker_status === 'yes'" class="text-link" to="/safety">查看安全提示</RouterLink>
          </div>
        </div>

        <div v-if="report?.ocr_status === 'failed'" class="ocr-failure-state">
          <TriangleAlert :size="24" />
          <div>
            <strong>没有生成任何候选指标</strong>
            <span>错误代码：{{ report.ocr_error_code }}；已尝试 {{ report.ocr_attempts }} 次。</span>
          </div>
          <button class="button secondary" :disabled="loading" @click="retryAnalysis">
            <RotateCcw :size="16" /> 重试识别
          </button>
        </div>

        <template v-else-if="report">
          <div class="report-notice">
            <span>{{ report.synthetic_notice }}</span>
            <div class="inline-actions">
              <button
                v-if="report.source_available"
                class="text-link button-reset"
                type="button"
                @click="downloadSource"
              >
                <Download :size="15" /> 下载源文件核对
              </button>
              <button class="text-link button-reset danger-text" type="button" :disabled="deletingReport" @click="removeCurrentReport">
                <Trash2 :size="15" /> {{ deletingReport ? '删除中…' : '删除本报告' }}
              </button>
            </div>
          </div>

          <section v-if="report.source_available" ref="sourcePreviewElement" class="source-preview-panel" aria-labelledby="source-preview-title">
            <div class="source-preview-heading">
              <div>
                <strong id="source-preview-title">原报告对照</strong>
                <small v-if="focusedMetric">当前定位：{{ focusedMetric.name }} · 第 {{ focusedMetric.source_page }} 页</small>
              </div>
              <button class="text-link button-reset" type="button" :disabled="sourcePreviewLoading" @click="loadSourcePreview(report)">
                <RotateCcw :size="14" /> {{ sourcePreviewLoading ? '读取中…' : '重新读取' }}
              </button>
            </div>
            <div v-if="sourcePreviewLoading" class="source-preview-state">
              <LoaderCircle :size="20" class="spinning" /> 正在通过受控接口读取源文件…
            </div>
            <div v-else-if="sourcePreviewError" class="source-preview-state error-message">
              <span>源文件预览不可用：{{ sourcePreviewError }}</span>
              <button class="text-link button-reset" type="button" @click="downloadSource">尝试下载核对</button>
            </div>
            <iframe
              v-else-if="sourcePreviewTargetUrl && report.content_type === 'application/pdf'"
              :key="`${report.report_id}-${focusedMetric?.source_page ?? 1}`"
              class="source-pdf-frame"
              :src="sourcePreviewTargetUrl"
              title="报告 PDF 原文预览"
            />
            <div v-else-if="sourcePreviewTargetUrl" class="source-image-canvas">
              <img :src="sourcePreviewTargetUrl" alt="报告原图" />
              <span v-if="sourceHighlightStyle" class="source-location-highlight" :style="sourceHighlightStyle" aria-label="当前指标原文位置" />
            </div>
            <p class="source-preview-note">定位框和页码来自 OCR 返回位置，只用于帮助对照；请以原报告可见内容为准。</p>
          </section>

          <div class="review-progress" aria-live="polite">
            <span>字段确认进度</span>
            <strong>{{ confirmedCount }} / {{ report.metrics.length }}</strong>
          </div>

          <div class="action-table-wrap report-review-table">
            <table class="data-table">
              <thead>
                <tr>
                  <th>指标与原文</th>
                  <th>数值</th>
                  <th>单位</th>
                  <th>参考范围</th>
                  <th>置信度与位置</th>
                  <th>校对</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="metric in report.metrics" :key="metric.id" :class="{ 'low-confidence-row': metric.confidence < 0.8 }">
                  <td>
                    <label class="inline-field">
                      <span>指标名称</span>
                      <input v-model.trim="drafts[metric.id].name" maxlength="80" :disabled="!canEditMetricContent(metric)" />
                    </label>
                    <span class="source-excerpt">原文：{{ metric.raw_text }}</span>
                  </td>
                  <td>
                    <label class="inline-field compact">
                      <span>结果数值</span>
                      <input v-model.number="drafts[metric.id].value" type="number" step="any" :disabled="!canEditMetricContent(metric)" />
                    </label>
                    <label class="inline-field compact">
                      <span>报告显示小数位</span>
                      <input v-model.number="drafts[metric.id].reported_precision" type="number" min="0" max="6" step="1" placeholder="未记录" />
                    </label>
                  </td>
                  <td>
                    <label class="inline-field compact">
                      <span>单位</span>
                      <input v-model.trim="drafts[metric.id].unit" maxlength="32" :disabled="!canEditMetricContent(metric)" />
                    </label>
                    <small v-if="metric.unit_projection?.status === 'converted'" class="unit-projection-note">
                      换算显示 ≈ {{ metric.unit_projection.standard_value?.toFixed(2) }} {{ metric.unit_projection.standard_unit }}
                    </small>
                    <small v-else-if="metric.unit_projection?.status === 'unsupported_unit'" class="unit-projection-note warning">单位待核对，暂不能跨报告对齐</small>
                    <small v-else-if="metric.unit_projection?.status === 'identity_conflict'" class="unit-projection-note warning">名称与标准代码冲突，请核对</small>
                    <small v-else-if="metric.unit_projection?.status === 'invalid_value'" class="unit-projection-note warning">数值无效，请对照原报告核对</small>
                    <small v-else-if="metric.unit_projection?.status === 'outside_catalog' && metric.confirmed" class="unit-projection-note">非首版标准指标，暂不对齐</small>
                  </td>
                  <td>
                    <label class="inline-field compact">
                      <span>参考范围</span>
                      <input v-model.trim="drafts[metric.id].reference_range" maxlength="64" :disabled="!canEditMetricContent(metric)" />
                    </label>
                    <label class="inline-field metric-method-field">
                      <span>检测方法（可不填）</span>
                      <input v-model.trim="drafts[metric.id].method" maxlength="120" placeholder="按报告原件填写" />
                    </label>
                  </td>
                  <td>
                    <span :class="['confidence-value', metric.confidence < 0.8 ? 'low' : '']">
                      {{ Math.round(metric.confidence * 100) }}%
                    </span>
                    <small>{{ sourcePosition(metric) }}</small>
                    <button
                      v-if="report.source_available"
                      class="text-link button-reset source-locate-button"
                      type="button"
                      :aria-pressed="focusedMetric?.id === metric.id"
                      @click="focusSource(metric)"
                    >
                      {{ focusedMetric?.id === metric.id ? '已定位原文' : '定位原文' }}
                    </button>
                  </td>
                  <td>
                    <div class="review-actions">
                      <span v-if="metric.confirmed" class="status-badge safe">
                        {{ metric.review_status === 'corrected' ? '已修正' : '已确认' }}
                      </span>
                      <button v-if="!metric.confirmed" class="button compact-button secondary" :disabled="busyMetricId === metric.id" @click="confirmOne(metric)">
                        确认原值
                      </button>
                      <button class="button compact-button primary" :disabled="busyMetricId === metric.id || !draftChanged(metric)" @click="saveCorrection(metric)">
                        保存修正
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="finalize-row">
            <span v-if="!allFieldsConfirmed">请确认或修正每一个字段后再继续。</span>
            <span v-else-if="unresolvedUnitCount">{{ unresolvedUnitCount }} 个标准指标的名称或单位待核对；可直接修改已确认字段。</span>
            <span v-else>所有字段已逐项处理，可以完成报告确认。</span>
            <button class="button primary" :disabled="loading || !allFieldsConfirmed || unresolvedUnitCount > 0 || report.status === 'confirmed'" @click="finalizeReport">
              <Check :size="17" />
              {{ report.status === 'confirmed' ? '报告已确认' : '完成报告确认' }}
            </button>
          </div>
        </template>

        <div v-else class="empty-state">上传合成报告后，结构化候选指标会显示在这里。</div>
      </section>
    </div>

    <section class="panel metric-history-panel">
      <div class="panel-heading">
        <div>
          <span class="section-kicker">复查数据准备</span>
          <h2>同指标历史对齐</h2>
        </div>
      </div>
      <p class="panel-note">仅统计最近 {{ metricHistory?.report_limit ?? 20 }} 份已确认报告。标准指标唯一、单位可投影，检查日期、检测机构、检测方法和报告显示精度均明确且一致，参考范围已填写并一致时才显示算术差；该差值不能用于判断健康趋势或食养效果。</p>
      <p v-if="metricHistoryError" class="message error-message">历史指标读取失败：{{ metricHistoryError }}</p>
      <div v-else-if="!historyRows.length" class="empty-state">确认报告后，这里会显示同一指标的历次记录。</div>
      <div v-else class="action-table-wrap metric-history-table">
        <table class="data-table">
          <thead>
            <tr>
              <th>标准指标</th>
              <th>前次原值</th>
              <th>本次原值</th>
              <th>标准单位算术差</th>
              <th>可比性限制</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in historyRows" :key="row.series.code">
              <td><strong>{{ row.series.name }}</strong><small>{{ row.series.points.length }} 条记录</small></td>
              <td>{{ formatHistoryPoint(row.previous) }}</td>
              <td>
                <button v-if="row.current" type="button" class="text-link button-reset" :disabled="reportLoading" @click="openReport(row.current.report_id)">
                  {{ formatHistoryPoint(row.current) }}
                </button>
              </td>
              <td v-if="typeof row.pair?.arithmetic_change === 'number'">
                ≈ {{ formatArithmeticChange(row.pair.arithmetic_change) }} {{ row.series.standard_unit }}
              </td>
              <td v-else>暂不计算</td>
              <td>
                <span v-if="!row.pair" class="history-limit">只有一份已确认报告</span>
                <span v-for="note in row.pair?.limitations ?? []" :key="note" class="history-limit">{{ note }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
