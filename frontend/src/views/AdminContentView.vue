<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  CheckCircle2,
  GitCompareArrows,
  LibraryBig,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  changeContentItemStatus,
  compareContentVersions,
  fetchContentItems,
  fetchEvidenceSources,
  getApiErrorMessage,
  reviewContentItem,
  validateContentItems,
} from '@/services/api'
import type {
  BulkContentValidation,
  ContentComparison,
  ContentItem,
  ContentStatus,
  ContentType,
  EvidenceSource,
} from '@/types'

const items = ref<ContentItem[]>([])
const sources = ref<EvidenceSource[]>([])
const loading = ref(false)
const busyItem = ref('')
const error = ref('')
const success = ref('')
const query = ref('')
const typeFilter = ref<ContentType | ''>('')
const statusFilter = ref<ContentStatus | ''>('')
const selectedIds = ref<string[]>([])
const validation = ref<BulkContentValidation | null>(null)
const comparison = ref<ContentComparison | null>(null)
const reviewForm = reactive({
  qualification: '',
  scope: '条目结构、来源依据、适用范围与安全边界',
  evidenceRef: '',
  notes: '',
})

const selectedItems = computed(() =>
  selectedIds.value
    .map((id) => items.value.find((item) => item.id === id))
    .filter((item): item is ContentItem => Boolean(item)),
)
const canCompare = computed(() => {
  if (selectedItems.value.length !== 2) return false
  const [first, second] = selectedItems.value
  return first.content_type === second.content_type && first.code === second.code && first.version !== second.version
})
const counts = computed(() => ({
  ingredient: items.value.filter((item) => item.content_type === 'ingredient').length,
  recipe: items.value.filter((item) => item.content_type === 'recipe').length,
  contraindication: items.value.filter((item) => item.content_type === 'contraindication').length,
}))

