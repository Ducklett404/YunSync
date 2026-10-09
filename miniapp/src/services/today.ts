import { createCalendarAdapter } from '../adapters/calendar'
import { createWeatherAdapter } from '../adapters/weather'
import { cloudApiEnabled, requestCloudNatural, requestCloudToday } from '../adapters/cloud'
import { rankM3Recommendations } from './recommendation'
import { matchPantryRecipes } from './pantry'
import { screenSafety } from './safety'
import { runtimeConfig } from '../config/runtime'
import { m2RecipeLibrary } from '../data/m2'
import type {
  DailyCheckIn,
  M1AcceptanceScenario,
  TodayExperienceResult,
  WeatherSnapshot,
  WellnessProfile,
} from '../types/domain'

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function unavailableWeather(city: string): WeatherSnapshot {
  return {
    city,
    text: '实时天气暂不可用，已使用城市季节通用内容',
    available: false,
    source: 'm1-acceptance-weather-offline',
    isDemo: true,
    version: 'm1-acceptance-1',
    reviewStatus: 'demo',
    updatedAt: new Date().toISOString(),
  }
}

function naturalRestrictions(text: string): string[] {
  const known = new Set(m2RecipeLibrary.flatMap(recipe => [
    ...recipe.ingredients.map(item => item.name), ...recipe.allergens,
  ]))
  ;['蒜', '大蒜', '花生', '鸡蛋', '牛奶', '大豆', '豆腐'].forEach(item => known.add(item))
  return [...known].filter(item => {
    if (!item) return false
    return ['过敏', '不耐受', '不能吃', '不吃', '别放'].some(term => text.includes(`${item}${term}`))
      || ['不吃', '不能吃', '忌'].some(term => text.includes(`${term}${item}`))
  })
}

function naturalSafety(profile: WellnessProfile, checkIn: DailyCheckIn, text: string) {
  const baseline = screenSafety(profile, { ...checkIn, note: `${checkIn.note} ${text}` })
  if (baseline.blocked || !text.trim()) return baseline
  if (/(孕妇|怀孕|哺乳|儿童|小孩|婴儿|未成年)/.test(text)) {
    return { blocked: true, level: 'out-of-scope' as const, matchedTriggers: [], title: '当前不在自动个体化范围内', message: '该人群需要专业人员结合具体情况提供建议。' }
  }
  if (/(糖尿病|肾病|肿瘤|透析|正在服药|吃药|用药|处方|治愈|治疗|治病|治感冒|退烧|药方|低盐|限盐|低钠|限钠|限钾|低钾|限磷|低磷|限糖|流质|半流质|低嘌呤|低蛋白)/.test(text)) {
    return { blocked: true, level: 'medical-review' as const, matchedTriggers: [], title: '请先遵循专业建议', message: '当前描述涉及疾病、用药或特殊饮食限制，已停止个体化推荐。' }
  }
  return baseline
}

export interface TodayExperienceRequest {
  profile: WellnessProfile
  checkIn: DailyCheckIn
  scenario?: M1AcceptanceScenario
  date?: string
  recentMainRecipeIds?: string[]
  naturalText?: string
}

