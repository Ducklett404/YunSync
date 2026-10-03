<template>
  <view class="page">
    <view class="demo-badge">M4 · DEMO 审核结构</view>
    <text class="title">手头食材做什么</text>
    <text class="copy">录入 1—15 种现有食材。系统先排除个人安全冲突，再从现有食谱模板中寻找完全匹配或最多缺 2 种非关键材料的结果。</text>

    <view class="panel">
      <text class="section-title">1. 现有食材</text>
      <view class="search-row">
        <input v-model="searchText" class="search-input" placeholder="输入食材，用逗号分隔" confirm-type="done" @confirm="addSearchIngredients" />
        <view class="add-action" @tap="addSearchIngredients">添加</view>
      </view>
      <text class="counter">已选 {{ session.ingredients.length }}/15</text>
      <view v-if="session.ingredients.length" class="selected-list">
        <view v-for="item in session.ingredients" :key="item" class="selected-chip" :data-value="item" @tap="onRemoveIngredientTap">{{ item }} ×</view>
      </view>

      <view v-for="group in ingredientGroups" :key="group.category" class="tag-group">
        <text class="group-name">{{ group.category }}</text>
        <view class="tag-list">
          <view v-for="item in group.items" :key="item" class="tag" :class="{ active: hasIngredient(item) }" :data-value="item" @tap="onIngredientTap">{{ item }}</view>
        </view>
      </view>
    </view>

    <view class="panel">
      <text class="section-title">2. 制作条件</text>
      <text class="label">可接受时间</text>
      <view class="choice-row time-options">
        <view v-for="item in timeOptions" :key="item.value" class="choice" :class="{ active: session.maxMinutes === item.value }" :data-value="item.value" @tap="onTimeTap">{{ item.label }}</view>
      </view>

      <text class="label">已有厨具（可多选）</text>
      <view class="tag-list">
        <view v-for="item in commonTools" :key="item.value" class="tag" :class="{ active: session.tools.includes(item.value) }" :data-value="item.value" @tap="onToolTap">{{ item.label }}</view>
      </view>

      <text class="label">份数</text>
      <view class="choice-row">
        <view v-for="item in servingOptions" :key="item.value" class="choice" :class="{ active: session.targetServings === item.value }" :data-value="item.value" @tap="onServingTap">{{ item.label }}</view>
      </view>

      <text class="label">是否接受再购买非关键材料</text>
      <view class="choice-row">
        <view v-for="item in additionalOptions" :key="item.value" class="choice" :class="{ active: session.maxAdditionalIngredients === item.value }" :data-value="item.value" @tap="onAdditionalTap">{{ item.label }}</view>
      </view>

      <button class="primary-button" @tap="runMatch">开始匹配</button>
    </view>

    <view v-if="result" class="results">
      <view v-if="result.safety.blocked" class="message-card safety-block">
        <text class="message-kicker">安全门禁已拦截</text>
        <text class="message-title">{{ result.safety.title }}</text>
        <text class="message-copy">{{ result.safety.message }}</text>
        <view class="text-link" @tap="openProfile">查看或修改个人档案</view>
      </view>

      <template v-else>
        <view class="message-card" :class="{ empty: !result.matches.length }">
          <text class="message-title">{{ result.matches.length ? `找到 ${result.matches.length} 个结果` : '没有可安全展示的结果' }}</text>
          <text class="message-copy">{{ result.message }}</text>
          <text v-if="result.safetyFilteredCount" class="filter-note">已硬过滤 {{ result.safetyFilteredCount }} 条安全冲突食谱。</text>
        </view>

        <view v-for="item in result.matches" :key="item.recipe.id" class="result-card" @tap="openRecipe(item.recipe.id, item.targetServings)">
          <view class="result-top">
            <text class="match-badge" :class="item.kind">{{ kindLabel(item.kind) }}</text>
            <text class="result-meta">{{ item.targetServings }} 人份 · {{ item.recipe.minutes }} 分钟</text>
          </view>
          <text class="result-name">{{ item.recipe.name }}</text>
          <text class="result-line">已有：{{ item.matchedIngredients.join('、') }}</text>
          <text v-if="item.missingIngredients.length" class="result-line missing">需再买：{{ item.missingIngredients.join('、') }}</text>
          <text v-if="item.substitutionsUsed.length" class="result-line substitution">登记替代：{{ item.substitutionsUsed.map((value) => `${value.from}→${value.to}`).join('；') }}</text>
          <text class="detail-link">查看按份数换算后的食材和做法 →</text>
        </view>
      </template>
    </view>

    <view class="safety-note">只匹配现有结构化食谱；替代关系必须已登记在模板中。当前内容均为 DEMO，未经正式专业签署，不会临时生成新配方。</view>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { runtimeConfig } from '../../config/runtime'
