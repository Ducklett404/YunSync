<template>
  <view class="page">
    <text class="title">体质参考</text>
    <view v-if="!available" class="card">
      <text class="card-title">问卷暂未开放</text>
      <text class="copy">只有取得正式授权并经专业审核的题库才会在这里显示。未填写不影响使用通用季节食谱。</text>
    </view>
    <template v-else>
      <text class="copy">请选择最接近近期日常感受的选项。结果只作生活方式参考，不用于诊断疾病或证候。</text>
      <view v-for="(question, index) in survey.questions" :key="question.id" class="card">
        <text class="card-title">{{ index + 1 }}. {{ question.prompt }}</text>
        <radio-group @change="selectAnswer(question.id, $event)">
          <label v-for="option in question.options" :key="option.id" class="option-row">
            <radio :value="option.id" :checked="answers[question.id] === option.id" color="#123d35" />
            <text>{{ option.label }}</text>
          </label>
        </radio-group>
      </view>
      <button class="primary-button" @tap="submit">生成体质参考</button>
      <view v-if="result" class="result-card">
        <text class="card-title">参考结果：{{ result.labels.join('、') }}</text>
        <text v-for="outcome in resultOutcomes" :key="outcome.id" class="copy">{{ outcome.description }}</text>
        <text class="trace">来源：{{ survey.source }} · 审核：{{ survey.reviewer }} · 版本：{{ survey.version }}</text>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import {
  constitutionSurvey as survey, evaluateConstitutionSurvey, isConstitutionSurveyAvailable,
  loadConstitutionSurveyResult, saveConstitutionSurveyResult,
} from '../../services/constitution'
import type { ConstitutionSurveyResult } from '../../services/constitution'
import { loadProfile, saveProfile } from '../../services/profile'

const available = isConstitutionSurveyAvailable()
const saved = loadConstitutionSurveyResult()
const answers = reactive<Record<string, string>>({ ...(saved?.surveyVersion === survey.version ? saved.answers : {}) })
const result = ref<ConstitutionSurveyResult | undefined>(saved?.surveyVersion === survey.version ? saved : undefined)
const resultOutcomes = computed(() => survey.outcomes.filter(outcome => result.value?.outcomeIds.includes(outcome.id)))

function selectAnswer(questionId: string, event: Event) {
  answers[questionId] = (event as unknown as { detail: { value: string } }).detail.value
}
function submit() {
  try {
    const next = evaluateConstitutionSurvey(survey, answers)
    saveConstitutionSurveyResult(next)
    const profile = loadProfile()
    profile.constitutionReference = {
      labels: next.labels,
      recommendationTags: next.recommendationTags,
      surveyVersion: next.surveyVersion,
    }
    saveProfile(profile)
    result.value = next
    uni.showToast({ title: '参考结果已保存', icon: 'success' })
  } catch {
    uni.showToast({ title: '请完成全部题目', icon: 'none' })
  }
}
</script>

<style scoped>
.page { min-height: 100vh; padding: 36rpx 30rpx 60rpx; box-sizing: border-box; }
.title, .copy, .card-title, .trace { display: block; }
.title { font-family: serif; font-size: 48rpx; font-weight: 800; }
.copy { margin-top: 14rpx; color: #63736c; font-size: 24rpx; line-height: 1.7; }
.card, .result-card { margin-top: 28rpx; padding: 28rpx; background: #fffef9; border-radius: 26rpx; }
.result-card { background: #edf3ef; }
.card-title { color: #142b26; font-size: 28rpx; font-weight: 800; line-height: 1.5; }
.option-row { display: flex; align-items: center; gap: 14rpx; padding: 22rpx 0; color: #334840; font-size: 25rpx; border-bottom: 1rpx solid #e7e9e5; }
.option-row:last-child { border-bottom: 0; }
.primary-button { margin-top: 32rpx; color: #fff; background: #123d35; border-radius: 22rpx; font-size: 28rpx; font-weight: 800; }
.trace { margin-top: 20rpx; color: #718078; font-size: 20rpx; line-height: 1.6; }
</style>
