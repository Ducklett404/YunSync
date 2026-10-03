import { festivalContentBundles, m2RecipeLibrary, resolveDemoCalendar } from '../src/data/m2'
import { isContentAvailable } from '../src/services/content'
import {
  clearEngagement, engagementLimits, isFavorite, loadRecipeFeedback, loadSavedRecipes,
  recordRecipeView, saveRecipeFeedback, setFavorite,
} from '../src/services/engagement'
import { rankM3Recommendations } from '../src/services/recommendation'
import { matchPantryRecipes } from '../src/services/pantry'
import type { DailyCheckIn, RecipeTemplate, WeatherSnapshot, WellnessProfile } from '../src/types/domain'

export function runM5Validation() {
  const checks: Array<{ name: string; passed: boolean }> = []
  const check = (name: string, passed: boolean) => checks.push({ name, passed })
  const throws = (action: () => void) => { try { action(); return false } catch { return true } }
  const storage = new Map<string, unknown>()
  let readFails = false
  let writeFails = false
  const root = globalThis as unknown as { uni: unknown }
  const previousUni = root.uni
  root.uni = {
    getStorageSync: (key: string) => { if (readFails) throw new Error('read failure'); return storage.get(key) },
    setStorageSync: (key: string, value: unknown) => { if (writeFails) throw new Error('quota'); storage.set(key, JSON.parse(JSON.stringify(value))) },
    removeStorageSync: (key: string) => { if (writeFails) throw new Error('remove failure'); storage.delete(key) },
  }
  const key = 'yunsync:engagement:v1'
  const demo = { allowDemoContent: true }
  const recipe = m2RecipeLibrary[0]
  const originalRecipe = { ...recipe }
  const bundle = festivalContentBundles[0]
  const originalBundle = { ...bundle }
  const originalLength = m2RecipeLibrary.length
  const profile: WellnessProfile = {
    city: '杭州', ageGroup: '18–39岁', allergens: [], preferences: [], medicalConditions: [], medications: [],
    doctorDietRestrictions: [], serviceScope: 'adult', constitutionSurveyInterest: false, updatedAt: new Date().toISOString(),
  }
  const checkIn: DailyCheckIn = { dateKey: '2026-01-26', feelings: ['正常'], note: '', updatedAt: profile.updatedAt }
  const weather: WeatherSnapshot = { city: '杭州', text: '天气不可用', available: false, source: 'fixture', isDemo: true, version: 'test', reviewStatus: 'demo', updatedAt: profile.updatedAt }
  const rank = (allowDemoContent = true) => rankM3Recommendations(resolveDemoCalendar('2026-01-26'), weather, profile, checkIn, [], { allowDemoContent })

  try {
    check('空记录可读取', loadSavedRecipes('favorites', demo).length === 0)
    setFavorite(recipe.id, true, demo)
    setFavorite(recipe.id, true, demo)
    check('重复收藏只保存一条', isFavorite(recipe.id) && loadSavedRecipes('favorites', demo).length === 1)
    recordRecipeView(recipe.id, demo)
    recordRecipeView(m2RecipeLibrary[1].id, demo)
    recordRecipeView(recipe.id, demo)
    check('最近浏览去重并置顶', loadSavedRecipes('recent', demo).length === 2 && loadSavedRecipes('recent', demo)[0].recipeId === recipe.id)
    saveRecipeFeedback(recipe.id, 'helpful', demo)
    saveRecipeFeedback(recipe.id, 'unclear-steps', demo)
    check('反馈可更新且绑定食谱版本', loadRecipeFeedback(recipe.id)?.kind === 'unclear-steps' && loadRecipeFeedback(recipe.id)?.version === recipe.version)
    check('非法反馈拒绝写入', throws(() => saveRecipeFeedback(recipe.id, 'invalid' as 'helpful', demo)))
    recipe.version = 'm5-new-version'
    check('收藏显示版本更新', loadSavedRecipes('favorites', demo)[0].versionChanged)
    check('旧反馈保留原版本', loadRecipeFeedback(recipe.id)?.version === originalRecipe.version)
    recipe.reviewStatus = 'disabled'
    check('停用收藏保留并标记不可用', !loadSavedRecipes('favorites', demo)[0].available && loadSavedRecipes('favorites', demo)[0].statusLabel === '内容已停用')
    check('停用内容拒绝新增浏览和反馈', throws(() => recordRecipeView(recipe.id, demo)) && throws(() => saveRecipeFeedback(recipe.id, 'helpful', demo)))
    check('今日推荐过滤停用内容', !rank().recipes.some((item) => item.id === recipe.id))
    const pantry = matchPantryRecipes({ ingredients: ['小米', '山药'], tools: ['汤锅', '菜刀'], maxMinutes: 30, targetServings: 1, maxAdditionalIngredients: 0 }, profile, demo)
    check('食材匹配过滤停用内容', !pantry.matches.some((item) => item.recipe.id === recipe.id))
    setFavorite(recipe.id, false)
    check('停用收藏仍可移除', !isFavorite(recipe.id))
    recipe.reviewStatus = 'draft'
    check('草稿拒绝查看和收藏', !isContentAvailable(recipe, demo) && throws(() => setFavorite(recipe.id, true, demo)))
    Object.assign(recipe, originalRecipe)
    setFavorite(recipe.id, true, demo)
    check('正式模式拒绝DEMO收藏及推荐', !loadSavedRecipes('favorites')[0].available && rank(false).recipes.length === 0 && !rank(false).bundle)
    check('正式模式拒绝DEMO写入', throws(() => setFavorite(recipe.id, true)) && throws(() => recordRecipeView(recipe.id)))
    check('approved但仍为DEMO不能放行', !isContentAvailable({ ...recipe, reviewStatus: 'approved' }, demo))
    check('正式审核内容可用', isContentAvailable({ ...recipe, reviewStatus: 'approved', isDemo: false }))
    bundle.reviewStatus = 'disabled'
    check('停用节庆内容包不再展示', !rank().bundle)
    Object.assign(bundle, originalBundle)

    const snapshot = { recipeId: 'removed', name: '历史食谱', version: 'v1', updatedAt: profile.updatedAt }
    storage.set(key, { favorites: [null, snapshot, snapshot, { recipeId: 'bad' }], recent: 'corrupt', feedback: [] })
    check('损坏记录过滤且重复去重', loadSavedRecipes('favorites', demo).length === 1 && loadSavedRecipes('recent', demo).length === 0)
    check('已删除内容保留名称并标记不可用', loadSavedRecipes('favorites', demo)[0].name === '历史食谱' && !loadSavedRecipes('favorites', demo)[0].available)

    clearEngagement()
    for (let index = 0; index < 51; index++) {
      const fixture: RecipeTemplate = { ...originalRecipe, id: `m5-limit-${index}` }
      m2RecipeLibrary.push(fixture)
      recordRecipeView(fixture.id, demo)
      saveRecipeFeedback(fixture.id, 'helpful', demo)
      if (index < 50) setFavorite(fixture.id, true, demo)
    }
    check('浏览上限20且最近项置顶', loadSavedRecipes('recent', demo).length === engagementLimits.recent && loadSavedRecipes('recent', demo)[0].recipeId === 'm5-limit-50')
    check('收藏上限50且不静默丢失', throws(() => setFavorite('m5-limit-50', true, demo)) && loadSavedRecipes('favorites', demo).length === engagementLimits.favorites)
    check('反馈上限50', !loadRecipeFeedback('m5-limit-0') && Boolean(loadRecipeFeedback('m5-limit-50')))
    readFails = true
    check('读取失败返回可用空状态', loadSavedRecipes('favorites', demo).length === 0 && !loadRecipeFeedback(recipe.id))
    check('读取失败禁止覆盖既有记录', throws(() => recordRecipeView(recipe.id, demo)) && throws(() => saveRecipeFeedback(recipe.id, 'helpful', demo)) && throws(() => setFavorite('m5-limit-0', false)))
    readFails = false
    writeFails = true
    check('保存失败向页面报告且无虚假成功', throws(() => recordRecipeView(recipe.id, demo)) && loadSavedRecipes('recent', demo)[0].recipeId === 'm5-limit-50')
    check('删除失败向页面报告', throws(clearEngagement))
    writeFails = false
    storage.set('yunsync:wellness-profile:v2', { allergens: ['大豆'] })
    clearEngagement()
    check('清除只删除收藏浏览反馈并保留安全档案', loadSavedRecipes('favorites', demo).length === 0 && loadSavedRecipes('recent', demo).length === 0 && !loadRecipeFeedback('m5-limit-50') && storage.has('yunsync:wellness-profile:v2'))
  } finally {
    root.uni = previousUni
    Object.assign(recipe, originalRecipe)
    Object.assign(bundle, originalBundle)
    m2RecipeLibrary.splice(originalLength)
  }
  return { milestone: 'M5', checksTotal: checks.length, checksPassed: checks.filter((item) => item.passed).length, passed: checks.every((item) => item.passed), checks }
}
