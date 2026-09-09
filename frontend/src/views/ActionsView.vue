<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowRight, CheckCircle2, FlaskConical, Gauge, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import { createExperiment, fetchActions, getApiErrorMessage } from '@/services/api'
import type { ActionTemplate } from '@/types'

const router = useRouter()
const actions = ref<ActionTemplate[]>([])
const selectedId = ref('')
const loading = ref(false)
const error = ref('')

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
      title="选择一项候选行动"
      description="一次只验证一个明确问题，避免多项习惯同时变化。"
    />

    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-else-if="loading && !actions.length" class="loading-block">正在生成候选行动…</div>
    <div v-else-if="!actions.length" class="empty-state">
      请先完成报告解析并确认识别字段，再生成候选行动。
    </div>

    <div class="action-list">
      <label
        v-for="(action, index) in actions"
        :key="action.id"
        class="action-card"
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
            <span class="score-pill"><Gauge :size="15" /> {{ action.score }}</span>
          </div>
          <p>{{ action.description }}</p>
          <div class="action-facts">
            <div><CheckCircle2 :size="17" /><span><strong>观察指标</strong>{{ action.primary_metric }}</span></div>
            <div><FlaskConical :size="17" /><span><strong>依据摘要</strong>{{ action.evidence_summary }}</span></div>
            <div><ShieldCheck :size="17" /><span><strong>安全条件</strong>{{ action.safety_note }}</span></div>
          </div>
        </div>
        <span class="radio-indicator"><CheckCircle2 :size="21" /></span>
      </label>
    </div>

    <div class="sticky-action-bar">
      <div>
        <strong>将生成 14 天随机交叉计划</strong>
        <span>7 个提醒日与 7 个常规日，仅用于探索性个人比较。</span>
      </div>
      <button class="button primary" :disabled="!selectedId || loading" @click="startExperiment">
        <LoaderCircle v-if="loading" :size="17" class="spinning" />
        <ArrowRight v-else :size="17" />
        生成计划
      </button>
    </div>
  </div>
</template>
