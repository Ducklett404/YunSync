<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ArrowRight, CircleAlert, RefreshCw, UtensilsCrossed } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  activateCarePlan, createCarePlan, downloadCarePlan, fetchCurrentCarePlan, fetchLatestReport,
  fetchSafetyDecision, getApiErrorMessage,
} from '@/services/api'
import type { CarePlan, CarePlanRequest, ReportAnalysis, SafetyDecision } from '@/types'

const plan = ref<CarePlan | null>(null)
const report = ref<ReportAnalysis | null>(null)
const safety = ref<SafetyDecision | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const form = reactive<CarePlanRequest>({
  selected_metric_codes: [], servings: 1, start_on: null, max_minutes: null,
  max_budget_yuan_per_serving: null, available_cookware: [], preferred_taste: '',
  region: '', unavailable_ingredient_codes: [],
})
const cookwareText = ref('')
const unavailableText = ref('')
const selectableMetrics = computed(() => report.value?.status === 'confirmed'
  ? report.value.metrics.filter((metric) => metric.confirmed)
  : [])
const recipeNames = computed(() => new Map(plan.value?.snapshot.recipes.map((recipe) => [recipe.code, recipe.title]) ?? []))

function parseList(value: string): string[] {
  return [...new Set(value.split(/[，,\n]/).map((part) => part.trim()).filter(Boolean))]
}

function toggleMetric(code: string) {
  const index = form.selected_metric_codes.indexOf(code)
  if (index >= 0) form.selected_metric_codes.splice(index, 1)
  else if (form.selected_metric_codes.length < 3) form.selected_metric_codes.push(code)
}

async function load() {
  loading.value = true
  error.value = ''
  const results = await Promise.allSettled([
    fetchSafetyDecision(), fetchCurrentCarePlan(), fetchLatestReport(),
  ] as const)
  if (results[0].status === 'fulfilled') safety.value = results[0].value
  else error.value = getApiErrorMessage(results[0].reason)
  if (results[1].status === 'fulfilled') plan.value = results[1].value
  else error.value ||= getApiErrorMessage(results[1].reason)
  if (results[2].status === 'fulfilled') {
    report.value = results[2].value
    if (!form.selected_metric_codes.length) {
      form.selected_metric_codes = results[2].value.metrics
        .filter((metric) => metric.confirmed && metric.flag === 'attention')
        .slice(0, 3).map((metric) => metric.code)
    }
  }
  loading.value = false
}

async function generate() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    plan.value = await createCarePlan({
      ...form,
      selected_metric_codes: [...form.selected_metric_codes],
      available_cookware: parseList(cookwareText.value),
      unavailable_ingredient_codes: parseList(unavailableText.value),
    })
    notice.value = '方案草案已生成，请逐项查看后确认。'
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