import { loadProfile } from '../../services/profile'
import { matchPantryRecipes, normalizePantryIngredients, pantryIngredientsEquivalent } from '../../services/pantry'
import type { PantryCategory, PantryMatchKind, PantryMatchResult, PantrySession, WellnessProfile } from '../../types/domain'

const ingredientGroups: Array<{ category: PantryCategory; items: string[] }> = [
  { category: '主食', items: ['大米', '小米', '糯米', '小麦粉', '粽叶', '莲子'] },
  { category: '蔬菜水果', items: ['番茄', '山药', '南瓜', '绿叶菜', '白菜', '菠菜', '胡萝卜', '春笋', '香菇', '莲藕', '雪梨', '白萝卜', '红枣'] },
  { category: '肉蛋奶', items: ['鸡蛋', '牛肉', '牛奶'] },
  { category: '豆制品', items: ['豆腐', '红豆', '豌豆', '红豆沙'] },
  { category: '调味品', items: ['食用油', '米醋', '大蒜'] },
]
const commonTools = ['汤锅', '大汤锅', '炖锅', '菜刀', '炒锅', '锅铲', '电饭锅', '烤箱', '烤盘', '面盆', '擀面杖', '量杯', '棉绳', '月饼模具', '洁净玻璃容器']
  .map((value) => ({ value, label: value }))
const timeOptions = [15, 20, 30, 45, 60, 90, 180]
  .map((value) => ({ value, label: `${value} 分钟内` }))
const servingOptions: Array<{ value: 1 | 2 | 4; label: string }> = [
  { value: 1, label: '一人食' },
  { value: 2, label: '2人家庭' },
  { value: 4, label: '4人家庭' },
]
const additionalOptions: Array<{ value: 0 | 1 | 2; label: string }> = [
  { value: 0, label: '不购买' },
  { value: 1, label: '最多 1 种' },
  { value: 2, label: '最多 2 种' },
]

let profile: WellnessProfile = loadProfile()
const searchText = ref('')
const result = ref<PantryMatchResult>()
const session = reactive<PantrySession>({
  ingredients: [], maxMinutes: 45, tools: ['汤锅', '菜刀', '炒锅', '锅铲', '电饭锅'], targetServings: 2, maxAdditionalIngredients: 1,
})

type DatasetTapEvent = { currentTarget: { dataset: { value?: string | number } } }
function eventValue(event: DatasetTapEvent): string | number { return event.currentTarget.dataset.value ?? '' }

function hasIngredient(item: string): boolean { return normalizePantryIngredients([...session.ingredients, item]).length === session.ingredients.length }
function addIngredient(item: string) {
  const next = normalizePantryIngredients([...session.ingredients, item])
  if (next.length === session.ingredients.length) return
  if (session.ingredients.length >= 15) { uni.showToast({ title: '最多录入 15 种', icon: 'none' }); return }
  session.ingredients = next
}
function removeIngredient(item: string) { session.ingredients = session.ingredients.filter((value) => !pantryIngredientsEquivalent(value, item)) }
function toggleIngredient(item: string) { hasIngredient(item) ? removeIngredient(item) : addIngredient(item) }
function onIngredientTap(event: DatasetTapEvent) { toggleIngredient(String(eventValue(event))) }
function onRemoveIngredientTap(event: DatasetTapEvent) { removeIngredient(String(eventValue(event))) }
function addSearchIngredients() {
  const values = searchText.value.split(/[、，,;；\s]+/).filter(Boolean)
  for (const value of values) addIngredient(value)
  searchText.value = ''
}
function toggleTool(item: string) {
  const index = session.tools.indexOf(item)
  index >= 0 ? session.tools.splice(index, 1) : session.tools.push(item)
}
function onToolTap(event: DatasetTapEvent) { toggleTool(String(eventValue(event))) }
function onTimeTap(event: DatasetTapEvent) { session.maxMinutes = Number(eventValue(event)) }
function onServingTap(event: DatasetTapEvent) { session.targetServings = Number(eventValue(event)) as PantrySession['targetServings'] }
function onAdditionalTap(event: DatasetTapEvent) { session.maxAdditionalIngredients = Number(eventValue(event)) as PantrySession['maxAdditionalIngredients'] }
function kindLabel(kind: PantryMatchKind): string { return ({ complete: '材料齐全', substitution: '使用登记替代', missing: '缺少少量材料' })[kind] }
function runMatch() {
  if (!session.ingredients.length) { uni.showToast({ title: '请先录入至少 1 种食材', icon: 'none' }); return }
  if (!session.tools.length) { uni.showToast({ title: '请至少选择 1 件厨具', icon: 'none' }); return }
  result.value = matchPantryRecipes({ ...session, ingredients: [...session.ingredients], tools: [...session.tools] }, profile, { allowDemoContent: runtimeConfig.dataMode === 'demo' })
}
function openRecipe(recipeId: string, servings: number) { uni.navigateTo({ url: `/pages/recipe/detail?id=${encodeURIComponent(recipeId)}&servings=${servings}` }) }
function openProfile() { uni.switchTab({ url: '/pages/profile/index' }) }
onShow(() => { profile = loadProfile() })
</script>

