import safetyRules from '../src/data/m3-safety-rules.json'
import { m2AcceptanceDates, m2RecipeLibrary, recipeConflictsWith, resolveDemoCalendar } from '../src/data/m2'
import { rankM3Recommendations as rankRecommendations } from '../src/services/recommendation'
import { screenSafety } from '../src/services/safety'
import type { DailyCheckIn, FeelingOption, ServiceScope, WeatherSnapshot, WellnessProfile } from '../src/types/domain'

interface CheckResult { name: string; passed: boolean; detail: string }

function rankM3Recommendations(...args: Parameters<typeof rankRecommendations>) {
  return rankRecommendations(args[0], args[1], args[2], args[3], args[4], { allowDemoContent: true })
}

const results: CheckResult[] = []

function check(name: string, passed: boolean, detail: string) {
  results.push({ name, passed, detail })
}

function profile(overrides: Partial<WellnessProfile> = {}): WellnessProfile {
  return {
    city: '杭州', ageGroup: '18—39岁', allergens: [], preferences: ['清淡'],
    medicalConditions: [], medications: [], doctorDietRestrictions: [], serviceScope: 'adult',
    constitutionSurveyInterest: false, updatedAt: '2026-01-01T00:00:00.000Z', ...overrides,
  }
}

function checkIn(note = '', feelings: FeelingOption[] = ['正常']): DailyCheckIn {
  return { dateKey: '2026-01-26', feelings, note, updatedAt: '2026-01-01T00:00:00.000Z' }
}

const weather: WeatherSnapshot = {
  city: '杭州', temperature: 8, humidity: 82, precipitation: 2, text: '小雨偏凉', available: true,
  source: 'M3 acceptance fixture', isDemo: true, version: 'm3-test', reviewStatus: 'demo', updatedAt: '2026-01-01T00:00:00.000Z',
}

let conflictTotal = 0
let conflictPassed = 0
function safetyConflict(name: string, passed: boolean, detail: string) {
  conflictTotal += 1
  if (passed) conflictPassed += 1
  check(name, passed, detail)
}

for (const trigger of safetyRules.urgentTriggers) {
  for (const term of trigger.terms) {
    const decision = screenSafety(profile(), checkIn(`我现在${term}`))
    safetyConflict(`高风险：${term}`, decision.blocked && decision.level === 'urgent', `${decision.level}/${decision.matchedTriggers.join('、')}`)
  }
}

for (const scope of Object.keys(safetyRules.outOfScopeLabels) as ServiceScope[]) {
  const decision = screenSafety(profile({ serviceScope: scope }), checkIn())
  safetyConflict(`特殊人群：${scope}`, decision.blocked && decision.level === 'out-of-scope', decision.level)
}

for (const restriction of safetyRules.unsupportedDoctorRestrictions) {
  const decision = screenSafety(profile({ doctorDietRestrictions: [restriction] }), checkIn())
  safetyConflict(`医疗限制：${restriction}`, decision.blocked && decision.level === 'medical-review', decision.level)
}

for (const [name, overrides] of [
  ['确诊情况', { medicalConditions: ['高血压'] }],
  ['正在用药', { medications: ['处方药'] }],
] as Array<[string, Partial<WellnessProfile>]>) {
  const decision = screenSafety(profile(overrides), checkIn())
  safetyConflict(name, decision.blocked && decision.level === 'medical-review', decision.level)
}

const allergenTerms = [...new Set(m2RecipeLibrary.flatMap((recipe) => recipe.allergens))]
for (const allergen of allergenTerms) {
  const selection = rankM3Recommendations(resolveDemoCalendar(m2AcceptanceDates.laba), weather, profile({ allergens: [allergen] }), checkIn())
  const passed = selection.recipes.every((recipe) => !recipeConflictsWith(recipe, [allergen]))
  safetyConflict(`过敏硬过滤：${allergen}`, passed, `返回 ${selection.recipes.length} 条，过滤 ${selection.filteredCount} 条`)
}

const labaGarlic = rankM3Recommendations(resolveDemoCalendar(m2AcceptanceDates.laba), weather, profile({ allergens: ['蒜'] }), checkIn())
check('V3-02 腊八蒜排除', !labaGarlic.recipes.some((recipe) => recipe.id === 'm2-laba-garlic'), labaGarlic.recipes.map((recipe) => recipe.id).join(','))

const mildCold = rankM3Recommendations(resolveDemoCalendar('2026-01-26'), weather, profile(), checkIn('', ['有点着凉']))
const mildColdText = mildCold.reasons.join('；')
check('V3-03 轻微着凉安全文案', mildCold.recipes.length > 0 && !/治疗|治愈|诊断|处方|调药/.test(mildColdText), mildColdText)

const dates = Object.values(m2AcceptanceDates).filter(Boolean) as string[]
let maxRecommendations = 0
for (const date of dates) {
  const selection = rankM3Recommendations(resolveDemoCalendar(date), weather, profile(), checkIn())
  maxRecommendations = Math.max(maxRecommendations, selection.recipes.length)
}
check('推荐数量上限', maxRecommendations <= 3, `最大返回 ${maxRecommendations} 条`)

const base = rankM3Recommendations(resolveDemoCalendar('2026-09-29'), weather, profile(), checkIn())
const repeated = rankM3Recommendations(resolveDemoCalendar('2026-09-29'), weather, profile(), checkIn(), [base.recipes[0]?.id].filter(Boolean) as string[])
check('近期主推荐去重复', Boolean(base.recipes[0] && repeated.recipes[0] && base.recipes[0].id !== repeated.recipes[0].id), `${base.recipes[0]?.id} -> ${repeated.recipes[0]?.id}`)

const offline = rankM3Recommendations(resolveDemoCalendar('2026-09-29'), { ...weather, available: false, text: '天气暂不可用', temperature: undefined }, profile(), checkIn())
check('天气不可用降级', offline.recipes.length > 0 && offline.fallbackUsed, `返回 ${offline.recipes.length} 条/fallback=${offline.fallbackUsed}`)

const conflictRate = conflictTotal ? (conflictPassed / conflictTotal) * 100 : 0
check('安全冲突拦截率', conflictRate === 100, `${conflictPassed}/${conflictTotal} = ${conflictRate.toFixed(2)}%`)

export function runM3Validation() {
  return {
    milestone: 'M3',
    safetyConflictRate: conflictRate,
    conflictPassed,
    conflictTotal,
    maxRecommendations,
    passed: results.every((item) => item.passed),
    checks: results,
  }
}
