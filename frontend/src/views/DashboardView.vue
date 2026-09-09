<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ArrowRight, CalendarCheck, CircleAlert, FileCheck2, Footprints, RefreshCw } from 'lucide-vue-next'
import MetricChart from '@/components/MetricChart.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useWorkspaceStore } from '@/stores/workspace'

const store = useWorkspaceStore()

onMounted(() => store.loadDashboard())

const flaggedMetrics = computed(() => store.dashboard?.metrics.filter((item) => item.flag !== 'normal') ?? [])
const result = computed(() => store.dashboard?.experiment?.result)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="今日概览"
      title="健康行动工作台"
      description="先确认数据，再选择一项值得验证的低风险行动。"
    >
      <button class="icon-button" title="刷新数据" :disabled="store.loading" @click="store.loadDashboard(true)">
        <RefreshCw :size="18" :class="{ spinning: store.loading }" />
      </button>
    </PageHeader>

    <div v-if="store.error" class="message error-message">{{ store.error }}</div>
    <div v-else-if="store.loading && !store.dashboard" class="loading-block">正在加载演示数据…</div>

    <template v-else-if="store.dashboard">
      <div class="notice-strip">
        <CircleAlert :size="18" />
        <span>{{ store.dashboard.notice }}</span>
      </div>

      <section class="summary-grid" aria-label="核心状态">
        <article class="summary-card">
          <div class="summary-icon teal"><FileCheck2 :size="20" /></div>
          <div>
            <span>最新报告</span>
            <strong>{{ store.dashboard.report?.status === 'confirmed' ? '已确认' : '待确认' }}</strong>
            <small>{{ store.dashboard.report?.filename }}</small>
          </div>
        </article>
        <article class="summary-card">
          <div class="summary-icon amber"><CircleAlert :size="20" /></div>
          <div>
            <span>需关注指标</span>
            <strong>{{ flaggedMetrics.length }} 项</strong>
            <small>仅作健康管理提示</small>
          </div>
        </article>
        <article class="summary-card">
          <div class="summary-icon green"><CalendarCheck :size="20" /></div>
          <div>
            <span>实验进度</span>
            <strong>{{ store.dashboard.experiment?.progress ?? 0 }} / 14 天</strong>
            <small>{{ store.dashboard.experiment?.action_title ?? '尚未选择行动' }}</small>
          </div>
        </article>
      </section>

      <section class="content-grid dashboard-grid">
        <div class="panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">已确认数据</span>
              <h2>健康指标</h2>
            </div>
            <RouterLink class="text-link" to="/report">查看报告 <ArrowRight :size="16" /></RouterLink>
          </div>
          <div class="metric-list">
            <div v-for="metric in store.dashboard.metrics" :key="metric.id" class="metric-row">
              <div>
                <strong>{{ metric.name }}</strong>
                <span>参考 {{ metric.reference_range }}</span>
              </div>
              <div class="metric-value">
                <strong>{{ metric.value }}</strong>
                <span>{{ metric.unit }}</span>
                <em :class="metric.flag">{{ metric.flag === 'normal' ? '范围内' : '需关注' }}</em>
              </div>
            </div>
          </div>
        </div>

        <div class="panel experiment-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">当前个人实验</span>
              <h2>{{ store.dashboard.experiment?.action_title }}</h2>
            </div>
            <Footprints :size="22" class="muted-icon" />
          </div>
          <div class="progress-label">
            <span>记录进度</span>
            <strong>{{ store.dashboard.experiment?.progress ?? 0 }} / 14</strong>
          </div>
          <div class="progress-track">
            <span :style="{ width: `${((store.dashboard.experiment?.progress ?? 0) / 14) * 100}%` }"></span>
          </div>
          <MetricChart
            :treatment="result?.treatment_average ?? null"
            :control="result?.control_average ?? null"
            :metric-label="result?.metric_label ?? '主要指标'"
            :metric-unit="result?.metric_unit ?? ''"
          />
          <p class="panel-note">{{ result?.message }}</p>
          <RouterLink class="button primary full-width" to="/experiment">
            继续今日记录 <ArrowRight :size="17" />
          </RouterLink>
        </div>
      </section>

      <section class="panel compact-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">下一步</span>
            <h2>候选行动排序</h2>
          </div>
          <RouterLink class="text-link" to="/actions">比较全部 <ArrowRight :size="16" /></RouterLink>
        </div>
        <div class="action-table-wrap">
          <table class="data-table">
            <thead><tr><th>行动</th><th>主要指标</th><th>综合适配分</th><th>风险</th></tr></thead>
            <tbody>
              <tr v-for="action in store.dashboard.actions" :key="action.id">
                <td><strong>{{ action.title }}</strong><span>{{ action.description }}</span></td>
                <td>{{ action.primary_metric }}</td>
                <td><span class="score-value">{{ action.score }}</span></td>
                <td><span class="status-badge safe">低风险</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
