<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Check,
  Download,
  FileSearch,
  FileUp,
  LoaderCircle,
  RotateCcw,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  analyzeReport,
  confirmReport,
  confirmReportMetric,
  correctReportMetric,
  downloadReportSource,
  fetchLatestReport,
  getApiErrorMessage,
  retryReport,
} from '@/services/api'
import type { HealthMetric, ReportAnalysis } from '@/types'

interface MetricDraft {
  name: string
  value: number
  unit: string
  reference_range: string
}

const report = ref<ReportAnalysis | null>(null)
const drafts = ref<Record<string, MetricDraft>>({})
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const busyMetricId = ref('')
const error = ref('')
const success = ref('')

const confirmedCount = computed(
  () => report.value?.metrics.filter((metric) => metric.confirmed).length ?? 0,
)
const allFieldsConfirmed = computed(
  () => Boolean(report.value?.metrics.length) && confirmedCount.value === report.value?.metrics.length,
)

onMounted(async () => {
  try {
    setReport(await fetchLatestReport())
  } catch (requestError) {
    const message = getApiErrorMessage(requestError)
    if (message !== '尚无体检报告') error.value = message
  }
})

function setReport(value: ReportAnalysis) {
  report.value = value
  drafts.value = Object.fromEntries(
    value.metrics.map((metric) => [
      metric.id,
      {
        name: metric.name,
        value: metric.value,
        unit: metric.unit,
        reference_range: metric.reference_range,
      },
    ]),
  )
}

function replaceMetric(updated: HealthMetric) {
  if (!report.value) return
  report.value.metrics = report.value.metrics.map((metric) =>
    metric.id === updated.id ? updated : metric,
  )
  drafts.value[updated.id] = {
    name: updated.name,
    value: updated.value,
    unit: updated.unit,
    reference_range: updated.reference_range,
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
    success.value = '已生成合成 OCR 候选字段，请逐项核对后再完成报告确认。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
    try {
      setReport(await fetchLatestReport())
    } catch {
      // Keep the actionable upload error when no failed report was persisted.
    }
  } finally {
    loading.value = false
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
        draft.unit !== metric.unit ||
        draft.reference_range !== metric.reference_range),
  )
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
    replaceMetric(
      await correctReportMetric(report.value.report_id, metric.id, {
        name: draft.name.trim(),
        value: Number(draft.value),
        unit: draft.unit.trim(),
        reference_range: draft.reference_range.trim(),
      }),
    )
    success.value = `已保存并确认“${draft.name}”的修正。`
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    busyMetricId.value = ''
  }
}

async function finalizeReport() {
  if (!report.value || !allFieldsConfirmed.value) return
  loading.value = true
  error.value = ''
  try {
    await confirmReport(report.value.report_id)
    report.value.status = 'confirmed'
    success.value = '报告字段已逐项确认，可进入候选行动比较。'
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

function sourcePosition(metric: HealthMetric) {
  const [x = 0, y = 0] = metric.source_bbox
  return `第 ${metric.source_page} 页 · ${Math.round(x * 100)}%, ${Math.round(y * 100)}%`
}
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="步骤 1"
      title="报告解析与确认"
      description="每个 OCR 候选字段都必须由用户确认或修正，整份报告确认后才能进入行动排序。"
    />

    <div class="content-grid report-grid">
      <section class="panel upload-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">数据接入</span>
            <h2>上传合成报告</h2>
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
        <div class="privacy-note">
          <ShieldCheck :size="18" />
          <span>文件仅进入本地私有目录并通过登录接口访问；当前请勿上传任何真实报告。</span>
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
            <button
              v-if="report.storage_provider === 'local_private'"
              class="text-link button-reset"
              type="button"
              @click="downloadSource"
            >
              <Download :size="15" /> 下载源文件核对
            </button>
          </div>

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
                      <input v-model.trim="drafts[metric.id].name" maxlength="80" :disabled="metric.confirmed || report.status === 'confirmed'" />
                    </label>
                    <span class="source-excerpt">原文：{{ metric.raw_text }}</span>
                  </td>
                  <td>
                    <label class="inline-field compact">
                      <span>结果数值</span>
                      <input v-model.number="drafts[metric.id].value" type="number" step="any" :disabled="metric.confirmed || report.status === 'confirmed'" />
                    </label>
                  </td>
                  <td>
                    <label class="inline-field compact">
                      <span>单位</span>
                      <input v-model.trim="drafts[metric.id].unit" maxlength="32" :disabled="metric.confirmed || report.status === 'confirmed'" />
                    </label>
                  </td>
                  <td>
                    <label class="inline-field compact">
                      <span>参考范围</span>
                      <input v-model.trim="drafts[metric.id].reference_range" maxlength="64" :disabled="metric.confirmed || report.status === 'confirmed'" />
                    </label>
                  </td>
                  <td>
                    <span :class="['confidence-value', metric.confidence < 0.8 ? 'low' : '']">
                      {{ Math.round(metric.confidence * 100) }}%
                    </span>
                    <small>{{ sourcePosition(metric) }}</small>
                  </td>
                  <td>
                    <span v-if="metric.confirmed" class="status-badge safe">
                      {{ metric.review_status === 'corrected' ? '已修正' : '已确认' }}
                    </span>
                    <div v-else class="review-actions">
                      <button class="button compact-button secondary" :disabled="busyMetricId === metric.id" @click="confirmOne(metric)">
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
            <span v-else>所有字段已逐项处理，可以完成报告确认。</span>
            <button class="button primary" :disabled="loading || !allFieldsConfirmed || report.status === 'confirmed'" @click="finalizeReport">
              <Check :size="17" />
              {{ report.status === 'confirmed' ? '报告已确认' : '完成报告确认' }}
            </button>
          </div>
        </template>

        <div v-else class="empty-state">上传合成报告后，结构化候选指标会显示在这里。</div>
      </section>
    </div>
  </div>
</template>
