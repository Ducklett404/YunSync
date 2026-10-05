import { ProductionWeatherAdapter } from '../src/adapters/weather'
import { m2RecipeLibrary } from '../src/data/m2'
import { buildLocalDataExport, deleteAllLocalData } from '../src/services/privacy'
import { weatherFitScore } from '../src/services/recommendation'
import { evaluateConstitutionSurvey } from '../src/services/constitution'
import type { ConstitutionSurveyDefinition } from '../src/services/constitution'

export async function runM6RuntimeValidation() {
  const checks: Array<{ name: string; passed: boolean }> = []
  const check = (name: string, passed: boolean) => checks.push({ name, passed })
  const storage = new Map<string, unknown>()
  const root = globalThis as unknown as { uni: unknown }
  const previousUni = root.uni
  let requestCount = 0
  let requestFails = false
  let now = Date.parse('2026-10-05T00:00:00Z')
  root.uni = {
    getStorageSync: (key: string) => storage.get(key),
    setStorageSync: (key: string, value: unknown) => storage.set(key, structuredClone(value)),
    removeStorageSync: (key: string) => storage.delete(key),
    getStorageInfoSync: () => ({ keys: [...storage.keys()] }),
    request: (options: { success: (value: unknown) => void; fail: (error: unknown) => void }) => {
      requestCount++
      if (requestFails) options.fail(new Error('network unavailable'))
      else options.success({
        statusCode: 200,
        data: { city: '杭州', temperature: 8, feelsLike: 6, humidity: 52, precipitation: 1.2, minTemperature: 4, maxTemperature: 14, text: '小雨', observedAt: '2026-10-05T00:00:00Z', source: 'fixture-weather', version: 'v1' },
      })
    },
  }
  try {
    const adapter = new ProductionWeatherAdapter({
      endpoint: 'https://weather.invalid/v1/city', provider: 'fixture-provider', timeoutMs: 1000,
      cacheTtlMs: 30 * 60 * 1000, staleTtlMs: 6 * 60 * 60 * 1000, now: () => now,
    })
    const live = await adapter.getCityWeather('杭州')
    check('正式天气响应被规范化并缓存', live.available && !live.isDemo && live.delivery === 'live' && live.temperature === 8)
    now += 10 * 60 * 1000
    const fresh = await adapter.getCityWeather('杭州')
    check('缓存有效期内不重复请求天气服务', fresh.delivery === 'fresh-cache' && requestCount === 1)
    now += 31 * 60 * 1000
    requestFails = true
    const stale = await adapter.getCityWeather('杭州')
    check('天气故障时使用限时旧缓存', stale.available && stale.delivery === 'stale-cache' && stale.text.includes('缓存'))
    now += 7 * 60 * 60 * 1000
    const fallback = await adapter.getCityWeather('杭州')
    check('旧缓存过期后回退季节通用内容', !fallback.available && fallback.delivery === 'fallback' && !fallback.isDemo)
    const soup = m2RecipeLibrary.find(recipe => recipe.category === '汤')!
    const dish = m2RecipeLibrary.find(recipe => recipe.category === '菜')!
    check('低温降水实际参与食谱排序', weatherFitScore(soup, live) > weatherFitScore(dish, live))

    const survey: ConstitutionSurveyDefinition = {
      source: 'fixture', licenseVersion: 'licensed-v1', reviewer: 'fixture-reviewer', isDemo: false,
      version: 'survey-v1', reviewStatus: 'approved', updatedAt: '2026-10-05T00:00:00Z',
      outcomes: [
        { id: 'cold', label: '偏寒感受较多', description: '谨慎参考说明', recommendationTags: ['温热'] },
        { id: 'dry', label: '近期易燥', description: '谨慎参考说明', recommendationTags: ['清淡'] },
      ],
      questions: [{ id: 'q1', prompt: 'fixture', options: [{ id: 'a', label: 'A', scores: { cold: 2, dry: 0 } }, { id: 'b', label: 'B', scores: { cold: 0, dry: 2 } }] }],
    }
    const surveyResult = evaluateConstitutionSurvey(survey, { q1: 'a' }, new Date('2026-10-05T08:00:00Z'))
    check('授权问卷按结构化分值生成谨慎参考', surveyResult.labels[0] === '偏寒感受较多' && surveyResult.recommendationTags[0] === '温热' && surveyResult.surveyVersion === 'survey-v1')

    storage.set('unrelated:key', { keep: true })
    storage.set('yunsync:wellness-profile:v2', { city: '杭州', allergens: ['花生'] })
    storage.set('yunsync:daily-checkin:v1:2026-10-05', { feelings: ['正常'] })
    const exported = buildLocalDataExport(new Date('2026-10-05T08:00:00Z'))
    check('隐私导出只包含本产品本机数据', exported.keys.length >= 2 && !exported.keys.includes('unrelated:key') && Boolean(exported.data['yunsync:wellness-profile:v2']))
    const deletion = deleteAllLocalData()
    check('撤回删除覆盖档案体感和天气缓存', deletion.deletedKeys.length >= 2 && [...storage.keys()].every(key => !key.startsWith('yunsync:')) && storage.has('unrelated:key'))
  } finally {
    root.uni = previousUni
  }
  return { milestone: 'M6-runtime', checks, passed: checks.every(item => item.passed) }
}
