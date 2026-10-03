<template>
  <view class="page">
    <view class="demo-badge">DEMO · 仅本机保存</view>
    <text class="title">我的</text>
    <text class="copy">管理收藏、浏览记录和轻量档案。日常饮食建议不替代诊疗。</text>

    <view v-for="section in savedSections" :key="section.kind" class="form-card">
      <text class="section-title">{{ section.title }}（{{ section.items.length }}）</text>
      <text v-if="!section.items.length" class="helper">{{ section.kind === 'favorites' ? '在食谱详情中收藏，之后就能在这里找到。' : '打开食谱详情后会留下浏览记录，最多保存最近 20 道。' }}</text>
      <view v-for="item in section.items" :key="item.recipeId" class="saved-row">
        <view class="saved-copy">
          <text class="saved-name">{{ item.name }}</text>
          <text class="helper">{{ item.statusLabel }} · {{ item.updatedAt.slice(0, 10) }}</text>
          <text v-if="item.versionChanged" class="helper">版本已更新：{{ item.version }} → {{ item.currentVersion }}</text>
        </view>
        <view class="saved-actions">
          <button v-if="item.available" class="small-button" tabindex="0" @click="openRecipe(item.recipeId)" @keydown.enter="openRecipe(item.recipeId)">查看</button>
          <button v-if="section.kind === 'favorites'" class="small-button muted" tabindex="0" @click="removeFavorite(item.recipeId)" @keydown.enter="removeFavorite(item.recipeId)">移除</button>
        </view>
      </view>
    </view>

    <view class="form-card">
      <text class="section-title">基本情况</text>
      <text class="label">城市</text>
      <picker :range="cities" :value="cityIndex" @change="onCityChange"><view class="field">{{ form.city }}⌄</view></picker>
      <text class="label">年龄段</text>
      <picker :range="ageGroups" :value="ageIndex" @change="onAgeChange"><view class="field">{{ form.ageGroup }}⌄</view></picker>
      <text class="label">适用人群</text>
      <picker :range="scopeLabels" :value="scopeIndex" @change="onScopeChange"><view class="field">{{ scopeLabels[scopeIndex] }}⌄</view></picker>
      <text v-if="form.serviceScope !== 'adult'" class="warning-copy">当前版本不为该人群自动生成个体化饮食推荐。</text>

      <text class="section-title spaced">安全信息</text>
      <text class="helper">以下内容优先用于拦截。多项请用顿号或逗号分隔；没有可留空。</text>
      <text class="label">已知过敏或不耐受</text>
      <input v-model="allergenText" class="field input" placeholder="如：花生、牛奶、蒜" />
      <text class="label">已确诊情况</text>
      <input v-model="conditionText" class="field input" placeholder="填写后将暂停自动个体化推荐" />
      <text class="label">正在使用的药物</text>
      <input v-model="medicationText" class="field input" placeholder="填写后将暂停自动个体化推荐" />
      <text class="label">医生明确要求的饮食限制</text>
      <input v-model="restrictionText" class="field input" placeholder="如：忌花生；低钾饮食" />
      <text class="helper">能对应具体食材的限制会硬过滤；需要营养成分或质地数据的限制会停止推荐。</text>

      <text class="section-title spaced">饮食偏好</text>
      <view class="chips">
        <button v-for="item in preferences" :key="item" class="chip" :class="{ active: form.preferences.includes(item) }" size="mini" @tap="togglePreference(item)">{{ item }}</button>
      </view>

      <view class="interest-row">
        <view>
          <text class="interest-title">愿意稍后填写体质参考问卷</text>
          <text class="helper">仅记录意愿；问卷尚未授权，当前不会启用。</text>
        </view>
        <switch :checked="form.constitutionSurveyInterest" color="#123d35" @change="onSurveyInterestChange" />
      </view>

      <button class="primary-button" tabindex="0" @click="save" @keydown.enter="save">保存本机档案</button>
    </view>

    <view class="safety-note">高热、胸痛、呼吸困难等情况不适合使用日常饮食推荐，应及时就医。儿童、孕哺期、复杂慢病、肿瘤治疗期、透析期和进食障碍人群当前均在服务范围外。</view>
    <view class="form-card">
      <text class="section-title">本机记录与隐私</text>
      <text class="helper">档案和体感用于安全筛查；收藏、浏览记录和食谱反馈只保存在当前设备，不跨设备同步。当前无需定位权限，可手动选择城市。反馈只记录所选选项和食谱版本，请勿填写个人健康信息。</text>
      <text class="helper">以下操作清除收藏、最近浏览和食谱反馈，保留用于安全筛查的档案与体感。</text>
      <button class="small-button clear-button" tabindex="0" @click="confirmClearRecords" @keydown.enter="confirmClearRecords">清除收藏、浏览与反馈</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { loadProfile, saveProfile } from '../../services/profile'
