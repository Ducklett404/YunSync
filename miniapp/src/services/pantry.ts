import { m2RecipeLibrary, recipeConflictsWith } from '../data/m2'
import { screenSafety } from './safety'
import { isContentAvailable } from './content'
import type {
  DailyCheckIn,
  PantryMatchKind,
  PantryMatchResult,
  PantryRecipeMatch,
  PantrySession,
  RecipeTemplate,
  WellnessProfile,
} from '../types/domain'

const automaticBasics = ['清水']
const ingredientAliasGroups = [
  ['番茄', '西红柿'],
  ['北豆腐', '嫩豆腐', '豆腐'],
  ['大蒜', '蒜'],
  ['当季绿叶菜', '绿叶菜', '青菜', '时蔬'],
  ['雪梨', '梨'],
  ['白萝卜', '萝卜'],
  ['小麦粉', '面粉'],
  ['红豆沙', '豆沙'],
  ['食用油', '油'],
]
const toolAliasGroups = [
  ['汤锅'], ['大汤锅'], ['炖锅'],
  ['菜刀'], ['炒锅'], ['锅铲'], ['电饭锅'], ['烤箱'], ['烤盘'],
  ['面盆'], ['擀面杖'], ['棉绳'], ['量杯'], ['月饼模具'], ['洁净玻璃容器'],
]

function compact(value: string): string {
  return value.trim().toLowerCase().replace(/[\s，,。.!！?？、]/g, '')
}

function equivalent(left: string, right: string, groups: string[][]): boolean {
  const a = compact(left)
  const b = compact(right)
  if (a === b) return true
  return groups.some((group) => {
    const normalized = group.map(compact)
    return normalized.includes(a) && normalized.includes(b)
  })
}

function pantryHas(values: string[], expected: string): boolean {
  return values.some((value) => equivalent(value, expected, ingredientAliasGroups))
}

export function pantryIngredientsEquivalent(left: string, right: string): boolean {
  return equivalent(left, right, ingredientAliasGroups)
}

function toolsAvailable(selectedTools: string[], requiredTools: string[]): boolean {
  if (!selectedTools.length) return false
  return requiredTools.every((required) => selectedTools.some((owned) => equivalent(owned, required, toolAliasGroups)))
}

function pantrySafetyCheckIn(): DailyCheckIn {
  return { dateKey: 'pantry', feelings: ['正常'], note: '', updatedAt: new Date().toISOString() }
}

export function normalizePantryIngredients(values: string[]): string[] {
  const normalized: string[] = []
  for (const raw of values) {
    const value = raw.trim()
    if (!value) continue
    if (!normalized.some((item) => equivalent(item, value, ingredientAliasGroups))) normalized.push(value)
    if (normalized.length === 15) break
  }
  return normalized
}

function matchRecipe(recipe: RecipeTemplate, session: PantrySession): PantryRecipeMatch | undefined {
  if (recipe.minutes > session.maxMinutes || !toolsAvailable(session.tools, recipe.tools)) return undefined

  const matchedIngredients: string[] = []
  const missingIngredients: string[] = []
  const missingKeyIngredients: string[] = []
  const substitutionsUsed: PantryRecipeMatch['substitutionsUsed'] = []

  for (const ingredient of recipe.ingredients) {
    if (automaticBasics.some((item) => equivalent(item, ingredient.name, ingredientAliasGroups))) {
      continue
    }
    if (pantryHas(session.ingredients, ingredient.name)) {
      matchedIngredients.push(ingredient.name)
      continue
    }

    const substitution = recipe.substitutions.find((item) =>
      equivalent(item.from, ingredient.name, ingredientAliasGroups) && pantryHas(session.ingredients, item.to),
    )
    if (substitution) {
      substitutionsUsed.push({ from: substitution.from, to: substitution.to, note: substitution.note })
      matchedIngredients.push(substitution.to)
      continue
    }

    missingIngredients.push(ingredient.name)
    if (ingredient.isKey) missingKeyIngredients.push(ingredient.name)
  }

  if (missingKeyIngredients.length) return undefined
  if (missingIngredients.length > session.maxAdditionalIngredients) return undefined

  let kind: PantryMatchKind = 'complete'
  if (missingIngredients.length) kind = 'missing'
  else if (substitutionsUsed.length) kind = 'substitution'

  return {
    recipe,
    kind,
    matchedIngredients,
    missingIngredients,
    substitutionsUsed,
    targetServings: session.targetServings,
  }
}

export function matchPantryRecipes(
  request: PantrySession,
  profile: WellnessProfile,
  options: { allowDemoContent?: boolean } = {},
): PantryMatchResult {
  const session = { ...request, ingredients: normalizePantryIngredients(request.ingredients) }
  const safety = screenSafety(profile, pantrySafetyCheckIn())
  if (safety.blocked) {
    return { safety, matches: [], safetyFilteredCount: 0, contentFilteredCount: 0, constraintFilteredCount: 0, message: safety.message }
  }

  if (!session.ingredients.length) {
    return { safety, matches: [], safetyFilteredCount: 0, contentFilteredCount: 0, constraintFilteredCount: 0, message: '请先录入至少 1 种现有食材。' }
  }

  const contentEligible = m2RecipeLibrary.filter((recipe) => isContentAvailable(recipe, options))
  const contentFilteredCount = m2RecipeLibrary.length - contentEligible.length
  const restrictions = [...profile.allergens, ...profile.doctorDietRestrictions]
  const safeRecipes = contentEligible.filter((recipe) => !recipeConflictsWith(recipe, restrictions))
  const safetyFilteredCount = contentEligible.length - safeRecipes.length
  const matches = safeRecipes
    .map((recipe) => matchRecipe(recipe, session))
    .filter((item): item is PantryRecipeMatch => Boolean(item))
    .sort((left, right) => {
      const rank: Record<PantryMatchKind, number> = { complete: 0, substitution: 1, missing: 2 }
      return rank[left.kind] - rank[right.kind]
        || left.missingIngredients.length - right.missingIngredients.length
        || left.recipe.minutes - right.recipe.minutes
        || left.recipe.id.localeCompare(right.recipe.id)
    })

  const constraintFilteredCount = safeRecipes.length - matches.length
  let message = `找到 ${matches.length} 个安全匹配；完全具备材料的结果优先。`
  if (!matches.length && safetyFilteredCount > 0) message = '当前食材可能命中个人过敏或明确禁忌，冲突食谱已全部排除；其余食谱不满足关键材料、厨具或时间条件。'
  else if (!matches.length && session.maxAdditionalIngredients === 0) message = '没有完全匹配。可以增加食材、放宽时间或允许再购买 1—2 种非关键材料。'
  else if (!matches.length) message = '没有安全匹配：现有食材缺少食谱关键材料，或厨具和制作时间不满足；系统不会临时拼出未经审核的配方。'

  return { safety, matches, safetyFilteredCount, contentFilteredCount, constraintFilteredCount, message }
}
