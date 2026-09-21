<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ArrowRight, CircleAlert, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { fetchSafetyDecision, getApiErrorMessage } from '@/services/api'
import { canAccessHealthFlow } from '@/state/onboarding'
import type { SafetyDecision } from '@/types'

const decision = ref<SafetyDecision | null>(null)
const loading = ref(false)
const error = ref('')

async function loadDecision() {
  loading.value = true
  error.value = ''
  try {
    decision.value = await fetchSafetyDecision()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

function titleFor(value: SafetyDecision['decision']): string {
  switch (value) {
    case 'urgent_care': return '请及时寻求医疗帮助'
    case 'consult_professional': return '请先咨询专业人员'
    case 'complete_information': return '请先补齐资料'
    case 'awaiting_review_rules': return '等待专业规则审核'
    case 'ready_general_guidance': return '基础安全门禁已通过'
  }
}

onMounted(loadDecision)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="V2 · 安全分流"
      title="查看当前安全提示"
      description="系统根据初筛、食养安全档案和报告原件核对结果给出保守提示，不依据单个指标诊断疾病。"
    >
      <button class="icon-button" title="刷新安全提示" :disabled="loading" @click="loadDecision">
        <RefreshCw :size="18" :class="{ spinning: loading }" />
      </button>
    </PageHeader>

    <div v-if="error" class="message error-message" role="alert">
      {{ error }} <RouterLink class="text-link" to="/start">返回授权与初筛 <ArrowRight :size="16" /></RouterLink>
    </div>
    <div v-else-if="loading && !decision" class="loading-block">正在读取安全提示…</div>

    <section v-else-if="decision" class="panel" :aria-live="decision.decision === 'urgent_care' ? 'assertive' : 'polite'">
      <div class="panel-heading">
        <div>
          <span class="section-kicker">{{ decision.tier ? `安全分流 ${decision.tier} 层` : '资料状态' }}</span>
          <h2>{{ titleFor(decision.decision) }}</h2>
        </div>
        <CircleAlert v-if="decision.tier" :size="24" class="muted-icon" />
        <ShieldCheck v-else :size="24" class="muted-icon" />
      </div>
      <p class="panel-note">{{ decision.message }}</p>
      <div v-if="decision.missing_items.length" class="notice-strip">
        <CircleAlert :size="18" />
        <span>待完成：{{ decision.missing_items.join('、') }}</span>
      </div>
      <p class="panel-note">{{ decision.can_generate_plan ? '当前仅表示可以进入已审核内容候选流程，仍不代表已经生成正式方案。' : '当前状态会阻止正式食养方案。' }} 安全规则版本：{{ decision.rule_version }}</p>
      <div class="account-actions">
        <RouterLink v-if="decision.decision === 'complete_information'" class="button secondary" to="/profile">
          补充安全档案 <ArrowRight :size="17" />
        </RouterLink>
        <RouterLink v-if="decision.decision === 'complete_information' && canAccessHealthFlow()" class="button secondary" to="/report">
          核对报告 <ArrowRight :size="17" />
        </RouterLink>
        <RouterLink v-if="decision.decision !== 'urgent_care'" class="text-link" to="/start">查看授权与初筛</RouterLink>
      </div>
    </section>
  </div>
</template>