async function activate() {
  if (!plan.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    plan.value = await activateCarePlan(plan.value.id)
    notice.value = '方案已确认，7 天安排和采购清单已锁定。'
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

async function exportPlan() {
  if (!plan.value) return
  error.value = ''
  try {
    const blob = await downloadCarePlan(plan.value.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `yunsync-care-plan-${plan.value.id}.json`
    link.click()
    URL.revokeObjectURL(url)
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <PageHeader eyebrow="V2 · M5–M6 食养方案" title="食养方案与一周安排"
      description="从已确认指标和经专业审核发布的食谱中生成一周示例餐食，材料和采购量可逐项核对。">
      <button class="icon-button" title="刷新方案状态" :disabled="loading" @click="load">
        <RefreshCw :size="18" :class="{ spinning: loading }" />
      </button>
    </PageHeader>

    <div v-if="error" class="message error-message" role="alert">{{ error }}</div>
    <div v-if="notice" class="message" role="status">{{ notice }}</div>
    <div v-if="loading" class="loading-block">正在读取方案状态…</div>

    <template v-else>
      <div class="notice-strip">
        <CircleAlert :size="18" />
        <span>目前演示食谱仍待专业审核。没有真实专业审核发布的食谱和安全规则时，系统不会生成正式方案。</span>
      </div>

      <section v-if="safety && !safety.can_generate_plan" class="panel" role="status">
        <span class="section-kicker">生成前安全门禁</span>
        <h2>暂不能生成方案</h2>
        <p class="panel-note">{{ safety.message }}</p>
        <p v-if="safety.missing_items.length" class="panel-note">待完成：{{ safety.missing_items.join('、') }}</p>
        <div class="account-actions">
          <RouterLink class="button secondary" to="/report">核对报告 <ArrowRight :size="16" /></RouterLink>
          <RouterLink class="button secondary" to="/profile">完善安全档案 <ArrowRight :size="16" /></RouterLink>
          <RouterLink class="text-link" to="/safety">查看安全提示</RouterLink>
        </div>
      </section>

      <section class="panel plan-form" aria-label="方案条件">
        <div class="panel-heading">
          <div><span class="section-kicker">第一步 · 匹配条件</span><h2>选择关注指标和烹饪条件</h2></div>
          <UtensilsCrossed :size="22" class="muted-icon" />
        </div>
        <p class="panel-note">最多选择 3 个已确认指标。排序仅表示模板匹配程度，不代表诊断或疗效概率。</p>
        <div v-if="!selectableMetrics.length" class="empty-state">尚无整份已确认报告。请先到报告页逐项核对。</div>
        <fieldset v-else class="plan-metric-options">
          <legend>关联指标</legend>
          <label v-for="metric in selectableMetrics" :key="metric.id">
            <input type="checkbox" :checked="form.selected_metric_codes.includes(metric.code)"
              :disabled="!form.selected_metric_codes.includes(metric.code) && form.selected_metric_codes.length >= 3"
              @change="toggleMetric(metric.code)" />
            <span>{{ metric.name }} · {{ metric.value }} {{ metric.unit }}</span>
          </label>
        </fieldset>
        <div class="plan-fields">
          <label>每次制作份数 <input v-model.number="form.servings" type="number" min="1" max="8" /></label>
          <label>开始日期 <input v-model="form.start_on" type="date" /></label>
          <label>最长制作时间（分钟，可选） <input v-model.number="form.max_minutes" type="number" min="5" max="360" placeholder="不限" /></label>
          <label>每份预算上限（元，可选） <input v-model.number="form.max_budget_yuan_per_serving" type="number" min="0" max="10000" step="0.1" placeholder="不限" /></label>
          <label>可用厨具（逗号分隔，可选） <input v-model="cookwareText" placeholder="如 汤锅,刀具" /></label>
          <label>口味标签（可选） <input v-model="form.preferred_taste" maxlength="80" placeholder="仅匹配审核模板已有标签" /></label>
          <label>地域标签（可选） <input v-model="form.region" maxlength="80" placeholder="仅匹配审核模板已有标签" /></label>
          <label>暂不可得食材代码（逗号分隔，可选） <input v-model="unavailableText" placeholder="将优先使用审核过的替代材料" /></label>
        </div>
        <button class="button primary" :disabled="saving || !safety?.can_generate_plan || !form.selected_metric_codes.length || plan?.status === 'ACTIVE' || plan?.status === 'READY' || plan?.pause_reason === 'new_report' || plan?.pause_reason === 'adverse_feedback'"
          @click="generate">{{ saving ? '正在校验…' : '生成方案草案' }}</button>
        <p v-if="plan?.pause_reason === 'new_report'" class="panel-note">新报告已到，请到 <RouterLink to="/follow-up">执行与复查</RouterLink> 页面完成对比并生成新版本。</p>
        <p v-if="plan?.pause_reason === 'adverse_feedback'" class="panel-note">因不适已暂停，需先寻求专业评估，系统不自动生成新方案。</p>
      </section>

      <template v-if="plan">
        <section class="panel">
          <div class="panel-heading">
            <div><span class="section-kicker">第二步 · 方案 {{ plan.status }}</span><h2>{{ plan.status === 'PAUSED' ? '方案已暂停，请重新评估' : '本期方案摘要' }}</h2></div>
          </div>
          <p class="panel-note">{{ plan.snapshot.general_principle }}</p>
          <p class="panel-note">{{ plan.snapshot.professional_consultation }}</p>
          <ul class="caveat-list"><li v-for="goal in plan.snapshot.goals" :key="goal.metric_id">{{ goal.statement }} 原记录：{{ goal.value }} {{ goal.unit }}；原参考范围：{{ goal.reference_range }}（{{ goal.report_date }}）</li></ul>
          <p class="panel-note">安全规则：{{ plan.snapshot.safety_rule_version }} · 解释方式：已审核模板与固定文案</p>
          <p class="panel-note">禁忌版本：{{ plan.snapshot.contraindication_refs.join('、') || '本期食谱无专属禁忌条目' }} · 排序规则：{{ plan.snapshot.ranking_policy_version }}</p>
          <button v-if="plan.status === 'READY'" class="button primary" :disabled="saving" @click="activate">核对后确认方案</button>
          <button class="button secondary" @click="exportPlan">导出方案与采购清单 JSON</button>
          <RouterLink class="button secondary" to="/follow-up">记录执行与复查</RouterLink>
          <p v-if="plan.status === 'PAUSED'" class="message error-message">{{ plan.pause_reason === 'adverse_feedback' ? '已记录不适，请停止执行并寻求专业评估。' : '报告、安全条件或内容版本已变化，此方案仅供历史核对。' }}</p>
        </section>

        <section class="panel">
          <span class="section-kicker">第三步 · 食谱卡</span>
          <h2>已审核食谱（{{ plan.snapshot.recipes.length }}）</h2>
          <div class="plan-recipes">
            <details v-for="recipe in plan.snapshot.recipes" :key="recipe.code" class="plan-recipe">
              <summary><strong>{{ recipe.title }}</strong><span>{{ recipe.servings }} 人份 · {{ recipe.total_minutes }} 分钟 · 匹配分 {{ recipe.score }}</span></summary>
              <p>{{ recipe.goal_statement }} {{ recipe.reason }}</p>
              <p>排序依据：审核来源 {{ recipe.score_breakdown.approved_evidence }}、目标 {{ recipe.score_breakdown.goal_match }}、偏好 {{ recipe.score_breakdown.preference_match }}、可执行性 {{ recipe.score_breakdown.feasibility }}、材料可得性 {{ recipe.score_breakdown.availability }}。</p>
              <p>关联指标：{{ recipe.matched_metric_codes.join('、') }} · 模板 {{ recipe.code }}@{{ recipe.version }}</p>
              <p>营养标签：{{ recipe.nutrition_tags.join('、') || '未标注' }} · 估计每份成本：{{ recipe.estimated_cost_yuan_per_serving === null ? '未标注' : `${recipe.estimated_cost_yuan_per_serving} 元` }}</p>
              <h3>材料与用量</h3>
              <ul><li v-for="material in recipe.materials" :key="`${material.code}@${material.version}`">
                {{ material.title }} {{ material.grams }} g（{{ material.edible_part }}）；{{ material.preparation }}
                <span v-if="material.substituted_for">，替代原料 {{ material.substituted_for }}</span>
                <small v-if="material.alternatives.length">；可用替代：{{ material.alternatives.map((item) => `${item.title} ${item.grams} g（${item.note}）`).join('、') }}</small>
              </li></ul>
              <h3>准备和制作</h3>
              <ul><li v-for="step in recipe.preprocessing" :key="step">{{ step }}</li></ul>
              <ol><li v-for="step in recipe.steps" :key="step.order">{{ step.instruction }}（{{ step.duration_minutes }} 分钟，{{ step.heat }}；厨具：{{ step.cookware.join('、') }}）</li></ol>
              <p>频次：{{ recipe.frequency }}（本周最多安排 {{ recipe.max_weekly_uses }} 次）· 周期：{{ recipe.cycle }} · 份量：{{ recipe.serving_note }}</p>
              <p>外食或同类选择：{{ recipe.dining_alternatives.join('、') }}</p>
              <p>注意：{{ recipe.caution }}</p>
              <small>来源：{{ recipe.source_refs.join('、') }} · 审核记录 {{ recipe.review_id }}</small>
            </details>
          </div>
        </section>

        <section class="panel">
          <span class="section-kicker">第四步 · 安排与采购</span><h2>7 天示例安排</h2>
          <p class="panel-note">每天列出一项示例餐食，并非全天菜单或营养处方。</p>
          <div class="plan-week"><div v-for="day in plan.snapshot.schedule" :key="day.day"><strong>第 {{ day.day }} 天 · {{ day.date }}</strong><span>{{ recipeNames.get(day.recipe_code) }} · {{ day.servings }} 人份</span></div></div>
          <h3>合并采购清单</h3>
          <ul class="plan-shopping"><li v-for="item in plan.snapshot.shopping_list" :key="`${item.code}@${item.version}`"><span>{{ item.title }}（{{ item.edible_part }}）</span><strong>{{ item.total_grams }} g</strong></li></ul>
          <p class="panel-note">{{ plan.snapshot.follow_up }}</p>
          <p class="panel-note">{{ plan.snapshot.disclaimer }}</p>
        </section>
      </template>
    </template>
  </div>
</template>
