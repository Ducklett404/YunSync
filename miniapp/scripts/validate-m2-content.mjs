import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir = path.dirname(fileURLToPath(import.meta.url))
const contentPath = path.resolve(currentDir, '../src/data/m2-content.json')
const content = JSON.parse(fs.readFileSync(contentPath, 'utf8'))
const errors = []

function check(condition, message) {
  if (!condition) errors.push(message)
}

const expectedFixtures = {
  'm2-laba': '2026-01-26',
  'm2-spring-festival': '2026-02-17',
  'm2-duanwu': '2026-06-19',
  'm2-mid-autumn': '2026-09-25',
  'm2-lichun': '2026-02-04',
  'm2-qingming': '2026-04-05',
  'm2-bailu': '2026-09-07',
  'm2-dongzhi': '2026-12-22',
}

const recipeById = new Map(content.recipes.map((recipe) => [recipe.id, recipe]))
check(content.bundles.length === 8, `内容包应为 8 个，实际 ${content.bundles.length}`)
check(content.solarTerms2026.length === 24, `节气应为 24 个，实际 ${content.solarTerms2026.length}`)
check(content.lunarMonthStarts2026.length === 13, '2026 农历月起点不完整')

for (const bundle of content.bundles) {
  check(bundle.dateRule?.gregorianFixtures?.['2026'] === expectedFixtures[bundle.id], `${bundle.id} 的 2026 日期不正确`)
  check(Boolean(bundle.cultureNote), `${bundle.id} 缺少文化说明`)
  check(Array.isArray(bundle.regions) && bundle.regions.length > 0, `${bundle.id} 缺少地域标签`)
  check(Array.isArray(bundle.recipeIds) && bundle.recipeIds.length > 0, `${bundle.id} 缺少食谱引用`)
  for (const recipeId of bundle.recipeIds) check(recipeById.has(recipeId), `${bundle.id} 引用了不存在的食谱 ${recipeId}`)
  check(bundle.isDemo === true && bundle.reviewStatus === 'demo', `${bundle.id} 未正确标记为 DEMO`)
}

const requiredRecipeFields = [
  'id', 'name', 'category', 'minutes', 'tags', 'reason', 'servings', 'ingredients', 'tools', 'steps',
  'substitutions', 'allergens', 'exclusions', 'regions', 'sceneTags', 'sourceNote', 'source', 'version',
  'reviewStatus', 'updatedAt',
]

for (const recipe of content.recipes) {
  for (const field of requiredRecipeFields) {
    const value = recipe[field]
    check(value !== undefined && value !== null && value !== '', `${recipe.id} 缺少字段 ${field}`)
  }
  check(Number.isInteger(recipe.servings) && recipe.servings > 0, `${recipe.id} 份数无效`)
  check(Number.isInteger(recipe.minutes) && recipe.minutes > 0, `${recipe.id} 时间无效`)
  check(Array.isArray(recipe.ingredients) && recipe.ingredients.length > 0, `${recipe.id} 食材为空`)
  for (const ingredient of recipe.ingredients || []) {
    check(Boolean(ingredient.name) && Boolean(ingredient.amount), `${recipe.id} 存在不完整食材`)
    check(Array.isArray(ingredient.allergenTags), `${recipe.id}/${ingredient.name} 缺少过敏原数组`)
  }
  check(Array.isArray(recipe.tools) && recipe.tools.length > 0, `${recipe.id} 厨具为空`)
  check(Array.isArray(recipe.steps) && recipe.steps.length >= 4 && recipe.steps.length <= 8, `${recipe.id} 步骤数不在 4-8`)
  check(recipe.steps?.every((step, index) => step.order === index + 1 && Boolean(step.action)), `${recipe.id} 步骤顺序或动作不完整`)
  check(recipe.isDemo === true && recipe.reviewStatus === 'demo', `${recipe.id} 未正确标记为 DEMO`)
}

for (const category of ['粥', '汤', '菜', '节庆食品']) {
  check(content.recipes.some((recipe) => recipe.category === category), `缺少 ${category} 类示例`)
}

function normalize(value) {
  return value.toLowerCase().replace(/[\s、,，/]/g, '')
}

function conflicts(recipe, restriction) {
  const needle = normalize(restriction).replace(/过敏|不耐受|忌口|不能吃|禁食/g, '')
  const terms = [
    ...recipe.allergens,
    ...recipe.exclusions,
    ...recipe.ingredients.flatMap((item) => [item.name, ...item.allergenTags]),
  ].map(normalize)
  return terms.some((term) => term.includes(needle) || needle.includes(term))
}

const laba = content.bundles.find((bundle) => bundle.id === 'm2-laba')
const safeLabaRecipeIds = laba.recipeIds.filter((id) => !conflicts(recipeById.get(id), '蒜不耐受'))
check(!safeLabaRecipeIds.includes('m2-laba-garlic'), '蒜不耐受时未排除腊八蒜')
check(safeLabaRecipeIds.includes('m2-laba-porridge'), '蒜不耐受时错误排除了腊八粥')

const completenessChecks = content.recipes.length * requiredRecipeFields.length
const report = {
  schemaVersion: content.schemaVersion,
  bundles: content.bundles.length,
  recipes: content.recipes.length,
  solarTerms: content.solarTerms2026.length,
  recipeFieldChecks: completenessChecks,
  fieldCompleteness: errors.some((item) => item.includes('缺少字段')) ? '<100%' : '100%',
  garlicIntoleranceRemaining: safeLabaRecipeIds,
  errors,
}

console.log(JSON.stringify(report, null, 2))
if (errors.length) process.exitCode = 1
