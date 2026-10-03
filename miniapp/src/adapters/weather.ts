import { demoWeatherByCity } from '../data/demo'
import type { WeatherSnapshot } from '../types/domain'

export interface WeatherAdapter {
  getCityWeather(city: string): Promise<WeatherSnapshot>
}

export class DemoWeatherAdapter implements WeatherAdapter {
  async getCityWeather(city: string): Promise<WeatherSnapshot> {
    await new Promise((resolve) => setTimeout(resolve, 180))
    return demoWeatherByCity[city] || {
      city,
      text: '实时天气暂不可用，已使用城市季节通用内容',
      available: false,
      source: 'seasonal-fallback',
      isDemo: true,
      version: 'm1-demo-1',
      reviewStatus: 'demo',
      updatedAt: new Date().toISOString(),
    }
  }
}

export function createWeatherAdapter(): WeatherAdapter {
  return new DemoWeatherAdapter()
}
