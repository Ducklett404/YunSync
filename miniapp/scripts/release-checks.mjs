const requiredConfig = [
  'YUNSYNC_MINIAPP_APPID', 'YUNSYNC_LEGAL_ENTITY', 'YUNSYNC_PRIVACY_CONTACT',
  'YUNSYNC_WEATHER_PROVIDER', 'YUNSYNC_CONTENT_SIGNOFF_VERSION',
]
const demoOrPlaceholder = /demo|演示|测试|待填写|待提供|placeholder|example|test-app|测试号/i

export function checkProductionData({ env, content, manifest, weatherReady = false }) {
  const errors = []
  for (const key of requiredConfig) {
    const value = env[key]?.trim()
    if (!value || demoOrPlaceholder.test(value)) errors.push(`${key}: missing or placeholder value`)
  }
  if (env.VITE_DATA_MODE !== 'real') errors.push('VITE_DATA_MODE must equal real')
  if (!/^wx[0-9a-f]{16}$/.test(env.YUNSYNC_MINIAPP_APPID || '')) errors.push('AppID must be a WeChat AppID')
  if (manifest?.['mp-weixin']?.appid !== env.YUNSYNC_MINIAPP_APPID) errors.push('Configured AppID differs from the built manifest')
  if (manifest?.['mp-weixin']?.setting?.urlCheck !== true) errors.push('WeChat request-domain validation must be enabled')
  if (!weatherReady) errors.push('Real weather adapter is not configured; the current demo adapter cannot release')

  const recipes = Array.isArray(content?.recipes) ? content.recipes : []
  const bundles = Array.isArray(content?.bundles) ? content.bundles : []
  const approved = item => item?.reviewStatus === 'approved' && item?.isDemo === false
  const active = recipes.filter(item => item?.reviewStatus !== 'disabled')
  for (const item of [...active, ...bundles.filter(item => item?.reviewStatus !== 'disabled')]) {
    if (!approved(item)) errors.push(`${item?.id || 'unknown'}: active content is not formally approved`)
    if (!item?.source?.trim() || demoOrPlaceholder.test(item.source)) errors.push(`${item?.id || 'unknown'}: missing formal source`)
    if (!item?.version?.trim() || demoOrPlaceholder.test(item.version)) errors.push(`${item?.id || 'unknown'}: missing formal version`)
    if (!Number.isFinite(Date.parse(item?.updatedAt))) errors.push(`${item?.id || 'unknown'}: missing content timestamp`)
  }
  const ids = new Set()
  for (const recipe of active) {
    if (!recipe.id || ids.has(recipe.id)) errors.push('Recipe IDs must be nonempty and unique')
    ids.add(recipe.id)
    if (!recipe.reviewer?.trim() || demoOrPlaceholder.test(recipe.reviewer)) errors.push(`${recipe.id}: missing professional reviewer`)
    if (!recipe.sourceNote?.trim() || demoOrPlaceholder.test(recipe.sourceNote)) errors.push(`${recipe.id}: missing signed recipe source note`)
    if (!recipe.name?.trim() || !Number.isFinite(recipe.minutes) || recipe.minutes <= 0 || !Number.isFinite(recipe.servings) || recipe.servings <= 0) errors.push(`${recipe.id}: incomplete recipe basics`)
    if (!Array.isArray(recipe.tools) || !recipe.tools.length || !Array.isArray(recipe.ingredients) || !recipe.ingredients.length || !Array.isArray(recipe.steps) || !recipe.steps.length) errors.push(`${recipe.id}: incomplete ingredients, tools or steps`)
    if (Array.isArray(recipe.ingredients) && recipe.ingredients.some(item => !item.name?.trim() || !item.amount?.trim() || typeof item.isKey !== 'boolean' || !Array.isArray(item.allergenTags))) errors.push(`${recipe.id}: incomplete ingredient metadata`)
    if (Array.isArray(recipe.steps) && recipe.steps.some((item, index) => item.order !== index + 1 || !item.action?.trim())) errors.push(`${recipe.id}: incomplete recipe steps`)
    if (!Array.isArray(recipe.allergens) || !Array.isArray(recipe.exclusions) || !Array.isArray(recipe.substitutions)) errors.push(`${recipe.id}: missing safety or substitution fields`)
  }
  const quota = { '粥': 12, '汤': 12, '菜': 16, '节庆食品': 8 }
  for (const [category, count] of Object.entries(quota)) {
    const available = active.filter(item => item.category === category && approved(item)).length
    if (available < count) errors.push(`${category}: ${available}/${count} signed recipes (frozen launch quota)`)
  }
  if (bundles.filter(approved).length < 8) errors.push('Fewer than eight approved festival/solar-term bundles')
  for (const bundle of bundles.filter(item => item?.reviewStatus !== 'disabled')) {
    if (!Array.isArray(bundle.recipeIds) || !bundle.recipeIds.length || bundle.recipeIds.some(id => !active.some(recipe => recipe.id === id && approved(recipe)))) errors.push(`${bundle.id}: bundle references unavailable recipes`)
  }
  return { passed: errors.length === 0, errors }
}