<style scoped>
.page { min-height: 100vh; padding: 36rpx 28rpx 60rpx; box-sizing: border-box; }
.demo-badge { display: inline-block; padding: 8rpx 14rpx; color: #7b561d; background: #f5e8c8; border-radius: 999rpx; font-size: 22rpx; font-weight: 700; }
.title, .copy, .section-title, .label, .counter, .group-name, .message-kicker, .message-title, .message-copy, .filter-note, .result-name, .result-line, .detail-link { display: block; }
.title { margin-top: 28rpx; font-family: serif; font-size: 50rpx; font-weight: 800; }.copy { margin-top: 14rpx; color: #66766f; font-size: 25rpx; line-height: 1.7; }
.panel { margin-top: 28rpx; padding: 28rpx; background: #fffef9; border-radius: 28rpx; }.section-title { color: #142b26; font-size: 32rpx; font-weight: 800; }
.search-row { display: flex; gap: 14rpx; margin-top: 20rpx; }.search-input { flex: 1; height: 78rpx; padding: 0 22rpx; background: #f1f4f1; border-radius: 18rpx; font-size: 25rpx; }.add-action { display: flex; align-items: center; padding: 0 24rpx; color: #fff; background: #526f65; border-radius: 18rpx; font-size: 24rpx; font-weight: 700; }
.counter { margin-top: 10rpx; color: #7d8b84; font-size: 21rpx; }.selected-list, .tag-list, .choice-row { display: flex; flex-wrap: wrap; gap: 12rpx; }.selected-list { margin-top: 16rpx; }.selected-chip { padding: 10rpx 16rpx; color: #fff; background: #123d35; border-radius: 999rpx; font-size: 22rpx; }
.tag-group { margin-top: 24rpx; }.group-name { margin-bottom: 10rpx; color: #5e6d66; font-size: 23rpx; font-weight: 700; }.tag { padding: 10rpx 17rpx; color: #42534c; background: #edf1ee; border: 1rpx solid transparent; border-radius: 999rpx; font-size: 22rpx; }.tag.active { color: #fff; background: #123d35; }
.label { margin: 28rpx 0 12rpx; color: #52625b; font-size: 24rpx; }.field { padding: 21rpx 22rpx; background: #f1f4f1; border-radius: 18rpx; font-size: 26rpx; }.choice { flex: 1; min-width: 150rpx; padding: 18rpx 10rpx; text-align: center; color: #42534c; background: #edf1ee; border-radius: 18rpx; font-size: 23rpx; }.choice.active { color: #fff; background: #123d35; }
.primary-button { margin-top: 34rpx; color: #fff; background: #123d35; border-radius: 22rpx; font-size: 28rpx; font-weight: 800; }.results { margin-top: 30rpx; }.message-card, .result-card { margin-top: 18rpx; padding: 26rpx; background: #fffef9; border-radius: 26rpx; }.message-card.empty { background: #fff4df; }.safety-block { border: 2rpx solid #d9a07c; background: #fff5ed; }.message-kicker { color: #a44a2f; font-size: 21rpx; font-weight: 800; }.message-title { margin-top: 6rpx; font-size: 30rpx; font-weight: 800; }.message-copy { margin-top: 10rpx; color: #66766f; font-size: 23rpx; line-height: 1.65; }.filter-note { margin-top: 10rpx; color: #9a4d2f; font-size: 21rpx; }.text-link { margin-top: 18rpx; color: #123d35; font-size: 24rpx; font-weight: 800; }
.result-card { border: 1rpx solid #dce2dc; }.result-top { display: flex; justify-content: space-between; align-items: center; }.match-badge { padding: 7rpx 13rpx; border-radius: 10rpx; color: #275649; background: #dfeee8; font-size: 20rpx; font-weight: 800; }.match-badge.substitution { color: #76551c; background: #f5e8c8; }.match-badge.missing { color: #8d4c32; background: #f8e2d8; }.result-meta { color: #718078; font-size: 21rpx; }.result-name { margin-top: 16rpx; font-family: serif; font-size: 36rpx; font-weight: 800; }.result-line { margin-top: 11rpx; color: #596a62; font-size: 22rpx; line-height: 1.55; }.result-line.missing { color: #924b30; }.result-line.substitution { color: #7a591d; }.detail-link { margin-top: 18rpx; color: #123d35; font-size: 23rpx; font-weight: 800; }
.safety-note { margin-top: 26rpx; padding: 22rpx; color: #5d6d66; background: #edf1ee; border-radius: 20rpx; font-size: 22rpx; line-height: 1.65; }
</style>
