<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { AlertTriangle, ArrowRight, BarChart3, CircleCheck, Info } from 'lucide-vue-next'
import MetricChart from '@/components/MetricChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import { fetchCurrentExperiment, fetchExperimentResult, getApiErrorMessage } from '@/services/api'
import type { Experiment, ExperimentResult } from '@/types'

const experiment = ref<Experiment | null>(null)
const result = ref<ExperimentResult | null>(null)
const error = ref('')

const differenceLabel = computed(() => {
  if (result.value?.observed_difference == null) return '等待更多记录'
  const prefix = result.value.observed_difference > 0 ? '+' : ''
  return `${prefix}${result.value.observed_difference} ${result.value.metric_unit}`
})

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
      title="个人结果评估"
      description="只描述当前记录中的差异，并同时展示数据量和不确定性。"
    />
    <div v-if="error" class="message error-message">{{ error }}</div>

    <template v-if="result && experiment">
      <section class="result-callout">
        <div class="result-icon"><BarChart3 :size="25" /></div>
        <div>
          <span>{{ experiment.action_title }}</span>
          <h2>{{ result.message }}</h2>
          <p>当前完成率 {{ result.completion_rate }}%，提醒日 {{ result.treatment_days }} 次，常规日 {{ result.control_days }} 次。</p>
        </div>
        <div class="difference-value"><span>观察差异</span><strong>{{ differenceLabel }}</strong></div>
      </section>

      <div class="content-grid result-grid">
        <section class="panel">
          <div class="panel-heading"><div><span class="section-kicker">主要指标</span><h2>{{ result.metric_label }}</h2></div></div>
          <MetricChart
            :treatment="result.treatment_average"
            :control="result.control_average"
            :metric-label="result.metric_label"
            :metric-unit="result.metric_unit"
          />
          <div class="result-stat-row">
            <div><span>提醒日均值</span><strong>{{ result.treatment_average ?? '—' }} {{ result.treatment_average == null ? '' : result.metric_unit }}</strong></div>
            <div><span>常规日均值</span><strong>{{ result.control_average ?? '—' }} {{ result.control_average == null ? '' : result.metric_unit }}</strong></div>
            <div><span>有效观测</span><strong>{{ result.treatment_days + result.control_days }} 次</strong></div>
          </div>
        </section>

        <section class="panel conclusion-panel">
          <div class="panel-heading"><div><span class="section-kicker">结论口径</span><h2>如何理解结果</h2></div><Info :size="21" class="muted-icon" /></div>
          <div class="interpretation positive"><CircleCheck :size="19" /><span><strong>可以描述</strong>{{ result.message }}</span></div>
          <div class="interpretation warning"><AlertTriangle :size="19" /><span><strong>不能描述</strong>该行动已经治疗疾病、稳定减重或必然适用于其他人。</span></div>
          <ul class="caveat-list"><li v-for="item in result.caveats" :key="item">{{ item }}</li></ul>
          <RouterLink class="button secondary full-width" to="/experiment">补充记录 <ArrowRight :size="17" /></RouterLink>
        </section>
      </div>
    </template>
  </div>
</template>
