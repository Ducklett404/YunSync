<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ArrowRight, CircleAlert, FileCheck2, RefreshCw, UserRoundCog, UtensilsCrossed } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { useWorkspaceStore } from '@/stores/workspace'

const store = useWorkspaceStore()

onMounted(() => store.loadDashboard(true))

const confirmedMetrics = computed(() =>
  store.dashboard?.report?.status === 'confirmed'
    ? store.dashboard.metrics.filter((metric) => metric.confirmed)
    : [],
)
const flaggedMetrics = computed(() => confirmedMetrics.value.filter((metric) => metric.flag === 'attention'))
const reportState = computed(() => {
  if (!store.dashboard?.report) return '尚未上传'
  return store.dashboard.report.status === 'confirmed' ? '已确认' : '待确认'
})
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="体检后食养随访 · V2 过渡版"
      title="健康数据准备"
      description="先确认报告和个人档案，再查看经审核内容生成的食养方案。复查迭代将在后续里程碑开放。"
    >
      <button class="icon-button" title="刷新数据" :disabled="store.loading" @click="store.loadDashboard(true)">
        <RefreshCw :size="18" :class="{ spinning: store.loading }" />
      </button>
    </PageHeader>

    <div v-if="store.error" class="message error-message" role="alert">{{ store.error }}</div>
    <div v-else-if="store.loading && !store.dashboard" class="loading-block">正在加载演示数据…</div>

    <template v-else-if="store.dashboard">
      <div class="notice-strip">
        <CircleAlert :size="18" />
        <span>当前环境使用合成数据。指标展示仅供核对，不能据此诊断疾病或生成正式食养建议。</span>
      </div>

      <section class="summary-grid" aria-label="当前准备状态">
        <article class="summary-card">
          <div class="summary-icon teal"><FileCheck2 :size="20" /></div>
          <div>
            <span>最新报告</span>
            <strong>{{ reportState }}</strong>
            <small>{{ store.dashboard.report?.filename ?? '请先上传合成报告' }}</small>
          </div>
        </article>
        <article class="summary-card">
          <div class="summary-icon amber"><CircleAlert :size="20" /></div>
          <div>
            <span>已确认报告中的需关注指标</span>
            <strong>{{ flaggedMetrics.length }} 项</strong>
            <small>仅按报告参考范围提示</small>
          </div>
        </article>
        <article class="summary-card">
          <div class="summary-icon gray"><UtensilsCrossed :size="20" /></div>
          <div>
            <span>食养方案</span>
            <strong>可检查</strong>
            <small>仅在专业内容与安全规则发布后生成</small>
          </div>
        </article>
      </section>

      <section class="content-grid dashboard-grid">
        <div class="panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">第一步 · 报告数据</span>
              <h2>核对体检指标</h2>
            </div>
            <RouterLink class="text-link" to="/report">前往报告 <ArrowRight :size="16" /></RouterLink>
          </div>
          <div v-if="!confirmedMetrics.length" class="empty-state">
            {{ store.dashboard.report ? '请完成整份报告的逐项确认。' : '上传合成报告后，在原文旁逐项确认指标。' }}
          </div>
          <div v-else class="metric-list">
            <div v-for="metric in confirmedMetrics" :key="metric.id" class="metric-row">
              <div>
                <strong>{{ metric.name }}</strong>
                <span>参考 {{ metric.reference_range || '未提供' }}</span>
              </div>
              <div class="metric-value">
                <strong>{{ metric.value }}</strong>
                <span>{{ metric.unit }}</span>
                <em :class="metric.flag">{{ metric.flag === 'normal' ? '范围内' : metric.flag === 'attention' ? '需关注' : '待判定' }}</em>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">第二步 · 个人约束</span>
              <h2>完善健康档案</h2>
            </div>
            <UserRoundCog :size="22" class="muted-icon" />
          </div>
          <p class="panel-note">在档案中明确回答过敏、用药、疾病、肝肾情况、医生饮食限制和特殊状态。专业内容与安全规则审核完成前，不会生成正式食养方案。</p>
          <RouterLink class="button secondary full-width" to="/profile">查看当前档案 <ArrowRight :size="17" /></RouterLink>
          <RouterLink class="text-link" to="/care-plan">查看方案准备状态 <ArrowRight :size="16" /></RouterLink>
        </div>
      </section>
    </template>
  </div>
</template>
