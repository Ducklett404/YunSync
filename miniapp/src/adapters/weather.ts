import { demoWeatherByCity } from '../data/demo'
import { runtimeConfig } from '../config/runtime'
import type { WeatherSnapshot } from '../types/domain'

export interface WeatherAdapter {
  getCityWeather(city: string): Promise<WeatherSnapshot>
}

export class DemoWeatherAdapter implements WeatherAdapter {
  async getCityWeather(city: string): Promise<WeatherSnapshot> {
    await new Promise((resolve) => setTimeout(resolve, 180))
    const snapshot = demoWeatherByCity[city]
    return snapshot ? { ...snapshot, delivery: 'demo' } : {
      city,
      text: '实时天气暂不可用，已使用城市季节通用内容',
      available: false,
      source: 'seasonal-fallback',
      isDemo: true,
      version: 'm1-demo-1',
      reviewStatus: 'demo',
      updatedAt: new Date().toISOString(),
      delivery: 'demo',
    }
  }
}

interface WeatherApiPayload {
  city?: unknown
  temperature?: unknown
  feelsLike?: unknown
  humidity?: unknown
  precipitation?: unknown
  minTemperature?: unknown
  maxTemperature?: unknown
  text?: unknown
  observedAt?: unknown
  source?: unknown
  version?: unknown
}

interface WeatherCacheRecord {
  cachedAt: string
  snapshot: WeatherSnapshot
}

export interface ProductionWeatherOptions {
  endpoint: string
  provider: string
  timeoutMs: number
  cacheTtlMs: number
  staleTtlMs: number
  now?: () => number
}

const CACHE_PREFIX = 'yunsync:weather:v1:'

