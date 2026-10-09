import { runtimeConfig } from '../config/runtime'
import type {
  FestivalContentBundle,
  PantryRecipeMatch,
  RecipeTemplate,
  WeatherSnapshot,
  WellnessProfile,
  DailyCheckIn,
  PantrySession,
  SafetyDecision,
} from '../types/domain'

interface CloudCacheStatus {
  status: 'hit' | 'miss' | 'bypass'
  backend: 'redis' | 'memory'
  ttlSeconds?: number
}

interface CloudTodayResponse {
  requestId: string
  ruleVersion: string
  main: RecipeTemplate | null
  alternatives: RecipeTemplate[]
  seasonalContent?: FestivalContentBundle
  weather: WeatherSnapshot
  reasons: string[]
  degraded: string[]
  cache: CloudCacheStatus
}

interface CloudPantryResponse {
  requestId: string
  ruleVersion: string
  matches: PantryRecipeMatch[]
  filteredCount: number
  message: string
  degraded: string[]
  cache: CloudCacheStatus
}

export interface CloudNaturalResponse extends CloudTodayResponse {
  mode: 'today' | 'pantry'
  safety: Pick<SafetyDecision, 'blocked' | 'level' | 'message'>
  ai: { status: 'assisted' | 'rules_fallback' | 'not_called'; promptVersion: string }
  explanation?: string
  factors?: { weather: string; region: string; seasonal?: string | null; feelings: string[]; ingredients: string[] }
  message?: string
}

const reasonLabels: Record<string, string> = {
  seasonal_content: '命中今日节庆或节气内容包',
  safety_filtered: '已排除过敏和明确饮食限制冲突',
  weather_ranked: '实时天气参与排序',
  region_ranked: '地域标签参与排序',
  feeling_ranked: '当天受控体感标签参与排序',
  general_safe_content: '从当前可用审核库中选择通用候选',
  pantry_match: '现有食材和常用厨具参与匹配',
}

function requestCloud<T>(path: string, data: Record<string, unknown>): Promise<T> {
  if (!runtimeConfig.cloudApiBaseUrl) return Promise.reject(new Error('云 API 未配置'))
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${runtimeConfig.cloudApiBaseUrl}${path}`,
      method: 'POST',
      data,
      timeout: runtimeConfig.cloudApiTimeoutMs,
      header: { 'Content-Type': 'application/json' },
      success: (response) => {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          reject(new Error(`云 API HTTP ${response.statusCode}`))
          return
        }
        resolve(response.data as T)
      },
      fail: reject,
    })
  })
}

function cityRegion(city: string): string {
  const regions: Record<string, string> = {
    北京: '华北', 杭州: '江南', 广州: '华南', 成都: '西南', 哈尔滨: '东北',
  }
  return regions[city] || '全国'
}

function assertTraceableRecipe(recipe: RecipeTemplate | null): void {
  if (!recipe) return
  if (!recipe.id || !recipe.source || !recipe.version || !recipe.reviewStatus) {
    throw new Error('云 API 返回了不可追溯的食谱')
  }
}

export function cloudApiEnabled(): boolean {
  return Boolean(runtimeConfig.cloudApiBaseUrl)
}

export async function requestCloudToday(
  profile: WellnessProfile,
  checkIn: DailyCheckIn,
  date: string,
  recentRecipeIds: string[],
): Promise<CloudTodayResponse> {
  const response = await requestCloud<CloudTodayResponse>('/v1/recommendations/today', {
    city: profile.city,
    region: cityRegion(profile.city),
    date,
    feelings: checkIn.feelings,
    allergies: profile.allergens,
    dietaryRestrictions: profile.doctorDietRestrictions,
    preferences: profile.preferences,
    constitutionTags: profile.constitutionReference?.recommendationTags || [],
    recentRecipeIds,
  })
  assertTraceableRecipe(response.main)
  response.alternatives.forEach(assertTraceableRecipe)
  return {
    ...response,
    reasons: response.reasons.map(reason => reasonLabels[reason] || reason),
  }
}

export async function requestCloudNatural(
  text: string,
  profile: WellnessProfile,
  date: string,
  recentRecipeIds: string[],
): Promise<CloudNaturalResponse> {
  const response = await requestCloud<CloudNaturalResponse>('/v1/recommendations/natural', {
    text,
    city: profile.city,
    region: cityRegion(profile.city),
    date,
    allergies: profile.allergens,
    dietaryRestrictions: profile.doctorDietRestrictions,
    preferences: profile.preferences,
    constitutionTags: profile.constitutionReference?.recommendationTags || [],
    recentRecipeIds,
    serviceScope: profile.serviceScope,
    hasMedicalConditions: profile.medicalConditions.length > 0,
    hasMedications: profile.medications.length > 0,
  })
  assertTraceableRecipe(response.main)
  response.alternatives.forEach(assertTraceableRecipe)
  return { ...response, reasons: (response.reasons || []).map(reason => reasonLabels[reason] || reason) }
}

export async function requestCloudPantry(
  session: PantrySession,
  profile: WellnessProfile,
): Promise<CloudPantryResponse> {
  const response = await requestCloud<CloudPantryResponse>('/v1/recommendations/pantry', {
    ingredients: session.ingredients,
    tools: session.tools,
    maxMinutes: session.maxMinutes,
    targetServings: session.targetServings,
    maxAdditionalIngredients: session.maxAdditionalIngredients,
    allergies: profile.allergens,
    dietaryRestrictions: profile.doctorDietRestrictions,
  })
  response.matches.forEach(item => assertTraceableRecipe(item.recipe))
  return response
}
