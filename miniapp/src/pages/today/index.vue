<template>
  <view class="page">
    <view v-if="runtimeConfig.showDemoBadge" class="demo-badge">DEMO · 演示数据</view>

    <view v-if="runtimeConfig.showDemoBadge" class="acceptance-panel">
      <text class="acceptance-title">M1 验收场景</text>
      <scroll-view scroll-x class="acceptance-scroll">
        <view class="scenario-row">
          <button v-for="item in acceptanceScenarios" :key="item" class="scenario-button" :class="{ active: scenario === item }" size="mini" @tap="selectScenario(item)">{{ acceptanceScenarioLabels[item] }}</button>
        </view>
      </scroll-view>
      <text class="acceptance-title date-title">M2 官方日期样例</text>
      <scroll-view scroll-x class="acceptance-scroll">
        <view class="scenario-row">
          <button v-for="item in acceptanceDateScenarios" :key="item" class="scenario-button" :class="{ active: dateScenario === item }" size="mini" @tap="selectDateScenario(item)">{{ m2AcceptanceDateLabels[item] }}</button>
        </view>
      </scroll-view>
    </view>

    <view class="top-row">
      <view>
        <text class="date">{{ model?.calendar.lunarDate || '今日' }} · {{ model?.calendar.weekday }}</text>
        <text v-if="model?.calendar.festival || model?.calendar.solarTerm" class="calendar-context">
          {{ model?.calendar.festival || model?.calendar.solarTerm }}<template v-if="model?.calendar.solarTermTime"> · {{ model.calendar.solarTermTime }}</template>
        </text>
        <text class="weather">{{ weatherLine }}</text>
      </view>
      <button class="city" size="mini" @tap="chooseCity">{{ profile.city }}⌄</button>
    </view>

    <view class="checkin">
      <text class="section-label">今天感觉怎么样？（可多选）</text>
      <scroll-view scroll-x class="chips">
        <view class="chip-row">
          <button v-for="item in feelings" :key="item" class="chip" :class="{ active: checkIn.feelings.includes(item) }" size="mini" @tap="toggleFeeling(item)">{{ item }}</button>
        </view>
      </scroll-view>
      <textarea v-model="checkIn.note" class="note-input" maxlength="100" placeholder="可补充轻微不适；高热、胸痛、呼吸困难等会停止推荐" @blur="saveCheckInAndReload" />
      <text class="checkin-hint">体感只用于当天排序；不会据此诊断疾病。</text>
    </view>

    <view v-if="loading" class="state-card">
      <view class="skeleton wide" /><view class="skeleton medium" /><view class="skeleton card" />
    </view>

    <view v-else-if="safety?.blocked" class="state-card safety-block">
      <text class="state-kicker">安全筛查已拦截</text>
      <text class="state-title">{{ safety.title }}</text>
      <text v-if="safety.matchedTriggers.length" class="matched">命中：{{ safety.matchedTriggers.join('、') }}</text>
      <text class="state-copy">{{ safety.message }}</text>
      <button class="secondary-button" @tap="openProfile">查看或修改档案</button>
    </view>

    <view v-else-if="error" class="state-card error-state">
      <text class="state-title">今日内容暂时没有加载出来</text>
      <text class="state-copy">你仍可浏览通用季节食谱，稍后再刷新天气。</text>
      <button class="secondary-button" @tap="loadToday">重新加载</button>
    </view>

    <view v-else-if="!model" class="state-card">
      <text class="state-title">没有符合当前硬性限制的推荐</text>
      <text class="state-copy">系统没有用不确定的替代项填充结果。请核对档案中的过敏和医生饮食限制，或仅浏览食材信息。</text>
    </view>

    <template v-else>
      <view v-if="model.contentBundle" class="context-card">
        <text class="context-kicker">{{ model.contentBundle.kind === 'festival' ? '节庆内容包' : '节气内容包' }}{{ model.contentBundle.isDemo ? ' · DEMO' : '' }}</text>
        <text class="context-name">{{ model.contentBundle.name }}</text>
        <text class="context-copy">{{ model.contentBundle.cultureNote }}</text>
      </view>

      <view class="recommend-card">
        <view class="card-accent" />
        <view class="card-body">
          <text class="eyebrow">今日主推荐</text>
          <text class="recipe-name">{{ model.main.name }}</text>
          <view class="tags"><text v-for="tag in model.main.tags" :key="tag" class="tag">{{ tag }}</text></view>
          <button class="primary-button" @tap="showRecipeDetail(model.main.id)">看食材和做法</button>
          <text class="reason"><text class="reason-strong">为什么推荐？</text>{{ shortReasons }}</text>
        </view>
      </view>

      <view v-if="model.alternatives.length" class="alternatives">
        <text class="section-title">两个备选</text>
        <view class="alternative-grid">
          <view v-for="item in model.alternatives" :key="item.id" class="alternative-card" @tap="showRecipeDetail(item.id)">
            <text class="alternative-name">{{ item.name }}</text>
            <text class="alternative-meta">{{ item.tags.join(' · ') }}</text>
          </view>
        </view>
      </view>

      <view class="reason-card" @tap="showReasons = !showReasons">
        <text class="reason-card-title">完整排序依据 {{ showReasons ? '收起' : '展开' }}</text>
        <template v-if="showReasons">
        <text v-for="item in model.recommendationReasons" :key="item" class="reason-item">· {{ item }}</text>
        </template>
      </view>
      <view v-if="model.fallbackUsed" class="fallback-note">已启用降级策略：天气不可用或内容包食谱被硬过滤时，展示城市季节通用安全候选。</view>
      <view class="safety-note">已先执行服务范围、高风险描述、药物/确诊情况和过敏禁忌筛查。结果只用于日常饮食参考，不替代诊断。</view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onShow } from '@dcloudio/uni-app'