export async function getTodayExperience({
  profile,
  checkIn,
  scenario = 'normal',
  date,
  recentMainRecipeIds = [],
  naturalText = '',
}: TodayExperienceRequest): Promise<TodayExperienceResult> {
  const safety = naturalSafety(profile, checkIn, naturalText)
  if (safety.blocked) return { safety }

  if (scenario === 'slow') await wait(2000)
  if (scenario === 'error') {
    await wait(350)
    throw new Error('M1 acceptance scenario: simulated content error')
  }
  if (scenario === 'empty') {
    await wait(350)
    return { safety }
  }

  const calendar = await createCalendarAdapter().getDate(date)

  if (scenario === 'normal' && cloudApiEnabled()) {
    try {
      if (naturalText.trim()) {
        const natural = await requestCloudNatural(naturalText.trim(), profile, date || calendar.dateKey, recentMainRecipeIds)
        if (natural.safety?.blocked) {
          return { safety: {
            blocked: true,
            level: natural.safety.level,
            matchedTriggers: [],
            title: '安全筛查已拦截',
            message: natural.safety.message,
          } }
        }
        if (natural.main) {
          return { safety, model: {
            calendar,
            weather: natural.weather,
            main: natural.main,
            alternatives: natural.alternatives.slice(0, 2),
            contentBundle: natural.seasonalContent,
            recommendationReasons: natural.reasons,
            fallbackUsed: natural.degraded.length > 0,
            aiExplanation: natural.explanation,
            aiStatus: natural.ai.status === 'assisted' ? 'assisted' : 'rules_fallback',
            usedFactors: natural.factors,
          } }
        }
        return { safety, message: natural.message }
      }
      const cloud = await requestCloudToday(
        profile,
        checkIn,
        date || calendar.dateKey,
        recentMainRecipeIds,
      )
      if (cloud.main) {
        return {
          safety,
          model: {
            calendar,
            weather: cloud.weather,
            main: cloud.main,
            alternatives: cloud.alternatives.slice(0, 2),
            contentBundle: cloud.seasonalContent,
            recommendationReasons: cloud.reasons,
            fallbackUsed: cloud.degraded.length > 0,
          },
        }
      }
    } catch {
      // 云 API 不可用时继续执行本地确定性规则，保留离线演示能力。
    }
  }

  const weather = scenario === 'weather-offline'
    ? unavailableWeather(profile.city)
    : await createWeatherAdapter().getCityWeather(profile.city)

  const fallbackCheckIn = naturalText.trim()
    ? { ...checkIn, feelings: [
      ...checkIn.feelings.filter(item => item !== '正常'),
      ...(naturalText.includes('着凉') || naturalText.includes('感冒') ? ['有点着凉' as const] : []),
      ...(naturalText.includes('胃口差') ? ['胃口较差' as const] : []),
      ...(naturalText.includes('口干') ? ['口干' as const] : []),
    ] as DailyCheckIn['feelings'] }
    : checkIn
  if (!fallbackCheckIn.feelings.length) fallbackCheckIn.feelings = ['正常']
  const localProfile = naturalText.trim()
    ? { ...profile, allergens: [...new Set([...profile.allergens, ...naturalRestrictions(naturalText)])] }
    : profile
  if (/(手上有|家里有|现成|冰箱|食材|做什么|做点|做饭)/.test(naturalText)) {
    const known = new Set(m2RecipeLibrary.flatMap(recipe => recipe.ingredients.map(item => item.name)))
    ;['鸡蛋', '西红柿', '豆腐', '蒜', '青菜', '面粉', '梨', '萝卜'].forEach(item => known.add(item))
    const restrictions = naturalRestrictions(naturalText)
    const ingredients = [...known].filter(item => naturalText.includes(item) && !restrictions.includes(item)).slice(0, 15)
    if (!ingredients.length) return { safety, message: '没有识别到当前审核食谱库可匹配的食材，请到食材页逐项选择。' }
    const matched = matchPantryRecipes({
      ingredients, tools: ['汤锅', '炒锅', '菜刀'], maxMinutes: 45,
      targetServings: 2, maxAdditionalIngredients: 1,
    }, localProfile, { allowDemoContent: runtimeConfig.dataMode === 'demo' })
    if (!matched.matches.length) return { safety, message: matched.message }
    return { safety, model: {
      calendar, weather, main: matched.matches[0].recipe,
      alternatives: matched.matches.slice(1, 3).map(item => item.recipe),
      recommendationReasons: ['本机审核食谱与已识别食材匹配', '按汤锅、炒锅、菜刀等常用厨具估算；请在食材页核对实际条件'],
      fallbackUsed: true, aiStatus: 'rules_fallback',
      usedFactors: { weather: weather.text, region: profile.city, feelings: fallbackCheckIn.feelings, ingredients },
    } }
  }
  const selection = rankM3Recommendations(calendar, weather, localProfile, fallbackCheckIn, recentMainRecipeIds, {
    allowDemoContent: runtimeConfig.dataMode === 'demo',
  })
  if (!selection.recipes.length) return { safety }

  return {
    safety,
    model: {
      calendar,
      weather,
      main: selection.recipes[0],
      alternatives: selection.recipes.slice(1, 3),
      contentBundle: selection.bundle,
      recommendationReasons: selection.reasons,
      fallbackUsed: selection.fallbackUsed,
      aiStatus: naturalText.trim() ? 'rules_fallback' : undefined,
    },
  }
}
