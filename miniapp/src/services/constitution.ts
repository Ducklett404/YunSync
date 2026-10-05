import rawSurvey from '../data/official-survey.json'
import { runtimeConfig } from '../config/runtime'
import type { ReviewStatus } from '../types/domain'

export interface SurveyOption {
  id: string
  label: string
  scores: Record<string, number>
}

export interface SurveyQuestion {
  id: string
  prompt: string
  options: SurveyOption[]
}

export interface SurveyOutcome {
  id: string
  label: string
  description: string
  recommendationTags: string[]
}

export interface ConstitutionSurveyDefinition {
  source: string
  licenseVersion: string
  reviewer: string
  isDemo: boolean
  version: string
  reviewStatus: ReviewStatus
  updatedAt: string
  questions: SurveyQuestion[]
  outcomes: SurveyOutcome[]
}

export interface ConstitutionSurveyResult {
  surveyVersion: string
  answers: Record<string, string>
  outcomeIds: string[]
  labels: string[]
  recommendationTags: string[]
  completedAt: string
}

const STORAGE_KEY = 'yunsync:constitution-survey:v1'
export const constitutionSurvey = rawSurvey as unknown as ConstitutionSurveyDefinition

export function isConstitutionSurveyAvailable(definition = constitutionSurvey): boolean {
  return runtimeConfig.surveyEnabled
    && definition.reviewStatus === 'approved'
    && !definition.isDemo
    && Boolean(definition.source && definition.licenseVersion && definition.reviewer && definition.version)
    && definition.questions.length > 0
    && definition.outcomes.length > 0
}

export function evaluateConstitutionSurvey(
  definition: ConstitutionSurveyDefinition,
  answers: Record<string, string>,
  completedAt = new Date(),
): ConstitutionSurveyResult {
  const scores = Object.fromEntries(definition.outcomes.map(outcome => [outcome.id, 0]))
  for (const question of definition.questions) {
    const option = question.options.find(item => item.id === answers[question.id])
    if (!option) throw new Error(`问题 ${question.id} 尚未完成`)
    for (const [outcomeId, score] of Object.entries(option.scores)) {
      if (Object.prototype.hasOwnProperty.call(scores, outcomeId) && Number.isFinite(score)) scores[outcomeId] += score
    }
  }
  const highest = Math.max(...Object.values(scores))
  const outcomeIds = Object.entries(scores).filter(([, score]) => score === highest).map(([id]) => id)
  const labels = definition.outcomes.filter(outcome => outcomeIds.includes(outcome.id)).map(outcome => outcome.label)
  const recommendationTags = [...new Set(definition.outcomes
    .filter(outcome => outcomeIds.includes(outcome.id))
    .flatMap(outcome => outcome.recommendationTags))]
  return { surveyVersion: definition.version, answers: { ...answers }, outcomeIds, labels, recommendationTags, completedAt: completedAt.toISOString() }
}

export function loadConstitutionSurveyResult(): ConstitutionSurveyResult | undefined {
  try {
    const value = uni.getStorageSync(STORAGE_KEY) as ConstitutionSurveyResult | undefined
    return value?.surveyVersion && Array.isArray(value.labels) ? value : undefined
  } catch {
    return undefined
  }
}

export function saveConstitutionSurveyResult(result: ConstitutionSurveyResult): void {
  uni.setStorageSync(STORAGE_KEY, result)
}
