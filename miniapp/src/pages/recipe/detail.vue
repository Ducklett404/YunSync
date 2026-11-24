<template>
  <view class="page">
    <view v-if="recipe" class="content">
      <view v-if="recipe.isDemo" class="demo-badge">DEMO · 未经正式专业签署</view>
      <text class="category">{{ recipe.category }}</text>
      <text class="title">{{ recipe.name }}</text>
      <text v-if="offlineCopy" class="item-note">当前显示本机副本 · {{ recipe.version }}</text>
      <text class="meta">{{ displayServings }} 人份 · 约 {{ recipe.minutes }} 分钟 · {{ recipe.tools.join('、') }}</text>
      <text v-if="displayServings !== recipe.servings" class="scale-note">单一单位的食材用量按原配方 {{ recipe.servings }} 人份换算。烹饪时间和锅具容量请按实际情况调整。</text>
      <text class="reason">{{ recipe.reason }}</text>
      <button class="favorite-button" tabindex="0" @click="toggleFavorite" @keydown.enter="toggleFavorite">{{ favorite ? '已收藏 · 取消收藏' : '收藏这道食谱' }}</button>
      <text v-if="storageMessage" class="item-note">{{ storageMessage }}</text>

      <view class="section">
        <text class="section-title">食材</text>
        <view v-for="item in recipe.ingredients" :key="`${item.name}-${item.amount}`" class="row">
          <view>
            <text class="item-name">{{ item.name }}</text>
            <text v-if="item.preparation" class="item-note">{{ item.preparation }}</text>
          </view>
          <text class="amount">{{ scaledAmount(item.amount, recipe.servings) }}</text>
        </view>
      </view>

      <view class="section">
        <view class="cooking-heading">
          <text class="section-title">做法</text>
          <button v-if="currentStep" class="cooking-button" tabindex="0" @click="cooking = undefined" @keydown.enter="cooking = undefined">查看全部步骤</button>
          <button v-else-if="recipe.steps.length" class="cooking-button" tabindex="0" @click="startCooking" @keydown.enter="startCooking">开始跟做</button>
        </view>
        <view v-if="cooking && currentStep" class="guided-step">
          <text class="cooking-progress" aria-live="polite">第 {{ cooking.index + 1 }} 步 / 共 {{ recipe.steps.length }} 步</text>
          <text class="cooking-action">{{ currentStep.action }}</text>
          <text v-if="currentStep.minutes" class="item-note">参考用时约 {{ currentStep.minutes }} 分钟</text>
          <text v-if="currentStep.doneWhen" class="item-note">完成提示：{{ currentStep.doneWhen }}</text>
          <view class="cooking-actions">
            <button class="cooking-button" :disabled="cooking.index === 0" tabindex="0" @click="moveCookingStep(-1)" @keydown.enter="moveCookingStep(-1)">上一步</button>
            <button class="cooking-button cooking-primary" tabindex="0" @click="moveCookingStep(1)" @keydown.enter="moveCookingStep(1)">{{ cooking.index + 1 === recipe.steps.length ? '完成跟做' : '下一步' }}</button>
          </view>
        </view>
        <view v-else v-for="step in recipe.steps" :key="step.order" class="step">
          <text class="step-number">{{ step.order }}</text>
          <view class="step-copy">
            <text>{{ step.action }}</text>
            <text v-if="step.minutes" class="item-note">参考用时约 {{ step.minutes }} 分钟</text>
            <text v-if="step.doneWhen" class="item-note">完成提示：{{ step.doneWhen }}</text>
          </view>
        </view>
      </view>

      <view v-if="recipe.substitutions.length" class="section">
        <text class="section-title">已登记替代</text>
        <view v-for="item in recipe.substitutions" :key="`${item.from}-${item.to}`" class="substitution">
          <text class="item-name">{{ item.from }} → {{ item.to }}</text>
          <text class="item-note">{{ item.note }}</text>
        </view>
      </view>

      <view class="safety-card">
        <text class="section-title">安全信息</text>
        <text class="safety-line">过敏原：{{ recipe.allergens.length ? recipe.allergens.join('、') : '未标出常见过敏原' }}</text>
        <text class="safety-line">不适用：{{ recipe.exclusions.length ? recipe.exclusions.join('；') : '暂无额外限制' }}</text>
        <text class="safety-line">日常饮食建议，不替代诊疗。</text>
      </view>

      <view class="trace-card">
        <text class="trace-title">来源与版本</text>
        <text class="trace-line">{{ recipe.sourceNote }}</text>
        <text class="trace-line">来源标识：{{ recipe.source }}</text>
        <text class="trace-line">版本：{{ recipe.version }} · 状态：{{ recipe.reviewStatus }}</text>
      </view>

      <view class="section">
        <text class="section-title">这道食谱怎么样？</text>
        <text class="item-note">反馈仅保存在本机，不会发送给运营人员，也不用于判断健康效果。</text>
        <view class="feedback-options">
          <button v-for="option in feedbackOptions" :key="option.kind" class="feedback-button" :class="{ selected: feedback?.kind === option.kind && feedback?.version === recipe.version }" tabindex="0" @click="submitFeedback(option.kind)" @keydown.enter="submitFeedback(option.kind)">{{ option.label }}</button>
        </view>
        <text v-if="feedback" class="item-note">已记录：{{ feedbackLabels[feedback.kind] }} · {{ feedback.version }}{{ feedback.version !== recipe.version ? '（旧版本反馈，可重新选择）' : '' }}</text>
      </view>
    </view>

    <view v-else-if="loading" class="empty-card">
      <text class="section-title">正在读取食谱</text>
    </view>
    <view v-else class="empty-card">
      <text class="section-title">这条食谱暂不可用</text>
      <text class="item-note">{{ unavailableReason }}。请返回“今日”或“食材”查看其他内容。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onShow, onUnload } from '@dcloudio/uni-app'
