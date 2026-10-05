import { runtimeConfig } from '../config/runtime'
import { hasApprovedOfflineCalendarBaseline, resolveDemoCalendar } from '../data/m2'
import type { CalendarContext } from '../types/domain'

export interface CalendarAdapter {
  getToday(): Promise<CalendarContext>
  getDate(input?: Date | string): Promise<CalendarContext>
}

export class DemoCalendarAdapter implements CalendarAdapter {
  async getToday(): Promise<CalendarContext> {
    return this.getDate()
  }

  async getDate(input?: Date | string): Promise<CalendarContext> {
    return resolveDemoCalendar(input)
  }
}

const lunarMonths: Record<string, number> = {
  正月: 1, 二月: 2, 三月: 3, 四月: 4, 五月: 5, 六月: 6,
  七月: 7, 八月: 8, 九月: 9, 十月: 10, 十一月: 11, 十二月: 12,
}
const lunarDays = ['初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十', '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十', '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十']

function parseLunarDate(label: string) {
  const monthLabel = Object.keys(lunarMonths).find((item) => label.startsWith(item))
  if (!monthLabel) return {}
  const dayLabel = label.slice(monthLabel.length)
  const day = lunarDays.indexOf(dayLabel) + 1
  return { month: lunarMonths[monthLabel], day: day > 0 ? day : undefined }
}

export class HkoCalendarAdapter implements CalendarAdapter {
  async getToday(): Promise<CalendarContext> {
    return this.getDate()
  }

  async getDate(input?: Date | string): Promise<CalendarContext> {
    const fallback = resolveDemoCalendar(input)
    const dateKey = fallback.dateKey
    try {
      const response = await uni.request({
        url: `https://data.weather.gov.hk/weatherAPI/opendata/lunardate.php?date=${dateKey}`,
        method: 'GET',
        timeout: 5000,
      })
      const data = response.data as { LunarYear?: string; LunarDate?: string }
      if (response.statusCode !== 200 || !data.LunarDate) throw new Error('HKO lunar API unavailable')
      const lunar = parseLunarDate(data.LunarDate)
      return {
        ...fallback,
        lunarYear: data.LunarYear,
        lunarMonth: lunar.month,
        lunarDay: lunar.day,
        lunarDate: data.LunarDate,
        source: '香港天文台公历与农历日期对照开放API',
        isDemo: false,
        version: 'hko-lunar-api-v1',
        reviewStatus: 'approved',
        updatedAt: new Date().toISOString(),
      }
    } catch {
      const approvedOffline = hasApprovedOfflineCalendarBaseline()
      return {
        ...fallback,
        lunarDate: fallback.lunarDate || '农历服务暂不可用',
        source: `${fallback.source}（官方API不可用时的已校验离线降级）`,
        isDemo: !approvedOffline,
        reviewStatus: approvedOffline ? 'approved' : 'draft',
      }
    }
  }
}

export function createCalendarAdapter(): CalendarAdapter {
  return runtimeConfig.dataMode === 'real' ? new HkoCalendarAdapter() : new DemoCalendarAdapter()
}
