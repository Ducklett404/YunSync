import rawRules from '../data/m3-safety-rules.json'
import type { DailyCheckIn, SafetyDecision, ServiceScope, WellnessProfile } from '../types/domain'

interface SafetyRules {
  version: string
  urgentTriggers: Array<{ id: string; label: string; terms: string[] }>
  outOfScopeLabels: Partial<Record<ServiceScope, string>>
  unsupportedDoctorRestrictions: string[]
  messages: {
    urgentTitle: string
    urgent: string
    outOfScopeTitle: string
    outOfScope: string
    medicalReviewTitle: string
    medicalReview: string
  }
}

const rules = rawRules as unknown as SafetyRules

function compact(value: string): string {
  return value.toLowerCase().replace(/[\s，,。.!！?？、]/g, '')
}

export function collectHardRestrictions(profile: WellnessProfile): string[] {
  return [...profile.allergens, ...profile.doctorDietRestrictions]
    .map((item) => item.trim())
    .filter(Boolean)
}

export function screenSafety(profile: WellnessProfile, checkIn: DailyCheckIn): SafetyDecision {
  const note = compact(checkIn.note)
  const matchedUrgent = rules.urgentTriggers
    .filter((trigger) => trigger.terms.some((term) => note.includes(compact(term))))
    .map((trigger) => trigger.label)

  if (matchedUrgent.length) {
    return {
      blocked: true,
      level: 'urgent',
      matchedTriggers: matchedUrgent,
      title: rules.messages.urgentTitle,
      message: rules.messages.urgent,
    }
  }

  if (profile.serviceScope !== 'adult') {
    const label = rules.outOfScopeLabels[profile.serviceScope] || '特殊人群'
    return {
      blocked: true,
      level: 'out-of-scope',
      matchedTriggers: [label],
      title: rules.messages.outOfScopeTitle,
      message: rules.messages.outOfScope,
    }
  }

  const unsupportedRestrictions = profile.doctorDietRestrictions.filter((restriction) =>
    rules.unsupportedDoctorRestrictions.some((term) => compact(restriction).includes(compact(term))),
  )
  if (unsupportedRestrictions.length) {
    return {
      blocked: true,
      level: 'medical-review',
      matchedTriggers: unsupportedRestrictions,
      title: rules.messages.medicalReviewTitle,
      message: '检测到需要营养成分或质地数据才能安全执行的医生饮食限制。当前演示食谱不具备这些审核数据，已停止个体化推荐。',
    }
  }

  const medicalInputs = [...profile.medicalConditions, ...profile.medications]
    .map((item) => item.trim())
    .filter(Boolean)
  if (medicalInputs.length) {
    return {
      blocked: true,
      level: 'medical-review',
      matchedTriggers: medicalInputs,
      title: rules.messages.medicalReviewTitle,
      message: rules.messages.medicalReview,
    }
  }

  return {
    blocked: false,
    level: 'clear',
    matchedTriggers: [],
    title: '安全筛查通过',
    message: '未命中当前规则中的高风险描述或超范围人群；推荐仍只属于日常饮食建议。',
  }
}

export const safetyRuleVersion = rules.version