import { runtimeConfig } from '../../config/runtime'
import { clearEngagement, loadSavedRecipes, setFavorite } from '../../services/engagement'
import type { SavedRecipeView } from '../../services/engagement'
import type { ServiceScope } from '../../types/domain'

const cities = ['杭州', '北京', '广州', '成都', '哈尔滨']
const ageGroups = ['18–39岁', '40–59岁', '60岁及以上']
const preferences = ['清淡', '少辣', '素食偏好', '少油']
const scopes: Array<{ key: ServiceScope; label: string }> = [
  { key: 'adult', label: '普通成年人' },
  { key: 'child', label: '儿童（停止自动推荐）' },
  { key: 'pregnant-or-breastfeeding', label: '孕哺期（停止自动推荐）' },
  { key: 'complex-chronic', label: '复杂慢病（停止自动推荐）' },
  { key: 'oncology-treatment', label: '肿瘤治疗期（停止自动推荐）' },
  { key: 'dialysis', label: '透析期（停止自动推荐）' },
  { key: 'eating-disorder', label: '进食障碍（停止自动推荐）' },
]

const form = reactive(loadProfile())
const favorites = ref<SavedRecipeView[]>([])
const recent = ref<SavedRecipeView[]>([])
const contentOptions = { allowDemoContent: runtimeConfig.dataMode === 'demo' }
const savedSections = computed(() => [
  { kind: 'favorites', title: '我的收藏', items: favorites.value },
  { kind: 'recent', title: '最近浏览', items: recent.value },
])
function refreshRecords() {
  favorites.value = loadSavedRecipes('favorites', contentOptions)
  recent.value = loadSavedRecipes('recent', contentOptions)
}
function openRecipe(id: string) {
  uni.navigateTo({ url: `/pages/recipe/detail?id=${encodeURIComponent(id)}` })
}
function removeFavorite(id: string) {
  try { setFavorite(id, false); refreshRecords() }
  catch { uni.showToast({ title: '移除失败，请重试', icon: 'none' }) }
}
function confirmClearRecords() {
  uni.showModal({
    title: '清除本机记录？', content: '将删除收藏、最近浏览和食谱反馈，无法恢复。轻量档案和体感会保留。',
    cancelText: '取消', confirmText: '清除',
    success(result) {
      if (!result.confirm) return
      try { clearEngagement(); refreshRecords(); uni.showToast({ title: '记录已清除', icon: 'success' }) }
      catch { uni.showToast({ title: '清除失败，请重试', icon: 'none' }) }
    },
  })
}
onShow(refreshRecords)
const allergenText = ref(form.allergens.join('、'))
const conditionText = ref(form.medicalConditions.join('、'))
const medicationText = ref(form.medications.join('、'))
const restrictionText = ref(form.doctorDietRestrictions.join('、'))
const cityIndex = computed(() => Math.max(0, cities.indexOf(form.city)))
const ageIndex = computed(() => Math.max(0, ageGroups.indexOf(form.ageGroup)))
const scopeIndex = computed(() => Math.max(0, scopes.findIndex((item) => item.key === form.serviceScope)))
const scopeLabels = computed(() => scopes.map((item) => item.label))

function splitList(value: string): string[] {
  return value.split(/[、，,;；/]/).map((item) => item.trim()).filter(Boolean)
}

