<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  ArrowRight,
  BadgeCheck,
  CheckCircle2,
  FlaskConical,
  Gauge,
  Info,
  LoaderCircle,
  MessageSquareText,
  ShieldCheck,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import { createExperiment, fetchActions, getApiErrorMessage } from '@/services/api'
import type { ActionTemplate } from '@/types'

const router = useRouter()
const actions = ref<ActionTemplate[]>([])
const selectedId = ref('')
const loading = ref(false)
const error = ref('')
const selectedAction = computed(() =>
  actions.value.find((action) => action.id === selectedId.value),
)

onMounted(async () => {
  loading.value = true
  try {
    actions.value = await fetchActions()
    selectedId.value = actions.value[0]?.id ?? ''
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
})

async function startExperiment() {
  if (!selectedId.value) return
  loading.value = true
  error.value = ''
  try {
    await createExperiment(selectedId.value)
    await router.push('/experiment')
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
      eyebrow="步骤 2"
      title="比较候选行动"
      description="候选项仅来自当前有效的低风险模板；适配分展示计算过程，不代表疗效概率。"
    />

    <div class="ranking-method-panel">
      <Gauge :size="20" />
      <div>
        <strong>排序规则：依据 40% + 短期可观察性 35% + 易执行性 25%</strong>
        <span>合成模板已经过产品规则校验，但仍待健康专业指导老师复核。</span>
      </div>
    </div>

    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-else-if="loading && !actions.length" class="loading-block">正在读取可用模板…</div>
    <div v-else-if="!actions.length" class="empty-state">
      当前没有满足报告确认、安全初筛、模板状态和数据量条件的候选行动。
    </div>

    <div class="action-list">
      <label
        v-for="(action, index) in actions"
        :key="action.id"
        class="action-card governed-action-card"
        :class="{ selected: selectedId === action.id }"
      >
        <input v-model="selectedId" type="radio" name="action" :value="action.id" />
        <div class="action-rank">0{{ index + 1 }}</div>
        <div class="action-body">
          <div class="action-title-row">
            <div>
              <span class="section-kicker">{{ action.category === 'activity' ? '活动行为' : '饮食行为' }}</span>
              <h2>{{ action.title }}</h2>
            </div>
            <span class="score-pill"><Gauge :size="15" /> 适配分 {{ action.score }}</span>
          </div>

          <div class="action-governance">
            <span><BadgeCheck :size="15" /> 模板 {{ action.template_version }}</span>
            <span>{{ action.review_label }}</span>
            <span>规则 {{ action.ranking_policy_version }}</span>
          </div>

          <p>{{ action.description }}</p>

          <div class="score-breakdown" :aria-label="`${action.title}适配分明细`">
            <div>
              <span>依据质量 · 权重 {{ action.score_components.evidence_weight }}%</span>
              <strong>{{ action.score_components.evidence_points }}</strong>
            </div>
            <div>
              <span>短期可观察性 · 权重 {{ action.score_components.observability_weight }}%</span>
              <strong>{{ action.score_components.observability_points }}</strong>
            </div>
            <div>
              <span>易执行性 · 权重 {{ action.score_components.ease_weight }}%</span>
              <strong>{{ action.score_components.ease_points }}</strong>
            </div>
          </div>
          <p class="rank-reason"><Info :size="15" /> {{ action.rank_reason }}</p>

          <div class="action-explanation">
            <MessageSquareText :size="18" />
            <div>
              <strong>受控解释</strong>
              <span>{{ action.explanation }}</span>
              <small>来源：{{ action.explanation_source }} · 策略 {{ action.explanation_policy_version }}</small>
            </div>
          </div>

          <div class="action-facts governed-facts">
            <div><CheckCircle2 :size="17" /><span><strong>观察指标</strong>{{ action.primary_metric }}</span></div>
            <div><FlaskConical :size="17" /><span><strong>依据摘要</strong>{{ action.evidence_summary }}</span></div>
            <div><CheckCircle2 :size="17" /><span><strong>适用条件</strong>{{ action.suitable_if }}</span></div>
            <div><ShieldCheck :size="17" /><span><strong>安全条件</strong>{{ action.safety_note }}</span></div>
          </div>

          <div class="safety-check-list">
            <span v-for="check in action.safety_checks" :key="check"><CheckCircle2 :size="14" /> {{ check }}</span>
          </div>
        </div>
        <span class="radio-indicator"><CheckCircle2 :size="21" /></span>
      </label>
    </div>

    <div class="sticky-action-bar">
      <div>
        <strong>{{ selectedAction ? `已选择：${selectedAction.title}` : '请选择一个可用行动' }}</strong>
        <span>将生成 14 天随机计划；7 个提醒日与 7 个常规日。</span>
      </div>
      <button class="button primary" :disabled="!selectedId || loading" @click="startExperiment">
        <LoaderCircle v-if="loading" :size="17" class="spinning" />
        <ArrowRight v-else :size="17" />
        生成计划
      </button>
    </div>
  </div>
</template>
