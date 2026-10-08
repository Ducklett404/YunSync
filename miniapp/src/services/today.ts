import { createCalendarAdapter } from '../adapters/calendar'
import { createWeatherAdapter } from '../adapters/weather'
import { cloudApiEnabled, requestCloudToday } from '../adapters/cloud'
import { rankM3Recommendations } from './recommendation'
import { screenSafety } from './safety'
import { runtimeConfig } from '../config/runtime'
import type {
  DailyCheckIn,
  M1AcceptanceScenario,
  TodayExperienceResult,
  WeatherSnapshot,
  WellnessProfile,
} from '../types/domain'

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function unavailableWeather(city: string): WeatherSnapshot {
  return {
    city,
    text: '实时天气暂不可用，已使用城市季节通用内容',
    available: false,
    source: 'm1-acceptance-weather-offline',
    isDemo: true,
    version: 'm1-acceptance-1',
    reviewStatus: 'demo',
    updatedAt: new Date().toISOString(),
  }
}

export interface TodayExperienceRequest {
  profile: WellnessProfile
  checkIn: DailyCheckIn
  scenario?: M1AcceptanceScenario
  date?: string
  recentMainRecipeIds?: string[]
}

export async function getTodayExperience({
  profile,
  checkIn,
  scenario = 'normal',
  date,
  recentMainRecipeIds = [],
}: TodayExperienceRequest): Promise<TodayExperienceResult> {
  const safety = screenSafety(profile, checkIn)
  if (safety.blocked) return { safety }

  if (scenario === 'slow') await wait(2000)
  if (scenario === 'error') {
    await wait(350)
    throw new Error('M1 acceptance scenario: simulated content error')
  }
  if (scenario === 'empty') {
    await wait(350)
    return { safety }
  }

  const calendar = await createCalendarAdapter().getDate(date)

  if (scenario === 'normal' && cloudApiEnabled()) {
    try {
      const cloud = await requestCloudToday(
        profile,
        checkIn,
        date || calendar.dateKey,
        recentMainRecipeIds,
      )
      if (cloud.main) {
        return {
          safety,
          model: {
            calendar,
            weather: cloud.weather,
            main: cloud.main,
            alternatives: cloud.alternatives.slice(0, 2),
            contentBundle: cloud.seasonalContent,
            recommendationReasons: cloud.reasons,
            fallbackUsed: cloud.degraded.length > 0,
          },
        }
      }
    } catch {
      // 云 API 不可用时继续执行本地确定性规则，保留离线演示能力。
    }
  }

  const weather = scenario === 'weather-offline'
    ? unavailableWeather(profile.city)
    : await createWeatherAdapter().getCityWeather(profile.city)

  const selection = rankM3Recommendations(calendar, weather, profile, checkIn, recentMainRecipeIds, {
    allowDemoContent: runtimeConfig.dataMode === 'demo',
  })
  if (!selection.recipes.length) return { safety }

  return {
    safety,
    model: {
      calendar,
      weather,
      main: selection.recipes[0],
      alternatives: selection.recipes.slice(1, 3),
      contentBundle: selection.bundle,
      recommendationReasons: selection.reasons,
      fallbackUsed: selection.fallbackUsed,
    },
  }
}