function onCityChange(event: { detail: { value: string } }) { form.city = cities[Number(event.detail.value)] }
function onAgeChange(event: { detail: { value: string } }) { form.ageGroup = ageGroups[Number(event.detail.value)] }
function onScopeChange(event: { detail: { value: string } }) { form.serviceScope = scopes[Number(event.detail.value)].key }
function togglePreference(item: string) {
  const index = form.preferences.indexOf(item)
  index >= 0 ? form.preferences.splice(index, 1) : form.preferences.push(item)
}
function onSurveyInterestChange(event: Event) {
  form.constitutionSurveyInterest = Boolean((event as unknown as { detail: { value: boolean } }).detail.value)
}

function save() {
  form.allergens = splitList(allergenText.value)
  form.medicalConditions = splitList(conditionText.value)
  form.medications = splitList(medicationText.value)
  form.doctorDietRestrictions = splitList(restrictionText.value)
  try {
    saveProfile(form)
    uni.showToast({ title: '已保存在本机', icon: 'success' })
  } catch {
    uni.showToast({ title: '保存失败，请重试', icon: 'none' })
  }
}
</script>

<style scoped>
.page { padding: 40rpx 30rpx 60rpx; }
.demo-badge { display: inline-block; padding: 8rpx 14rpx; color: #7b561d; background: #f5e8c8; border-radius: 999rpx; font-size: 22rpx; }
.title, .copy, .label, .section-title, .helper, .warning-copy, .interest-title { display: block; }
.title { margin-top: 28rpx; font-family: serif; font-size: 50rpx; font-weight: 700; }
.copy { margin-top: 12rpx; color: #66766f; font-size: 26rpx; line-height: 1.7; }
.form-card { margin-top: 32rpx; padding: 30rpx; background: #fffef9; border-radius: 30rpx; }
.section-title { color: #142b26; font-size: 30rpx; font-weight: 800; }
.section-title.spaced { margin-top: 42rpx; }
.label { margin: 28rpx 0 12rpx; color: #52625b; font-size: 25rpx; }
.field { padding: 22rpx 24rpx; background: #f1f4f1; border-radius: 18rpx; font-size: 28rpx; }
.input { box-sizing: border-box; width: 100%; height: 92rpx; }
.helper { margin-top: 10rpx; color: #718078; font-size: 21rpx; line-height: 1.55; }
.warning-copy { margin-top: 10rpx; color: #9a4d2f; font-size: 22rpx; }
.chips { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 18rpx; }
.chip { margin: 0; padding: 0 22rpx; color: #42534c; background: #f1f4f1; border-radius: 999rpx; font-size: 24rpx; }
.chip.active { color: #fff; background: #123d35; }
.interest-row { display: flex; justify-content: space-between; align-items: center; gap: 18rpx; margin-top: 34rpx; padding: 22rpx; background: #f7f4eb; border-radius: 20rpx; }
.interest-title { color: #263c35; font-size: 25rpx; font-weight: 700; }
.primary-button { margin-top: 36rpx; color: #fff; background: #123d35; border-radius: 22rpx; font-size: 28rpx; font-weight: 800; }
.safety-note { margin-top: 24rpx; padding: 22rpx; color: #5d6d66; background: #edf1ee; border-radius: 20rpx; font-size: 22rpx; line-height: 1.6; }
.saved-row { display: flex; justify-content: space-between; gap: 18rpx; padding: 24rpx 0; border-bottom: 1rpx solid #e3e7e3; }
.saved-row:last-child { border-bottom: 0; }
.saved-copy { flex: 1; min-width: 0; }
.saved-name { display: block; font-size: 27rpx; font-weight: 700; }
.saved-actions { display: flex; flex-direction: column; gap: 12rpx; }
.small-button { margin: 0; padding: 0 20rpx; color: #fff; background: #123d35; border-radius: 16rpx; font-size: 23rpx; }
.small-button.muted, .clear-button { color: #52625b; background: #edf1ee; }
.clear-button { margin-top: 22rpx; }
</style>