function filters() {
  const value: { content_type?: ContentType; status?: ContentStatus; q?: string } = {}
  if (typeFilter.value) value.content_type = typeFilter.value
  if (statusFilter.value) value.status = statusFilter.value
  if (query.value.trim()) value.q = query.value.trim()
  return value
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [loadedItems, loadedSources] = await Promise.all([
      fetchContentItems(filters()),
      fetchEvidenceSources(),
    ])
    items.value = loadedItems
    sources.value = loadedSources
    selectedIds.value = selectedIds.value.filter((id) => loadedItems.some((item) => item.id === id))
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

function toggleItem(id: string) {
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter((value) => value !== id)
    : [...selectedIds.value, id]
  validation.value = null
  comparison.value = null
}

function typeLabel(value: ContentType): string {
  return { ingredient: '食材', recipe: '食谱', contraindication: '禁忌规则' }[value]
}

function statusLabel(value: ContentStatus): string {
  return { draft: '草稿', reviewed: '已审核', published: '已发布', retired: '已停用' }[value]
}

function statusClass(value: ContentStatus): string {
  if (value === 'published') return 'safe'
  if (value === 'retired') return 'danger'
  return 'pending'
}

function itemSummary(item: ContentItem): string {
  if (item.content_type === 'ingredient') {
    return `${String(item.payload.latin_species || '未填物种')} · ${String(item.payload.edible_part || '未填部位')}`
  }
  if (item.content_type === 'recipe') {
    const materials = Array.isArray(item.payload.materials) ? item.payload.materials : []
    const steps = Array.isArray(item.payload.steps) ? item.payload.steps : []
    return `${materials.length} 种材料 · ${steps.length} 个步骤 · ${String(item.payload.servings || '-')} 人份`
  }
  return `${String(item.payload.trigger_type || '未填触发类型')} · ${String(item.payload.action || '未填动作')}`
}

async function submitReview(item: ContentItem, decision: 'approved' | 'rejected') {
  if (!reviewForm.qualification.trim() || !reviewForm.evidenceRef.trim() || !reviewForm.scope.trim()) {
    error.value = '请先填写审核资质、审核范围和证据记录号。'
    return
  }
  busyItem.value = item.id
  error.value = ''
  success.value = ''
  try {
    await reviewContentItem(item.id, {
      decision,
      reviewer_qualification: reviewForm.qualification.trim(),
      review_scope: reviewForm.scope.trim(),
      evidence_ref: reviewForm.evidenceRef.trim(),
      attested: true,
      notes: reviewForm.notes.trim(),
    })
    success.value = decision === 'approved' ? `已批准审核：${item.title}` : `已退回草稿：${item.title}`
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    busyItem.value = ''
  }
}

async function govern(item: ContentItem, action: 'publish' | 'retire' | 'rollback') {
  busyItem.value = item.id
  error.value = ''
  success.value = ''
  try {
    await changeContentItemStatus(item.id, action)
    const labels = { publish: '发布', retire: '停用', rollback: '回滚' }
    success.value = `${labels[action]}完成：${item.title} ${item.version}`
    await load()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    busyItem.value = ''
  }
}

async function bulkValidate() {
  if (!selectedIds.value.length) return
  error.value = ''
  success.value = ''
  try {
    validation.value = await validateContentItems(selectedIds.value)
    success.value = validation.value.valid ? '所选条目通过发布依赖校验。' : '校验完成，请处理阻断项。'
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function compareSelected() {
  if (!canCompare.value) return
  const [first, second] = selectedItems.value
  error.value = ''
  try {
    comparison.value = await compareContentVersions(
      first.content_type,
      first.code,
      first.version,
      second.version,
    )
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="M4 · 专业内容治理"
      title="食养内容知识库"
      description="检索和核验食材、家庭食谱与禁忌规则。只有来源有效、依赖完整且具名审核通过的版本才能发布给参与者。"
    >
      <button class="icon-button" title="刷新知识库" :disabled="loading" @click="load">
        <RefreshCw :size="18" :class="{ spinning: loading }" />
      </button>
    </PageHeader>

    <div class="summary-grid content-summary-grid">
      <div class="summary-card"><div class="summary-icon teal"><LibraryBig :size="20" /></div><div><span>食材条目</span><strong>{{ counts.ingredient }}</strong><small>含普通食物与食药物质候审项</small></div></div>
      <div class="summary-card"><div class="summary-icon green"><CheckCircle2 :size="20" /></div><div><span>家庭食谱</span><strong>{{ counts.recipe }}</strong><small>含克重、步骤、替换与频次字段</small></div></div>
      <div class="summary-card"><div class="summary-icon amber"><ShieldCheck :size="20" /></div><div><span>禁忌规则</span><strong>{{ counts.contraindication }}</strong><small>{{ sources.length }} 个可追溯证据来源</small></div></div>
    </div>

    <div v-if="error" class="message error-message" role="alert">{{ error }}</div>
    <div v-if="success" class="message success-message" role="status">{{ success }}</div>

    <section class="panel content-admin-controls">
      <div class="content-filter-row">
        <label class="content-search-field">
          <Search :size="17" />
          <input v-model="query" type="search" placeholder="搜索标题或代码" @keyup.enter="load" />
        </label>
        <select v-model="typeFilter" aria-label="内容类型" @change="load">
          <option value="">全部类型</option>
          <option value="ingredient">食材</option>
          <option value="recipe">食谱</option>
          <option value="contraindication">禁忌规则</option>
        </select>
        <select v-model="statusFilter" aria-label="内容状态" @change="load">
          <option value="">全部状态</option>
          <option value="draft">草稿</option>
          <option value="reviewed">已审核</option>
          <option value="published">已发布</option>
          <option value="retired">已停用</option>
        </select>
        <button class="button secondary" :disabled="loading" @click="load">检索</button>
      </div>
      <div class="content-selection-actions">
        <span>已选择 {{ selectedIds.length }} 项</span>
        <button class="button secondary compact-button" :disabled="!selectedIds.length" @click="bulkValidate">批量校验</button>
        <button class="button secondary compact-button" :disabled="!canCompare" @click="compareSelected">
          <GitCompareArrows :size="15" /> 比较两版
        </button>
      </div>
    </section>

    <section class="panel content-review-form">
      <div class="panel-heading">
        <div><span class="section-kicker">具名审核记录</span><h2>本次审核声明</h2></div>
        <span class="status-badge pending">发布前必填</span>
      </div>
      <div class="content-review-fields">
        <label><span>审核资质</span><input v-model="reviewForm.qualification" placeholder="例如：注册营养师（演示时请明确标注测试身份）" /></label>
        <label><span>证据记录号</span><input v-model="reviewForm.evidenceRef" placeholder="例如：review/2026-09-21/001" /></label>
        <label class="wide-field"><span>审核范围</span><input v-model="reviewForm.scope" /></label>
        <label class="wide-field"><span>备注</span><textarea v-model="reviewForm.notes" rows="2" placeholder="记录限制、修订意见或复核日期"></textarea></label>
      </div>
      <p class="panel-note">点击批准或退回即表示当前登录审核员确认上述身份与范围。演示审核不能替代 M4 的正式专业签字。</p>
    </section>

    <section v-if="validation" class="panel">
      <div class="panel-heading"><div><span class="section-kicker">批量校验</span><h2>{{ validation.valid ? '通过发布依赖校验' : '存在阻断项' }}</h2></div></div>
      <div class="validation-list">
        <article v-for="result in validation.results" :key="result.item_id" :class="['validation-item', { invalid: !result.valid }]">
          <strong>{{ result.code || result.item_id }} <small v-if="result.version">{{ result.version }}</small></strong>
          <span v-if="result.valid">结构与依赖有效</span>
          <span v-for="message in result.errors" v-else :key="message">{{ message }}</span>
          <em v-for="warning in result.warnings" :key="warning">{{ warning }}</em>
        </article>
      </div>
    </section>

    <section v-if="comparison" class="panel">
      <div class="panel-heading"><div><span class="section-kicker">版本比较</span><h2>{{ comparison.code }} · {{ comparison.from_version }} → {{ comparison.to_version }}</h2></div></div>
      <div v-if="Object.keys(comparison.changed_fields).length" class="action-table-wrap">
        <table class="data-table comparison-table"><thead><tr><th>字段</th><th>原值</th><th>新值</th></tr></thead><tbody>
          <tr v-for="(change, field) in comparison.changed_fields" :key="field"><td><code>{{ field }}</code></td><td>{{ change.from ?? '—' }}</td><td>{{ change.to ?? '—' }}</td></tr>
        </tbody></table>
      </div>
      <div v-else class="empty-state">两个版本没有字段差异。</div>
    </section>

    <div v-if="loading && !items.length" class="loading-block">正在读取内容知识库…</div>
    <div v-else-if="!items.length" class="empty-state">没有符合筛选条件的条目。</div>
    <section v-else class="content-item-list">
      <article v-for="item in items" :key="item.id" :class="['panel', 'content-item-card', { selected: selectedIds.includes(item.id) }]">
        <label class="content-select-box" :aria-label="`选择 ${item.title}`">
          <input type="checkbox" :checked="selectedIds.includes(item.id)" @change="toggleItem(item.id)" />
        </label>
        <div class="content-item-main">
          <div class="content-item-title">
            <div><span class="section-kicker">{{ typeLabel(item.content_type) }} · {{ item.code }}</span><h2>{{ item.title }}</h2></div>
            <div class="content-item-badges"><span :class="['status-badge', statusClass(item.status)]">{{ statusLabel(item.status) }}</span><span v-if="item.is_active" class="status-badge safe">当前生效</span></div>
          </div>
          <p>{{ itemSummary(item) }}</p>
          <div class="content-item-meta"><span>版本 {{ item.version }}</span><span>创建者 {{ item.created_by }}</span><span>{{ new Date(item.created_at).toLocaleString('zh-CN') }}</span></div>
          <details><summary>查看结构化内容</summary><pre>{{ JSON.stringify(item.payload, null, 2) }}</pre></details>
        </div>
        <div class="content-item-actions">
          <button v-if="item.status === 'draft' || item.status === 'reviewed'" class="button secondary compact-button" :disabled="busyItem === item.id" @click="submitReview(item, 'approved')">批准审核</button>
          <button v-if="item.status === 'draft' || item.status === 'reviewed'" class="button secondary compact-button" :disabled="busyItem === item.id" @click="submitReview(item, 'rejected')">退回草稿</button>
          <button v-if="item.status === 'reviewed'" class="button primary compact-button" :disabled="busyItem === item.id" @click="govern(item, 'publish')">发布</button>
          <button v-if="item.status === 'published'" class="button secondary compact-button" :disabled="busyItem === item.id" @click="govern(item, 'retire')">停用</button>
          <button v-if="item.status === 'retired'" class="button secondary compact-button" :disabled="busyItem === item.id" @click="govern(item, 'rollback')">回滚到此版</button>
        </div>
      </article>
    </section>

    <section class="panel evidence-source-panel">
      <div class="panel-heading"><div><span class="section-kicker">证据来源</span><h2>来源版本与核验状态</h2></div></div>
      <div class="evidence-source-list">
        <article v-for="source in sources" :key="source.id">
          <div><strong>{{ source.title }}</strong><span>{{ source.ref }} · {{ source.publisher }}</span></div>
          <a v-if="source.url_or_archive_ref.startsWith('http')" class="text-link" :href="source.url_or_archive_ref" target="_blank" rel="noreferrer">查看原始来源</a>
          <span :class="['status-badge', source.status === 'active' ? 'safe' : 'pending']">{{ source.status }}</span>
        </article>
      </div>
    </section>
  </div>
</template>
