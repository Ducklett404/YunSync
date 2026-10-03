import { m2RecipeLibrary, recipeConflictsWith } from '../src/data/m2'
import { matchPantryRecipes } from '../src/services/pantry'
import type { PantrySession, WellnessProfile } from '../src/types/domain'

interface HouseholdCase {
  name: string
  ingredients: string[]
  tools: string[]
  maxMinutes: number
  maxAdditionalIngredients: 0 | 1 | 2
  expectedId?: string
  expectedKind?: 'complete' | 'substitution' | 'missing'
  allergens?: string[]
}

const baseProfile: WellnessProfile = {
  city: '杭州', ageGroup: '18—39岁', allergens: [], preferences: ['清淡'], medicalConditions: [], medications: [],
  doctorDietRestrictions: [], serviceScope: 'adult', constitutionSurveyInterest: false, updatedAt: '2026-09-29T00:00:00.000Z',
}

const cases: HouseholdCase[] = [
  { name: '鸡蛋+西红柿+豆腐', ingredients: ['鸡蛋', '西红柿', '豆腐', '食用油'], tools: ['汤锅', '菜刀'], maxMinutes: 20, maxAdditionalIngredients: 0, expectedId: 'demo-tomato-tofu', expectedKind: 'complete' },
  { name: '小米+山药', ingredients: ['小米', '山药'], tools: ['汤锅', '菜刀'], maxMinutes: 30, maxAdditionalIngredients: 0, expectedId: 'demo-yam-millet', expectedKind: 'complete' },
  { name: '青菜+食用油', ingredients: ['青菜', '食用油'], tools: ['炒锅', '锅铲'], maxMinutes: 15, maxAdditionalIngredients: 0, expectedId: 'demo-greens', expectedKind: 'complete' },
  { name: '大米+春笋+豌豆', ingredients: ['大米', '春笋', '豌豆'], tools: ['电饭锅', '菜刀'], maxMinutes: 45, maxAdditionalIngredients: 1, expectedId: 'm2-qingming-spring-rice', expectedKind: 'missing' },
  { name: '莲藕+梨', ingredients: ['莲藕', '梨'], tools: ['汤锅', '菜刀'], maxMinutes: 40, maxAdditionalIngredients: 0, expectedId: 'm2-bailu-pear-lotus-soup', expectedKind: 'complete' },
  { name: '牛肉+萝卜', ingredients: ['牛肉', '萝卜'], tools: ['炖锅', '菜刀'], maxMinutes: 90, maxAdditionalIngredients: 0, expectedId: 'm2-dongzhi-radish-beef', expectedKind: 'complete' },
  { name: '面粉+白菜+豆腐', ingredients: ['面粉', '白菜', '豆腐'], tools: ['面盆', '擀面杖', '汤锅'], maxMinutes: 60, maxAdditionalIngredients: 0, expectedId: 'm2-spring-dumpling', expectedKind: 'complete' },
  { name: '蒜+米醋', ingredients: ['蒜', '米醋'], tools: ['洁净玻璃容器'], maxMinutes: 20, maxAdditionalIngredients: 0, expectedId: 'm2-laba-garlic', expectedKind: 'complete' },
  { name: '小米+南瓜（登记替代）', ingredients: ['小米', '南瓜'], tools: ['汤锅', '菜刀'], maxMinutes: 30, maxAdditionalIngredients: 0, expectedId: 'demo-yam-millet', expectedKind: 'substitution' },
  { name: '大豆过敏+西红柿+豆腐', ingredients: ['西红柿', '豆腐', '食用油'], tools: ['汤锅', '菜刀'], maxMinutes: 20, maxAdditionalIngredients: 0, allergens: ['大豆'] },
]

const checks: Array<{ name: string; passed: boolean; detail: string }> = []
const add = (name: string, passed: boolean, detail: string) => checks.push({ name, passed, detail })
const scenarioResults = []

for (const scenario of cases) {
  const session: PantrySession = {
    ingredients: scenario.ingredients,
    tools: scenario.tools,
    maxMinutes: scenario.maxMinutes,
    maxAdditionalIngredients: scenario.maxAdditionalIngredients,
    targetServings: 2,
  }
  const profile = { ...baseProfile, allergens: scenario.allergens || [] }
  const result = matchPantryRecipes(session, profile, { allowDemoContent: true })
  const expected = scenario.expectedId
    ? result.matches.find((item) => item.recipe.id === scenario.expectedId && item.kind === scenario.expectedKind)
    : undefined
  const passed = scenario.expectedId ? Boolean(expected) : result.matches.length === 0 && result.message.length >= 12
  add(`家庭食材：${scenario.name}`, passed, result.matches.length ? result.matches.map((item) => `${item.recipe.id}/${item.kind}`).join(',') : result.message)
  scenarioResults.push({ name: scenario.name, outcome: passed ? 'clear-result' : 'failed', matches: result.matches.length, message: result.message })

  for (const match of result.matches) {
    add(`${scenario.name}：不超过两种非关键缺料`, match.missingIngredients.length <= 2, match.missingIngredients.join('、') || '无缺料')
    add(`${scenario.name}：来源为模板`, m2RecipeLibrary.some((recipe) => recipe.id === match.recipe.id), match.recipe.id)
    add(`${scenario.name}：无过敏冲突`, !recipeConflictsWith(match.recipe, profile.allergens), match.recipe.id)
    const substitutionsRegistered = match.substitutionsUsed.every((used) =>
      match.recipe.substitutions.some((registered) => registered.from === used.from && registered.to === used.to),
    )
    add(`${scenario.name}：替代关系已登记`, substitutionsRegistered, match.substitutionsUsed.map((item) => `${item.from}->${item.to}`).join(',') || '未使用替代')
  }
}

const sixteenIngredients = Array.from({ length: 16 }, (_, index) => `食材${index + 1}`)
const limitResult = matchPantryRecipes({ ingredients: sixteenIngredients, tools: ['汤锅'], maxMinutes: 180, targetServings: 1, maxAdditionalIngredients: 2 }, baseProfile, { allowDemoContent: true })
add('输入上限由引擎截断为15种', limitResult.matches.length === 0 && limitResult.message.length > 0, limitResult.message)

const productionResult = matchPantryRecipes({ ingredients: ['小米', '山药'], tools: ['汤锅', '菜刀'], maxMinutes: 30, targetServings: 1, maxAdditionalIngredients: 0 }, baseProfile)
add('生产模式拒绝DEMO模板', productionResult.matches.length === 0 && productionResult.contentFilteredCount === m2RecipeLibrary.length, `过滤 ${productionResult.contentFilteredCount} 条`)

const keyMetadataComplete = m2RecipeLibrary.every((recipe) => recipe.ingredients.every((ingredient) => typeof ingredient.isKey === 'boolean'))
add('关键食材元数据完整', keyMetadataComplete, `${m2RecipeLibrary.flatMap((recipe) => recipe.ingredients).length} 项食材`)

export function runM4Validation() {
  const householdPassed = checks.filter((item) => item.name.startsWith('家庭食材：') && item.passed).length
  return {
    milestone: 'M4', householdCases: cases.length, householdPassed,
    passed: householdPassed === 10 && checks.every((item) => item.passed),
    scenarioResults, checks,
  }
}