import { cloudApiEnabled, CloudHttpError, requestCloudRecipe } from '../../adapters/cloud'
import { getRecipeById } from '../../data/m2'
import { runtimeConfig } from '../../config/runtime'
import { contentUnavailableReason, isContentAvailable } from '../../services/content'
import { scaleRecipeAmount } from '../../services/recipe-amount'
import { feedbackLabels, isFavorite, loadRecipeFeedback, recordRecipeView, saveRecipeFeedback, setFavorite } from '../../services/engagement'
import type { FeedbackKind, RecipeFeedback } from '../../services/engagement'
import type { RecipeTemplate } from '../../types/domain'

const recipe = ref<RecipeTemplate>()
const recipeId = ref('')
const expectedVersion = ref('')
const offlineCopy = ref(false)
const loading = ref(false)
const favorite = ref(false)
const feedback = ref<RecipeFeedback>()
const unavailableReason = ref('内容已移除或链接无效')
const storageMessage = ref('')
const contentOptions = { allowDemoContent: runtimeConfig.dataMode === 'demo' }
const recordOptions = computed(() => ({ ...contentOptions, fromCloud: cloudApiEnabled() && !offlineCopy.value }))
const feedbackOptions = (Object.keys(feedbackLabels) as FeedbackKind[]).map((kind) => ({ kind, label: feedbackLabels[kind] }))
const targetServings = ref<number>()
const cooking = ref<{ version: string; index: number }>()
const displayServings = computed(() => targetServings.value || recipe.value?.servings || 1)
const currentStep = computed(() => {
  const state = cooking.value
  if (state && recipe.value?.version === state.version) return recipe.value.steps[state.index]
})
const versionChangedMessage = '食谱版本已更新，请从推荐列表重新选择'
let detailRequestId = 0
let recordedVersion: string | undefined

function scaledAmount(amount: string, baseServings: number): string {
  if (!targetServings.value || targetServings.value === baseServings) return amount
  return scaleRecipeAmount(amount, baseServings, targetServings.value) ?? amount
}

function startCooking() {
  if (recipe.value?.steps.length) cooking.value = { version: recipe.value.version, index: 0 }
}

function moveCookingStep(offset: number) {
  if (!cooking.value || !recipe.value) return
  const index = cooking.value.index + offset
  if (index < 0) return
  if (index < recipe.value.steps.length) {
    cooking.value.index = index
    return
  }
  cooking.value = undefined
  uni.showToast({ title: '已完成跟做', icon: 'none' })
}

async function refreshRecipe() {
  const requestId = ++detailRequestId
  const id = recipeId.value
  const version = expectedVersion.value
  const local = getRecipeById(id)
  const useCloud = Boolean(id && cloudApiEnabled())
  let current = local
  let usingOfflineCopy = false
  let reason: string | undefined
  favorite.value = isFavorite(id)
  feedback.value = loadRecipeFeedback(id)
  loading.value = useCloud
  if (useCloud) {
    recipe.value = undefined
    try {
      current = await requestCloudRecipe(id, version)
    } catch (error) {
      if (error instanceof CloudHttpError && error.status < 500) {
        current = undefined
        if (error.status === 409) reason = versionChangedMessage
      } else {
        usingOfflineCopy = Boolean(local)
        reason = local ? undefined : '在线食谱暂时无法读取，本机没有此食谱的副本'
      }
    }
  }
  if (requestId !== detailRequestId) return
  if (current && version && current.version !== version) {
    current = undefined
    reason = usingOfflineCopy ? '本机副本与推荐版本不一致，请联网后重新选择' : versionChangedMessage
  }
  recipe.value = current && isContentAvailable(current, contentOptions) ? current : undefined
  offlineCopy.value = usingOfflineCopy
  unavailableReason.value = reason || contentUnavailableReason(current)
  loading.value = false
  if (recipe.value && recipe.value.version !== recordedVersion) {
    try {
      recordRecipeView(recipe.value, recordOptions.value)
      recordedVersion = recipe.value.version
    } catch {
      storageMessage.value = '浏览记录未保存，仍可查看食谱。'
    }
  }
}