import { runtimeConfig } from '../../config/runtime'
import { m2AcceptanceDateLabels, m2AcceptanceDates } from '../../data/m2'
import { acceptanceScenarioLabels, loadAcceptanceScenario, loadM2AcceptanceDateScenario, saveAcceptanceScenario, saveM2AcceptanceDateScenario } from '../../services/acceptance'
import { createDefaultCheckIn, loadDailyCheckIn, saveDailyCheckIn } from '../../services/checkin'
import { loadRecentMainRecipeIds, saveMainRecommendation } from '../../services/history'
import { loadProfile } from '../../services/profile'
import { getTodayExperience } from '../../services/today'
import type { DailyCheckIn, FeelingOption, M1AcceptanceScenario, M2AcceptanceDateScenario, SafetyDecision, TodayViewModel } from '../../types/domain'

const cities = ['杭州', '北京', '广州', '成都', '哈尔滨']
const feelings: FeelingOption[] = ['正常', '有点着凉', '胃口较差', '睡眠不足', '口干', '排便不规律', '其他轻微不适']
const acceptanceScenarios: M1AcceptanceScenario[] = ['normal', 'slow', 'weather-offline', 'error', 'empty']
const acceptanceDateScenarios: M2AcceptanceDateScenario[] = ['today', 'laba', 'spring-festival', 'duanwu', 'mid-autumn', 'lichun', 'qingming', 'bailu', 'dongzhi']
const profile = ref(loadProfile())
const scenario = ref<M1AcceptanceScenario>(loadAcceptanceScenario())
const dateScenario = ref<M2AcceptanceDateScenario>(loadM2AcceptanceDateScenario())
const checkIn = ref<DailyCheckIn>(createDefaultCheckIn(currentDateKey()))
const loading = ref(true)
const error = ref(false)
const safety = ref<SafetyDecision>()
const model = ref<TodayViewModel>()
const showReasons = ref(false)
let loadVersion = 0

const selectedDateKey = computed(() => m2AcceptanceDates[dateScenario.value] || currentDateKey())
const weatherLine = computed(() => {
  const weather = model.value?.weather
  if (!weather) return '正在读取今日上下文'
  if (!weather.available) return weather.text
  return `${weather.temperature}℃ ${weather.text}`
})
const shortReasons = computed(() => model.value?.recommendationReasons.slice(0, 4).join(' · ') || '')

