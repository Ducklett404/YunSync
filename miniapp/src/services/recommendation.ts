import { getCityRegion, getContentBundle, m2RecipeLibrary, recipeConflictsWith } from '../data/m2'
import type {
  CalendarContext,
  DailyCheckIn,
  RecipeTemplate,
  WeatherSnapshot,
  WellnessProfile,
} from '../types/domain'

interface RankedRecipe {
  recipe: RecipeTemplate
  score: number
}

export interface RecommendationSelection {
  bundle: ReturnType<typeof getContentBundle>
  recipes: RecipeTemplate[]
  reasons: string[]
  fallbackUsed: boolean
  filteredCount: number
}

const meatTerms = ['牛肉', '猪肉', '鸡肉', '鸭肉', '鱼', '虾', '羊肉']

function feelingScore(recipe: RecipeTemplate, checkIn: DailyCheckIn): number {
  let score = 0
  for (const feeling of checkIn.feelings) {
    if (feeling === '有点着凉' && ['粥', '汤'].includes(recipe.category)) score += 8
    if (feeling === '胃口较差' && ['粥', '汤'].includes(recipe.category)) score += 8
    if (feeling === '睡眠不足' && recipe.minutes <= 30) score += 5
    if (feeling === '口干' && recipe.category === '汤') score += 7
    if (feeling === '排便不规律' && recipe.ingredients.some((item) => /蔬菜|绿叶菜|豌豆|红豆|杂粮/.test(item.name))) score += 5
  }
  return score
}

function preferenceScore(recipe: RecipeTemplate, profile: WellnessProfile): number {
  let score = 0
  if (profile.preferences.includes('清淡') && recipe.tags.includes('清淡')) score += 6
  if (profile.preferences.includes('少油') && recipe.tags.includes('少油')) score += 6
  if (profile.preferences.includes('素食偏好')) {
    const containsMeat = recipe.ingredients.some((item) => meatTerms.some((term) => item.name.includes(term)))
    score += containsMeat ? -20 : 8
  }
  return score
}

function explanation(
  calendar: CalendarContext,
  weather: WeatherSnapshot,
  profile: WellnessProfile,
  checkIn: DailyCheckIn,
  filteredCount: number,
  repeatedAvoided: boolean,
): string[] {
  const reasons: string[] = []
  if (calendar.festival) reasons.push(`命中${calendar.festival}日期内容包`)
  else if (calendar.solarTerm) reasons.push(`命中${calendar.solarTerm}节气内容包`)
  reasons.push(`城市：${profile.city}${getCityRegion(profile.city) ? ` / ${getCityRegion(profile.city)}` : ''}`)
  if (checkIn.feelings.some((item) => item !== '正常')) reasons.push(`今日自述：${checkIn.feelings.join('、')}`)
  if (weather.available) reasons.push(`天气标签：${weather.text}`)
  else reasons.push('天气不可用，已使用城市季节通用内容')
  if (filteredCount > 0) reasons.push(`已硬过滤 ${filteredCount} 条过敏或明确禁忌冲突食谱`)
  if (repeatedAvoided) reasons.push('已降低近期主推荐的重复优先级')
  return reasons
}

export function rankM3Recommendations(
  calendar: CalendarContext,
  weather: WeatherSnapshot,
  profile: WellnessProfile,
  checkIn: DailyCheckIn,
  recentMainRecipeIds: string[] = [],
): RecommendationSelection {
  const bundle = getContentBundle(calendar, profile.city)
  const restrictions = [...profile.allergens, ...profile.doctorDietRestrictions]
  const safeRecipes = m2RecipeLibrary.filter((recipe) => !recipeConflictsWith(recipe, restrictions))
  const filteredCount = m2RecipeLibrary.length - safeRecipes.length
  const region = getCityRegion(profile.city)
  const bundleIds = new Set(bundle?.recipeIds || [])

  const ranked: RankedRecipe[] = safeRecipes.map((recipe) => {
    let score = 0
    if (bundleIds.has(recipe.id)) score += 100
    if (recipe.regions.includes('全国')) score += 4
    if (region && recipe.regions.includes(region)) score += 12
    score += feelingScore(recipe, checkIn)
    score += preferenceScore(recipe, profile)
    if (recentMainRecipeIds.includes(recipe.id)) score -= 60
    return { recipe, score }
  })

  ranked.sort((left, right) => right.score - left.score || left.recipe.id.localeCompare(right.recipe.id))
  const selected = ranked.slice(0, 3).map(({ recipe }) => ({ ...recipe }))
  const repeatedAvoided = Boolean(recentMainRecipeIds.length && selected[0] && !recentMainRecipeIds.includes(selected[0].id))
  const reasons = explanation(calendar, weather, profile, checkIn, filteredCount, repeatedAvoided)
  if (selected[0]) selected[0].reason = reasons.join('；')
  const bundleRecipeSelected = selected.some((recipe) => bundleIds.has(recipe.id))

  return {
    bundle,
    recipes: selected,
    reasons,
    fallbackUsed: !weather.available || Boolean(bundle && !bundleRecipeSelected),
    filteredCount,
  }
}