function toggleFavorite() {
  if (!recipe.value) return
  try {
    setFavorite(recipe.value, !favorite.value, recordOptions.value)
    favorite.value = isFavorite(recipe.value.id)
    storageMessage.value = ''
    uni.showToast({ title: favorite.value ? '已收藏到本机' : '已取消收藏', icon: 'success' })
  } catch (error) {
    storageMessage.value = error instanceof Error && error.message.includes('收藏已满') ? error.message : '保存失败，请检查本机存储后重试。'
  }
}

function submitFeedback(kind: FeedbackKind) {
  if (!recipe.value) return
  try {
    saveRecipeFeedback(recipe.value, kind, recordOptions.value)
    feedback.value = loadRecipeFeedback(recipe.value.id)
    storageMessage.value = ''
    uni.showToast({ title: '反馈已记录在本机', icon: 'success' })
  } catch {
    storageMessage.value = '反馈保存失败，请稍后重试。'
  }
}

onLoad((options) => {
  try {
    recipeId.value = typeof options?.id === 'string' ? decodeURIComponent(options.id) : ''
    expectedVersion.value = typeof options?.version === 'string' ? decodeURIComponent(options.version) : ''
  } catch {
    recipeId.value = ''
  }
  const servings = Number(options?.servings)
  if ([1, 2, 4].includes(servings)) targetServings.value = servings
})
onShow(refreshRecipe)
onUnload(() => { detailRequestId += 1 })
</script>

<style scoped>
.cooking-heading, .cooking-actions { display: flex; align-items: center; justify-content: space-between; gap: 12rpx; }
.cooking-heading .section-title { margin-bottom: 0; }
.cooking-button { margin: 0; padding: 0 16rpx; color: #123d35; background: #edf4ee; border-radius: 14rpx; font-size: 22rpx; }
.cooking-primary { color: #fff; background: #123d35; }
.guided-step { margin-top: 18rpx; padding: 22rpx; background: #f1f6f2; border-radius: 18rpx; }
.cooking-progress, .cooking-action { display: block; }
.cooking-progress { color: #52625b; font-size: 22rpx; }
.cooking-action { margin-top: 9rpx; color: #142b26; font-size: 29rpx; line-height: 1.6; }
.cooking-actions { margin-top: 18rpx; }
.page { min-height: 100vh; padding: 30rpx 28rpx 60rpx; box-sizing: border-box; }
.demo-badge { display: inline-block; padding: 8rpx 14rpx; color: #7b561d; background: #f5e8c8; border-radius: 999rpx; font-size: 22rpx; font-weight: 700; }
.category { display: block; margin-top: 30rpx; color: #8f5f18; font-size: 24rpx; font-weight: 700; }
.title { display: block; margin-top: 8rpx; font-family: serif; font-size: 52rpx; font-weight: 800; }
.meta, .reason, .scale-note { display: block; margin-top: 14rpx; color: #66766f; font-size: 24rpx; line-height: 1.7; }
.scale-note { padding: 16rpx 18rpx; color: #76551c; background: #fff3d8; border-radius: 16rpx; font-size: 21rpx; }
.section, .safety-card, .trace-card, .empty-card { margin-top: 28rpx; padding: 28rpx; background: #fffef9; border-radius: 28rpx; }
.section-title { display: block; margin-bottom: 18rpx; font-family: serif; font-size: 34rpx; font-weight: 800; }
.row { display: flex; justify-content: space-between; gap: 20rpx; padding: 18rpx 0; border-bottom: 1rpx solid #e3e7e3; }
.row:last-child { border-bottom: 0; }
.item-name, .item-note, .amount, .trace-title, .trace-line, .safety-line { display: block; }
.item-name { color: #142b26; font-size: 27rpx; font-weight: 700; }
.item-note, .trace-line { margin-top: 7rpx; color: #66766f; font-size: 22rpx; line-height: 1.6; }
.amount { flex: none; color: #42534c; font-size: 25rpx; }
.step { display: flex; gap: 18rpx; margin-top: 18rpx; }
.step-number { display: flex; flex: none; align-items: center; justify-content: center; width: 46rpx; height: 46rpx; color: #fff; background: #123d35; border-radius: 50%; font-size: 22rpx; font-weight: 800; }
.step-copy { flex: 1; padding-top: 5rpx; color: #2d3f38; font-size: 26rpx; line-height: 1.65; }
.substitution { padding: 16rpx 0; }
.safety-card { color: #5c4018; background: #fff1d5; }
.safety-line { margin-top: 10rpx; font-size: 23rpx; line-height: 1.65; }
.trace-card { background: #edf1ee; }
.trace-title { color: #31473f; font-size: 25rpx; font-weight: 800; }
.favorite-button { margin-top: 24rpx; color: #123d35; background: #e5eee7; border-radius: 20rpx; font-size: 26rpx; }
.feedback-options { display: flex; flex-wrap: wrap; gap: 14rpx; margin-top: 20rpx; }
.feedback-button { margin: 0; padding: 0 20rpx; color: #42534c; background: #f1f4f1; border-radius: 18rpx; font-size: 23rpx; }
.feedback-button.selected { color: #fff; background: #123d35; }
</style>
