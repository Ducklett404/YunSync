<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Check, FileSearch, FileUp, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { analyzeReport, confirmReport, fetchLatestReport, getApiErrorMessage } from '@/services/api'
import type { ReportAnalysis } from '@/types'

const report = ref<ReportAnalysis | null>(null)
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const error = ref('')
const success = ref('')

onMounted(async () => {
  try {
    report.value = await fetchLatestReport()
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  }
})

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
  success.value = ''
}

async function runAnalysis() {
  if (!selectedFile.value) return
  loading.value = true
  error.value = ''
  try {
    report.value = await analyzeReport(selectedFile.value)
    success.value = '已生成合成 OCR 结果，请逐项确认。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function confirmAll() {
  if (!report.value) return
  loading.value = true
  try {
    await confirmReport(report.value.report_id)
    report.value.status = 'confirmed'
    report.value.metrics = report.value.metrics.map((metric) => ({ ...metric, confirmed: true }))
    success.value = '所有字段已确认，可进入候选行动比较。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="步骤 1"
      title="报告解析与确认"
      description="OCR 结果必须由用户确认后才能进入行动排序。"
    />

    <div class="content-grid report-grid">
      <section class="panel upload-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">数据接入</span>
            <h2>上传体检报告</h2>
          </div>
          <FileUp :size="22" class="muted-icon" />
        </div>
        <label class="upload-zone">
          <input type="file" accept=".pdf,.png,.jpg,.jpeg" @change="onFileChange" />
          <FileSearch :size="34" />
          <strong>{{ selectedFile?.name ?? '选择 PDF 或图片' }}</strong>
          <span>最大 5 MB；初版仅返回合成演示结果</span>
        </label>
        <button class="button primary full-width" :disabled="!selectedFile || loading" @click="runAnalysis">
          <LoaderCircle v-if="loading" :size="17" class="spinning" />
          <FileSearch v-else :size="17" />
          解析报告
        </button>
        <div class="privacy-note">
          <ShieldCheck :size="18" />
          <span>演示阶段请勿上传包含姓名、证件号码或联系方式的真实报告。</span>
        </div>
      </section>

      <section class="panel metrics-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">识别结果</span>
            <h2>{{ report?.filename ?? '尚无报告' }}</h2>
          </div>
          <span v-if="report" class="status-badge" :class="report.status === 'confirmed' ? 'safe' : 'pending'">
            {{ report.status === 'confirmed' ? '已确认' : '待确认' }}
          </span>
        </div>

        <div v-if="error" class="message error-message">{{ error }}</div>
        <div v-if="success" class="message success-message">{{ success }}</div>

        <div v-if="report" class="action-table-wrap">
          <table class="data-table">
            <thead><tr><th>指标</th><th>结果</th><th>参考范围</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="metric in report.metrics" :key="metric.id">
                <td><strong>{{ metric.name }}</strong></td>
                <td>{{ metric.value }} {{ metric.unit }}</td>
                <td>{{ metric.reference_range }}</td>
                <td><span :class="['status-badge', metric.flag === 'normal' ? 'safe' : 'pending']">{{ metric.flag === 'normal' ? '范围内' : '需关注' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-state">上传报告后，结构化指标会显示在这里。</div>

        <button v-if="report" class="button secondary" :disabled="loading || report.status === 'confirmed'" @click="confirmAll">
          <Check :size="17" />
          {{ report.status === 'confirmed' ? '字段已确认' : '确认全部字段' }}
        </button>
      </section>
    </div>
  </div>
</template>

