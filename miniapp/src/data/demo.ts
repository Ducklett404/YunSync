import type { CalendarContext, RecipeTemplate, WeatherSnapshot } from '../types/domain'
import { m2RecipeLibrary, resolveDemoCalendar } from './m2'

const now = '2026-09-29T08:00:00+08:00'

export const demoCalendar: CalendarContext = resolveDemoCalendar('2026-09-29')

export const demoWeatherByCity: Record<string, WeatherSnapshot> = {
  杭州: {
    city: '杭州', temperature: 24, feelsLike: 25, humidity: 72, precipitation: 0.4,
    minTemperature: 20, maxTemperature: 27, text: '小雨，昼夜温差较小', available: true,
    source: 'demo-weather', isDemo: true, version: 'm1-demo-1', reviewStatus: 'demo', updatedAt: now,
  },
  北京: {
    city: '北京', temperature: 20, feelsLike: 19, humidity: 38, precipitation: 0,
    minTemperature: 12, maxTemperature: 23, text: '晴，空气偏干', available: true,
    source: 'demo-weather', isDemo: true, version: 'm1-demo-1', reviewStatus: 'demo', updatedAt: now,
  },
}

export const demoRecipes: RecipeTemplate[] = m2RecipeLibrary.filter((recipe) =>
  ['demo-yam-millet', 'demo-tomato-tofu', 'demo-greens'].includes(recipe.id),
)
