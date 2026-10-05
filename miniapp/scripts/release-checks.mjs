const requiredConfig = [
  'YUNSYNC_MINIAPP_APPID', 'VITE_YUNSYNC_LEGAL_ENTITY', 'VITE_YUNSYNC_PRIVACY_CONTACT',
  'VITE_YUNSYNC_PRIVACY_NOTICE_VERSION', 'VITE_YUNSYNC_WEATHER_PROVIDER',
  'VITE_YUNSYNC_WEATHER_ENDPOINT', 'YUNSYNC_CONTENT_SIGNOFF_VERSION',
  'VITE_YUNSYNC_SURVEY_ENABLED', 'YUNSYNC_SURVEY_LICENSE_VERSION',
]
const demoOrPlaceholder = /demo|演示|测试|待填写|待提供|placeholder|example|test-app|测试号/i

export function isProductionWeatherEndpoint(value) {
  try {
    const url = new URL(value)
    const secretNames = /^(key|token|secret|password|api_?key|authorization)$/i
    return url.protocol === 'https:' && !url.username && !url.password
      && !['localhost', '127.0.0.1', '0.0.0.0'].includes(url.hostname)
      && ![...url.searchParams.keys()].some(name => secretNames.test(name))
  } catch {
    return false
  }
}

export function checkProductionData({ env, content, survey, manifest, weatherReady }) {
  const errors = []
  for (const key of requiredConfig) {
    const value = env[key]?.trim()
    if (!value || demoOrPlaceholder.test(value)) errors.push(`${key}: missing or placeholder value`)
  }
  if (env.VITE_DATA_MODE !== 'real') errors.push('VITE_DATA_MODE must equal real')
  if (env.VITE_YUNSYNC_SURVEY_ENABLED !== 'true') errors.push('The authorized constitution survey must be enabled for formal release')
  if (!/^wx[0-9a-f]{16}$/.test(env.YUNSYNC_MINIAPP_APPID || '')) errors.push('AppID must be a WeChat AppID')
  if (manifest?.['mp-weixin']?.appid !== env.YUNSYNC_MINIAPP_APPID) errors.push('Configured AppID differs from the built manifest')
  if (manifest?.['mp-weixin']?.setting?.urlCheck !== true) errors.push('WeChat request-domain validation must be enabled')
  const endpointReady = isProductionWeatherEndpoint(env.VITE_YUNSYNC_WEATHER_ENDPOINT || '')
  if (weatherReady === false || !endpointReady) errors.push('A credential-free HTTPS weather proxy endpoint is required')

  const recipes = Array.isArray(content?.recipes) ? content.recipes : []
  const bundles = Array.isArray(content?.bundles) ? content.bundles : []
  const calendar = content?.calendarSource || {}
  if (!calendar.authority?.trim() || !/^https:\/\//.test(calendar.conversionUrl || '') || !/^https:\/\//.test(calendar.solarTermsUrl || '') || !Number.isFinite(Date.parse(calendar.verifiedAt))) errors.push('Formal calendar source and verification metadata are incomplete')
  if (!Array.isArray(content?.lunarMonthStarts2026) || content.lunarMonthStarts2026.length < 12) errors.push('Formal lunar offline baseline is incomplete')
  if (!Array.isArray(content?.solarTerms2026) || content.solarTerms2026.length !== 24) errors.push('Formal solar-term offline baseline must contain 24 entries')
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
    if (recipe.version !== env.YUNSYNC_CONTENT_SIGNOFF_VERSION) errors.push(`${recipe.id}: recipe version differs from the signed content version`)
  }
  const quota = { '粥': 12, '汤': 12, '菜': 16, '节庆食品': 8 }
  for (const [category, count] of Object.entries(quota)) {
    const available = active.filter(item => item.category === category && approved(item)).length
    if (available !== count) errors.push(`${category}: ${available}/${count} signed recipes (frozen launch quota)`)
  }
  if (active.length !== 48) errors.push(`Formal recipe library must contain exactly 48 active recipes; found ${active.length}`)
  if (content?.schemaVersion !== env.YUNSYNC_CONTENT_SIGNOFF_VERSION) errors.push('Content library version differs from the signed content version')
  if (bundles.filter(approved).length < 8) errors.push('Fewer than eight approved festival/solar-term bundles')
  for (const bundle of bundles.filter(item => item?.reviewStatus !== 'disabled')) {
    if (!Array.isArray(bundle.recipeIds) || !bundle.recipeIds.length || bundle.recipeIds.some(id => !active.some(recipe => recipe.id === id && approved(recipe)))) errors.push(`${bundle.id}: bundle references unavailable recipes`)
    if (bundle.version !== env.YUNSYNC_CONTENT_SIGNOFF_VERSION) errors.push(`${bundle.id}: bundle version differs from the signed content version`)
  }

  if (survey?.reviewStatus !== 'approved' || survey?.isDemo !== false) errors.push('Constitution survey is not formally approved')
  if (survey?.licenseVersion !== env.YUNSYNC_SURVEY_LICENSE_VERSION) errors.push('Survey license version differs from the configured authorization')
  for (const field of ['source', 'reviewer', 'version']) {
    if (!survey?.[field]?.trim() || demoOrPlaceholder.test(survey[field])) errors.push(`Survey ${field} is missing or placeholder`)
  }
  if (!Number.isFinite(Date.parse(survey?.updatedAt))) errors.push('Survey review timestamp is missing')
  const outcomes = Array.isArray(survey?.outcomes) ? survey.outcomes : []
  const outcomeIds = new Set(outcomes.map(item => item?.id))
  if (!outcomes.length || outcomes.some(item => !item?.id?.trim() || !item?.label?.trim() || !item?.description?.trim() || !Array.isArray(item?.recommendationTags) || !item.recommendationTags.length || item.recommendationTags.some(tag => !tag?.trim()))) errors.push('Survey outcomes are incomplete')
  const questions = Array.isArray(survey?.questions) ? survey.questions : []
  if (!questions.length) errors.push('Authorized survey question bank is empty')
  for (const question of questions) {
    if (!question?.id?.trim() || !question?.prompt?.trim() || !Array.isArray(question?.options) || question.options.length < 2) {
      errors.push('Survey question or options are incomplete')
      continue
    }
    for (const option of question.options) {
      const scores = option?.scores && typeof option.scores === 'object' ? Object.entries(option.scores) : []
      if (!option?.id?.trim() || !option?.label?.trim() || !scores.length || scores.some(([id, score]) => !outcomeIds.has(id) || !Number.isFinite(score))) errors.push(`${question.id}: survey option scoring is invalid`)
    }
  }
  return { passed: errors.length === 0, errors }
}
