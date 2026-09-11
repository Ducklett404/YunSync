<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  CircleCheck,
  Info,
  LoaderCircle,
  Sparkles,
} from 'lucide-vue-next'
import MetricChart from '@/components/MetricChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import {
  fetchCurrentExperiment,
  fetchExperimentResult,
  getApiErrorMessage,
  saveNextStep,
} from '@/services/api'
import type { Experiment, ExperimentResult, NextStepCode } from '@/types'

const experiment = ref<Experiment | null>(null)
const result = ref<ExperimentResult | null>(null)
const error = ref('')
const success = ref('')
const savingChoice = ref<NextStepCode | null>(null)

const differenceLabel = computed(() => {
  if (result.value?.observed_difference == null) return '暂不判断'
  const prefix = result.value.observed_difference > 0 ? '+' : ''
  return `${prefix}${result.value.observed_difference} ${result.value.metric_unit}`
})

const intervalLabel = computed(() => {
  if (result.value?.bootstrap_ci_lower == null || result.value.bootstrap_ci_upper == null) {
    return '样本不足，未计算'
  }
  return `${result.value.bootstrap_ci_lower} 至 ${result.value.bootstrap_ci_upper} ${result.value.metric_unit}`
})

const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    data_insufficient: '记录不足',
    possible_benefit: '观察方向偏向有利',
    possible_unfavorable: '观察方向偏向不利',
    uncertain: '方向仍不确定',
  }
  return labels[result.value?.status ?? ''] ?? '探索性结果'
})

const missingSummary = computed(() => {
  if (!result.value || result.value.missing_days === 0) return '无主要指标缺失'
  const labels: Record<string, string> = {
    forgot: '忘记记录',
    device_unavailable: '设备不可用',
    physical_discomfort: '身体不适',
    unplanned_event: '计划外事件',
    other: '其他',
    unspecified: '未说明',
    not_recorded: '尚未记录',
  }
  return Object.entries(result.value.missing_reason_counts)
    .map(([reason, count]) => `${labels[reason] ?? reason} ${count} 天`)
    .join(' · ')
})

async function chooseNextStep(code: NextStepCode) {
  if (!experiment.value || savingChoice.value) return
  error.value = ''
  success.value = ''
  savingChoice.value = code
  try {
    await saveNextStep(experiment.value.id, code)
    result.value = await fetchExperimentResult(experiment.value.id)
    success.value = '下一步选择已保存，你可以随时改选。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    savingChoice.value = null
  }
}

