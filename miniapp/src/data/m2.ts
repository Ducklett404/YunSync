import rawContent from './m2-content.json'
import { isContentAvailable } from '../services/content'
import type { ContentOptions } from '../services/content'
import type {
  CalendarContext,
  FestivalContentBundle,
  M2AcceptanceDateScenario,
  RecipeTemplate,
  RegionTag,
} from '../types/domain'

interface LunarMonthStart {
  date: string
  month: number
}

interface SolarTermFixture {
  date: string
  name: string
  time: string
}

interface M2ContentData {
  schemaVersion: string
  calendarSource: {
    authority: string
    conversionUrl: string
    solarTermsUrl: string
    verifiedAt: string
  }
  lunarMonthStarts2026: LunarMonthStart[]
  solarTerms2026: SolarTermFixture[]
  bundles: FestivalContentBundle[]
  recipes: RecipeTemplate[]
}

const content = rawContent as unknown as M2ContentData
const dayMilliseconds = 24 * 60 * 60 * 1000
const monthNames = ['', '正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月']
const dayNames = ['', '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十', '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十', '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十']
const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const cityRegions: Record<string, RegionTag> = {
  杭州: '江南',
  北京: '华北',
  广州: '华南',
  成都: '西南',
  哈尔滨: '东北',
}

export function getCityRegion(city: string): RegionTag | undefined {
  return cityRegions[city]
}

export const m2AcceptanceDates: Record<M2AcceptanceDateScenario, string | undefined> = {
  today: undefined,
  laba: '2026-01-26',
  'spring-festival': '2026-02-17',
  duanwu: '2026-06-19',
  'mid-autumn': '2026-09-25',
  lichun: '2026-02-04',
  qingming: '2026-04-05',
  bailu: '2026-09-07',
  dongzhi: '2026-12-22',
}

export const m2AcceptanceDateLabels: Record<M2AcceptanceDateScenario, string> = {
  today: '今天',
  laba: '腊八',
  'spring-festival': '春节',
  duanwu: '端午',
  'mid-autumn': '中秋',
  lichun: '立春',
  qingming: '清明',
  bailu: '白露',
  dongzhi: '冬至',
}

function asDateKey(input?: Date | string): string {
  if (typeof input === 'string') return input.slice(0, 10)
  const date = input || new Date()
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function asUtcDay(dateKey: string): number {
  const [year, month, day] = dateKey.split('-').map(Number)
  return Date.UTC(year, month - 1, day)
}

function resolveLunar2026(dateKey: string) {
  const starts = content.lunarMonthStarts2026
  const start = [...starts].reverse().find((item) => item.date <= dateKey)
  if (!start || dateKey < '2026-01-01' || dateKey > '2026-12-31') return undefined
  const day = Math.round((asUtcDay(dateKey) - asUtcDay(start.date)) / dayMilliseconds) + 1
  if (day < 1 || day > 30) return undefined
  return {
    year: dateKey < '2026-02-17' ? '乙巳年，蛇' : '丙午年，马',
    month: start.month,
    day,
    label: `${monthNames[start.month]}${dayNames[day]}`,
  }
}

function resolveFestival(lunarMonth?: number, lunarDay?: number): string | undefined {
  if (lunarMonth === 12 && lunarDay === 8) return '腊八节'
  if (lunarMonth === 1 && lunarDay === 1) return '春节'
  if (lunarMonth === 5 && lunarDay === 5) return '端午节'
  if (lunarMonth === 8 && lunarDay === 15) return '中秋节'
  return undefined
}

export function resolveDemoCalendar(input?: Date | string): CalendarContext {
  const dateKey = asDateKey(input)
  const [year, month, day] = dateKey.split('-').map(Number)
  const lunar = resolveLunar2026(dateKey)
  const solarTerm = content.solarTerms2026.find((item) => item.date === dateKey)
  const date = new Date(year, month - 1, day)
  return {
    dateKey,
    gregorianDate: `${year}年${month}月${day}日`,
    weekday: weekdays[date.getDay()],
    lunarYear: lunar?.year,
    lunarMonth: lunar?.month,
    lunarDay: lunar?.day,
    lunarDate: lunar?.label || '农历日期待官方服务返回',
    solarTerm: solarTerm?.name,
    solarTermTime: solarTerm?.time,
    festival: resolveFestival(lunar?.month, lunar?.day),
    source: `${content.calendarSource.authority}2026公历农历对照表与二十四节气数据`,
    isDemo: true,
    version: content.schemaVersion,
    reviewStatus: 'demo',
    updatedAt: content.calendarSource.verifiedAt,
  }
}

export const festivalContentBundles = content.bundles
export const m2RecipeLibrary = content.recipes

export function getRecipeById(recipeId: string): RecipeTemplate | undefined {
  return m2RecipeLibrary.find((recipe) => recipe.id === recipeId)
}

export function getContentBundle(calendar: CalendarContext, city?: string, options: ContentOptions = {}): FestivalContentBundle | undefined {
  const region = city ? cityRegions[city] : undefined
  return festivalContentBundles.find((bundle) => {
    if (!isContentAvailable(bundle, options)) return false
    const rule = bundle.dateRule
    const dateMatches = rule.kind === 'lunar'
      ? calendar.lunarMonth === rule.lunarMonth && calendar.lunarDay === rule.lunarDay
      : calendar.solarTerm === rule.solarTerm
    const regionMatches = !region || bundle.regions.includes('全国') || bundle.regions.includes(region)
    return dateMatches && regionMatches
  })
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[\s、,，/]/g, '')
}

export function recipeConflictsWith(recipe: RecipeTemplate, restrictions: string[]): boolean {
  if (!restrictions.length) return false
  const recipeTerms = [
    ...recipe.allergens,
    ...recipe.exclusions,
    ...recipe.ingredients.flatMap((ingredient) => [ingredient.name, ...ingredient.allergenTags]),
  ].map(normalize)
  return restrictions.some((restriction) => {
    const needle = normalize(restriction).replace(/过敏|不耐受|忌口|不能吃|禁食|忌|限制|避免|不吃|少吃/g, '')
    return Boolean(needle) && recipeTerms.some((term) => term.includes(needle) || needle.includes(term))
  })
}

export function selectM2Recommendations(
  calendar: CalendarContext,
  city: string,
  restrictions: string[] = [],
) {
  const bundle = getContentBundle(calendar, city, { allowDemoContent: true })
  const preferredIds = bundle?.recipeIds || []
  const fallbackIds = ['demo-yam-millet', 'demo-tomato-tofu', 'demo-greens']
  const orderedIds = [...preferredIds, ...fallbackIds]
  const recipes = orderedIds
    .filter((id, index) => orderedIds.indexOf(id) === index)
    .map(getRecipeById)
    .filter((recipe): recipe is RecipeTemplate => Boolean(recipe))
    .filter((recipe) => isContentAvailable(recipe, { allowDemoContent: true }))
    .filter((recipe) => !recipeConflictsWith(recipe, restrictions))
    .slice(0, 3)
  return { bundle, recipes }
}
