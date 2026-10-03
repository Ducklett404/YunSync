<template>
  <view class="page">
    <view v-if="recipe" class="content">
      <view class="demo-badge">DEMO · 未经正式专业签署</view>
      <text class="category">{{ recipe.category }}</text>
      <text class="title">{{ recipe.name }}</text>
      <text class="meta">{{ displayServings }} 人份 · 约 {{ recipe.minutes }} 分钟 · {{ recipe.tools.join('、') }}</text>
      <text v-if="displayServings !== recipe.servings" class="scale-note">食材用量已按原配方 {{ recipe.servings }} 人份等比例换算；烹饪时间和锅具容量仍需按实际情况调整。</text>
      <text class="reason">{{ recipe.reason }}</text>

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
        <text class="section-title">做法</text>
        <view v-for="step in recipe.steps" :key="step.order" class="step">
          <text class="step-number">{{ step.order }}</text>
          <text class="step-copy">{{ step.action }}</text>
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
    </view>

    <view v-else class="empty-card">
      <text class="section-title">没有找到这条食谱</text>
      <text class="item-note">它可能已停用，或链接参数不完整。</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getRecipeById } from '../../data/m2'
import type { RecipeTemplate } from '../../types/domain'

const recipe = ref<RecipeTemplate>()
const targetServings = ref<number>()
const displayServings = computed(() => targetServings.value || recipe.value?.servings || 1)

function scaledAmount(amount: string, baseServings: number): string {
  if (!targetServings.value || targetServings.value === baseServings) return amount
  const match = amount.match(/^([0-9]+(?:\.[0-9]+)?)(.*)$/)
  if (!match) return amount
  const scaled = Math.round((Number(match[1]) * targetServings.value / baseServings) * 10) / 10
  return `${scaled}${match[2]}`
}

onLoad((options) => {
  const id = typeof options?.id === 'string' ? decodeURIComponent(options.id) : ''
  recipe.value = getRecipeById(id)
  const servings = Number(options?.servings)
  if ([1, 2, 4].includes(servings)) targetServings.value = servings
})
</script>

<style scoped>
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
</style>
