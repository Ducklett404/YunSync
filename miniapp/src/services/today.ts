import { createCalendarAdapter } from '../adapters/calendar'
import { createWeatherAdapter } from '../adapters/weather'
import { rankM3Recommendations } from './recommendation'
import { screenSafety } from './safety'
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

  const [calendar, weather] = await Promise.all([
    createCalendarAdapter().getDate(date),
    scenario === 'weather-offline'
      ? Promise.resolve(unavailableWeather(profile.city))
      : createWeatherAdapter().getCityWeather(profile.city),
  ])

  const selection = rankM3Recommendations(calendar, weather, profile, checkIn, recentMainRecipeIds)
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