onMounted(async () => {
  try {
    experiment.value = await fetchCurrentExperiment()
    result.value = await fetchExperimentResult(experiment.value.id)
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  }
})
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="步骤 4"
      title="个人结果复盘"
      description="同时查看均值、中位数、有效率、缺失与不确定区间，再决定下一轮怎么做。"
    />
    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-if="success" class="message success-message">{{ success }}</div>

    <template v-if="result && experiment">
      <section class="result-callout">
        <div class="result-icon"><BarChart3 :size="25" /></div>
        <div>
          <span>{{ experiment.action_title }} · {{ statusLabel }}</span>
          <h2>{{ result.message }}</h2>
          <p>有效率 {{ result.effective_rate }}%，完成率 {{ result.completion_rate }}%；两者口径独立。</p>
        </div>
        <div class="difference-value"><span>提醒日 − 常规日</span><strong>{{ differenceLabel }}</strong></div>
      </section>

      <div class="content-grid result-grid">
        <section class="panel">
          <div class="panel-heading">
            <div><span class="section-kicker">描述统计</span><h2>{{ result.metric_label }}</h2></div>
            <span class="analysis-version">{{ result.analysis_version }}</span>
          </div>
          <MetricChart
            :treatment="result.treatment_average"
            :control="result.control_average"
            :treatment-median="result.treatment_median"
            :control-median="result.control_median"
            :metric-label="result.metric_label"
            :metric-unit="result.metric_unit"
          />
          <div class="result-stat-row four-up">
            <div><span>提醒日均值</span><strong>{{ result.treatment_average ?? '—' }} {{ result.treatment_average == null ? '' : result.metric_unit }}</strong></div>
            <div><span>常规日均值</span><strong>{{ result.control_average ?? '—' }} {{ result.control_average == null ? '' : result.metric_unit }}</strong></div>
            <div><span>提醒日中位数</span><strong>{{ result.treatment_median ?? '—' }} {{ result.treatment_median == null ? '' : result.metric_unit }}</strong></div>
            <div><span>常规日中位数</span><strong>{{ result.control_median ?? '—' }} {{ result.control_median == null ? '' : result.metric_unit }}</strong></div>
          </div>
          <div class="uncertainty-box">
            <span>95% 重采样区间（{{ result.bootstrap_iterations }} 次）</span>
            <strong>{{ intervalLabel }}</strong>
            <p>区间跨过 0 时，只能说明方向仍不确定，不应解读为“没有任何差异”。</p>
          </div>
        </section>

        <section class="panel conclusion-panel">
          <div class="panel-heading"><div><span class="section-kicker">受控复盘</span><h2>如何理解结果</h2></div><Sparkles :size="21" class="muted-icon" /></div>
          <div class="interpretation positive"><CircleCheck :size="19" /><span><strong>可以描述</strong>{{ result.explanation }}</span></div>
          <div class="interpretation warning"><AlertTriangle :size="19" /><span><strong>不能描述</strong>该行动已经治疗疾病、必然有效或适用于其他人。</span></div>
          <div class="explanation-meta">来源 {{ result.explanation_source }} · 策略 {{ result.explanation_policy_version }}</div>
          <ul class="caveat-list"><li v-for="item in result.caveats" :key="item">{{ item }}</li></ul>
          <RouterLink class="button secondary full-width" to="/experiment">补充记录 <ArrowRight :size="17" /></RouterLink>
        </section>
      </div>

      <section class="panel data-quality-panel">
        <div class="panel-heading"><div><span class="section-kicker">数据质量</span><h2>有效、缺失与异常值</h2></div><Info :size="21" class="muted-icon" /></div>
        <div class="quality-grid">
          <div><span>有效记录</span><strong>{{ result.valid_days }} / 14 天</strong><small>提醒日 {{ result.treatment_days }} · 常规日 {{ result.control_days }}</small></div>
          <div><span>主要指标缺失</span><strong>{{ result.missing_days }} 天</strong><small>{{ missingSummary }}</small></div>
          <div><span>IQR 异常值</span><strong>{{ result.outlier_count }} 个</strong><small>主分析保留原值；异常值只用于敏感性对照</small></div>
          <div><span>敏感性差异</span><strong>{{ result.sensitivity_difference ?? '不适用' }}<template v-if="result.sensitivity_difference != null"> {{ result.metric_unit }}</template></strong><small>仅在可剔除异常值且两组仍有足够记录时显示</small></div>
        </div>
      </section>

      <section class="panel next-step-panel">
        <div class="panel-heading"><div><span class="section-kicker">下一轮决策</span><h2>选择一个可撤回的下一步</h2></div></div>
        <p class="panel-note">系统建议仅依据本轮数据质量与观察方向，你仍可以选择更符合自身情况的方案。</p>
        <div class="next-step-grid">
          <button
            v-for="option in result.next_step_options"
            :key="option.code"
            type="button"
            class="next-step-card"
            :class="{ recommended: option.recommended, selected: option.selected }"
            :disabled="savingChoice !== null"
            @click="chooseNextStep(option.code)"
          >
            <span class="next-step-flags">
              <em v-if="option.recommended">系统建议</em>
              <em v-if="option.selected" class="selected-flag"><Check :size="13" />已选择</em>
            </span>
            <strong>{{ option.title }}</strong>
            <small>{{ option.description }}</small>
            <LoaderCircle v-if="savingChoice === option.code" :size="17" class="spinning" />
            <ArrowRight v-else :size="17" />
          </button>
        </div>
      </section>
    </template>
  </div>
</template>