function currentDateKey(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function loadCheckInForSelectedDate() {
  checkIn.value = loadDailyCheckIn(selectedDateKey.value)
}

async function loadToday() {
  const version = ++loadVersion
  loading.value = true
  error.value = false
  safety.value = undefined
  model.value = undefined
  showReasons.value = false
  try {
    const result = await getTodayExperience({
      profile: profile.value,
      checkIn: checkIn.value,
      scenario: scenario.value,
      date: m2AcceptanceDates[dateScenario.value],
      recentMainRecipeIds: loadRecentMainRecipeIds(selectedDateKey.value),
    })
    if (version !== loadVersion) return
    safety.value = result.safety
    model.value = result.model
    if (result.model) {
      try { saveMainRecommendation(result.model.calendar.dateKey, result.model.main.id) }
      catch { uni.showToast({ title: '推荐可用，历史记录未保存', icon: 'none' }) }
    }
  } catch {
    if (version === loadVersion) error.value = true
  } finally {
    if (version === loadVersion) {
      loading.value = false
      uni.stopPullDownRefresh()
    }
  }
}

function toggleFeeling(item: FeelingOption) {
  if (item === '正常') checkIn.value.feelings = ['正常']
  else {
    const selected = checkIn.value.feelings.filter((value) => value !== '正常')
    const index = selected.indexOf(item)
    index >= 0 ? selected.splice(index, 1) : selected.push(item)
    checkIn.value.feelings = selected.length ? selected : ['正常']
  }
  saveDailyCheckIn(checkIn.value)
  loadToday()
}

function saveCheckInAndReload() {
  saveDailyCheckIn(checkIn.value)
  loadToday()
}

function selectScenario(next: M1AcceptanceScenario) {
  scenario.value = next
  saveAcceptanceScenario(next)
  loadToday()
}

function selectDateScenario(next: M2AcceptanceDateScenario) {
  dateScenario.value = next
  saveM2AcceptanceDateScenario(next)
  loadCheckInForSelectedDate()
  loadToday()
}

function chooseCity() {
  uni.showActionSheet({ itemList: cities, success: ({ tapIndex }) => { profile.value.city = cities[tapIndex]; loadToday() } })
}

function openProfile() { uni.switchTab({ url: '/pages/profile/index' }) }
function showRecipeDetail(recipeId: string) { uni.navigateTo({ url: `/pages/recipe/detail?id=${encodeURIComponent(recipeId)}` }) }

onLoad(() => { loadCheckInForSelectedDate(); loadToday() })
onShow(() => {
  const next = loadProfile()
  const changed = JSON.stringify(next) !== JSON.stringify(profile.value)
  profile.value = next
  if (changed) loadToday()
})
onPullDownRefresh(loadToday)
</script>

<style scoped>
.page { min-height: 100vh; padding: 28rpx 28rpx 56rpx; box-sizing: border-box; }
.demo-badge { display: inline-block; padding: 8rpx 14rpx; margin-bottom: 22rpx; border-radius: 999rpx; color: #7b561d; background: #f5e8c8; font-size: 22rpx; font-weight: 700; }
.acceptance-panel { margin-bottom: 24rpx; padding: 20rpx; background: #edf3ef; border: 1rpx dashed #9aaba3; border-radius: 22rpx; }
.acceptance-title { display: block; margin-bottom: 12rpx; color: #52625b; font-size: 22rpx; font-weight: 700; }.date-title { margin-top: 18rpx; }
.acceptance-scroll { width: 100%; white-space: nowrap; }.scenario-row { display: inline-flex; gap: 10rpx; }
.scenario-button { margin: 0; padding: 0 20rpx; color: #42534c; background: #fffef9; border-radius: 999rpx; font-size: 22rpx; }.scenario-button.active { color: #fff; background: #123d35; }
.top-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28rpx; }.date, .weather { display: block; }.date { font-size: 34rpx; font-weight: 800; }
.calendar-context { display: block; margin-top: 6rpx; color: #8f5f18; font-size: 24rpx; font-weight: 700; }.weather { margin-top: 8rpx; color: #66766f; font-size: 25rpx; }
.city { margin: 0; padding: 0 24rpx; color: #123d35; background: #e7eee9; border-radius: 999rpx; font-size: 26rpx; }
.checkin { margin-bottom: 24rpx; }.section-label { color: #66766f; font-size: 26rpx; }.chips { width: 100%; margin-top: 12rpx; white-space: nowrap; }.chip-row { display: inline-flex; gap: 12rpx; }
.chip { margin: 0; padding: 0 24rpx; color: #42534c; background: #fffef9; border: 1rpx solid #d6dfd9; border-radius: 999rpx; font-size: 25rpx; }.chip.active { color: #fff; background: #123d35; border-color: #123d35; }
.note-input { box-sizing: border-box; width: 100%; height: 120rpx; margin-top: 16rpx; padding: 18rpx 20rpx; background: #fffef9; border: 1rpx solid #d6dfd9; border-radius: 18rpx; font-size: 24rpx; }
.checkin-hint { display: block; margin-top: 8rpx; color: #809088; font-size: 20rpx; }
.context-card { margin-bottom: 24rpx; padding: 24rpx; color: #3d4e46; background: #fff3d8; border-radius: 24rpx; }.context-kicker, .context-name, .context-copy { display: block; }
.context-kicker { color: #8f5f18; font-size: 21rpx; font-weight: 700; }.context-name { margin-top: 8rpx; color: #342512; font-family: serif; font-size: 38rpx; font-weight: 800; }.context-copy { margin-top: 10rpx; font-size: 23rpx; line-height: 1.7; }
.recommend-card { overflow: hidden; background: #fffef9; border-radius: 36rpx; box-shadow: 0 18rpx 55rpx rgba(18, 61, 53, .09); }.card-accent { height: 180rpx; background: linear-gradient(135deg, #d6a44a, #8f2e24); }.card-body { padding: 30rpx; }
.eyebrow { display: block; color: #66766f; font-size: 24rpx; }.recipe-name { display: block; margin: 10rpx 0 18rpx; font-family: serif; font-size: 52rpx; font-weight: 700; }
.tags { display: flex; flex-wrap: wrap; gap: 10rpx; margin-bottom: 26rpx; }.tag { padding: 8rpx 14rpx; color: #705321; background: #f5e8c8; border-radius: 12rpx; font-size: 22rpx; }
.primary-button { color: #fff; background: #123d35; border-radius: 22rpx; font-size: 28rpx; font-weight: 800; }.reason { display: block; margin-top: 22rpx; color: #66766f; font-size: 23rpx; line-height: 1.7; }.reason-strong { margin-right: 8rpx; color: #142b26; font-weight: 700; }
.alternatives { margin-top: 34rpx; }.section-title { display: block; margin-bottom: 18rpx; font-family: serif; font-size: 36rpx; font-weight: 700; }.alternative-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }
.alternative-card { padding: 24rpx; background: rgba(255,255,255,.7); border: 1rpx solid #dce2dc; border-radius: 24rpx; }.alternative-name, .alternative-meta { display: block; }.alternative-name { font-size: 28rpx; font-weight: 700; }.alternative-meta { margin-top: 10rpx; color: #66766f; font-size: 21rpx; line-height: 1.5; }
.reason-card { margin-top: 24rpx; padding: 22rpx; background: #f7f4eb; border-radius: 20rpx; }.reason-card-title, .reason-item { display: block; }.reason-card-title { margin-bottom: 8rpx; color: #263c35; font-size: 24rpx; font-weight: 700; }.reason-item { color: #66766f; font-size: 21rpx; line-height: 1.7; }
.safety-note, .fallback-note { margin-top: 24rpx; padding: 22rpx; border-radius: 20rpx; font-size: 22rpx; line-height: 1.6; }.safety-note { color: #5d6d66; background: #edf1ee; }.fallback-note { color: #79511f; background: #fff1d5; }
.state-card { padding: 28rpx; background: #fffef9; border-radius: 30rpx; }.safety-block { border: 2rpx solid #d9a07c; background: #fff5ed; }.state-kicker { display: block; margin-bottom: 10rpx; color: #a44a2f; font-size: 21rpx; font-weight: 800; }
.matched { display: block; margin-top: 14rpx; color: #8b422e; font-size: 23rpx; font-weight: 700; }.skeleton { height: 28rpx; margin-bottom: 20rpx; background: #e5e9e5; border-radius: 12rpx; }.skeleton.wide { width: 72%; }.skeleton.medium { width: 48%; }.skeleton.card { width: 100%; height: 320rpx; margin-top: 28rpx; }
.state-title, .state-copy { display: block; }.state-title { font-size: 32rpx; font-weight: 700; }.state-copy { margin-top: 14rpx; color: #66766f; line-height: 1.7; }.secondary-button { margin-top: 24rpx; color: #123d35; background: #edf3ef; border-radius: 20rpx; font-size: 27rpx; }
</style>