function optionalNumber(value: unknown): number | undefined {
  if (value === '' || value === null || value === undefined) return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function normalizePayload(payload: unknown, city: string, provider: string): WeatherSnapshot {
  if (!payload || typeof payload !== 'object') throw new Error('天气服务返回格式错误')
  const root = payload as Record<string, unknown>
  const value = (root.data && typeof root.data === 'object' ? root.data : root) as WeatherApiPayload
  const temperature = optionalNumber(value.temperature)
  const text = typeof value.text === 'string' ? value.text.trim() : ''
  const updatedAt = typeof value.observedAt === 'string' && Number.isFinite(Date.parse(value.observedAt))
    ? new Date(value.observedAt).toISOString()
    : ''
  if (temperature === undefined || !text || !updatedAt) throw new Error('天气服务缺少温度、天气描述或观测时间')
  const responseCity = typeof value.city === 'string' && value.city.trim() ? value.city.trim() : city
  const humidity = optionalNumber(value.humidity)
  const precipitation = optionalNumber(value.precipitation)
  const minTemperature = optionalNumber(value.minTemperature)
  const maxTemperature = optionalNumber(value.maxTemperature)
  if (responseCity !== city) throw new Error('天气服务返回了其他城市的数据')
  if (temperature < -80 || temperature > 60) throw new Error('天气服务返回的温度超出有效范围')
  if (humidity !== undefined && (humidity < 0 || humidity > 100)) throw new Error('天气服务返回的湿度超出有效范围')
  if (precipitation !== undefined && precipitation < 0) throw new Error('天气服务返回的降水量无效')
  if (minTemperature !== undefined && maxTemperature !== undefined && minTemperature > maxTemperature) throw new Error('天气服务返回的温差范围无效')
  return {
    city: responseCity,
    temperature,
    feelsLike: optionalNumber(value.feelsLike),
    humidity,
    precipitation,
    minTemperature,
    maxTemperature,
    text,
    available: true,
    source: typeof value.source === 'string' && value.source.trim() ? value.source.trim() : provider,
    isDemo: false,
    version: typeof value.version === 'string' && value.version.trim() ? value.version.trim() : 'weather-api-v1',
    reviewStatus: 'approved',
    updatedAt,
    delivery: 'live',
  }
}

function unavailableWeather(city: string): WeatherSnapshot {
  return {
    city,
    text: '实时天气暂不可用，已使用城市季节通用内容',
    available: false,
    source: 'seasonal-fallback',
    isDemo: false,
    version: 'weather-fallback-v1',
    reviewStatus: 'approved',
    updatedAt: new Date().toISOString(),
    delivery: 'fallback',
  }
}

export class ProductionWeatherAdapter implements WeatherAdapter {
  private readonly now: () => number

  constructor(private readonly options: ProductionWeatherOptions) {
    this.now = options.now || Date.now
  }

  private cacheKey(city: string): string {
    return `${CACHE_PREFIX}${encodeURIComponent(city)}`
  }

  private readCache(city: string): WeatherCacheRecord | undefined {
    try {
      const value = uni.getStorageSync(this.cacheKey(city)) as WeatherCacheRecord | undefined
      if (!value || !value.snapshot || !Number.isFinite(Date.parse(value.cachedAt))) return undefined
      if (value.snapshot.city !== city || value.snapshot.isDemo || !value.snapshot.available) return undefined
      return value
    } catch {
      return undefined
    }
  }

  private writeCache(city: string, snapshot: WeatherSnapshot): void {
    try {
      uni.setStorageSync(this.cacheKey(city), { cachedAt: new Date(this.now()).toISOString(), snapshot })
    } catch {
      // 天气仍可展示；缓存写入失败不应中断核心浏览。
    }
  }

  private request(city: string): Promise<WeatherSnapshot> {
    const separator = this.options.endpoint.includes('?') ? '&' : '?'
    const url = `${this.options.endpoint}${separator}city=${encodeURIComponent(city)}`
    return new Promise((resolve, reject) => {
      uni.request({
        url,
        method: 'GET',
        timeout: this.options.timeoutMs,
        success: (response) => {
          if (response.statusCode < 200 || response.statusCode >= 300) {
            reject(new Error(`天气服务 HTTP ${response.statusCode}`))
            return
          }
          try {
            const snapshot = normalizePayload(response.data, city, this.options.provider)
            const observationAge = this.now() - Date.parse(snapshot.updatedAt)
            if (observationAge > this.options.staleTtlMs || observationAge < -10 * 60 * 1000) throw new Error('天气观测时间已过期或来自未来')
            resolve(snapshot)
          }
          catch (error) { reject(error) }
        },
        fail: reject,
      })
    })
  }

  async getCityWeather(city: string): Promise<WeatherSnapshot> {
    const cached = this.readCache(city)
    const cacheAge = cached ? this.now() - Date.parse(cached.cachedAt) : Number.POSITIVE_INFINITY
    if (cached && cacheAge <= this.options.cacheTtlMs) {
      return { ...cached.snapshot, delivery: 'fresh-cache' }
    }
    try {
      const snapshot = await this.request(city)
      this.writeCache(city, snapshot)
      return snapshot
    } catch {
      if (cached && cacheAge <= this.options.staleTtlMs) {
        return { ...cached.snapshot, text: `${cached.snapshot.text}（缓存）`, delivery: 'stale-cache' }
      }
      return unavailableWeather(city)
    }
  }
}

export function createWeatherAdapter(): WeatherAdapter {
  if (runtimeConfig.dataMode === 'real' && runtimeConfig.weatherEndpoint) {
    return new ProductionWeatherAdapter({
      endpoint: runtimeConfig.weatherEndpoint,
      provider: runtimeConfig.weatherProvider || 'configured-weather-service',
      timeoutMs: runtimeConfig.weatherTimeoutMs,
      cacheTtlMs: runtimeConfig.weatherCacheTtlMs,
      staleTtlMs: runtimeConfig.weatherStaleTtlMs,
    })
  }
  if (runtimeConfig.dataMode === 'real') return { getCityWeather: async city => unavailableWeather(city) }
  return new DemoWeatherAdapter()
}
