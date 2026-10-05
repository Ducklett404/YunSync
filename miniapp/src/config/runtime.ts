function positiveNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

const environment = import.meta.env || {}
const dataMode = (environment.VITE_DATA_MODE || 'demo') as 'demo' | 'real'

export const runtimeConfig = {
  dataMode,
  showDemoBadge: dataMode !== 'real',
  weatherEndpoint: (environment.VITE_YUNSYNC_WEATHER_ENDPOINT || '').trim(),
  weatherProvider: (environment.VITE_YUNSYNC_WEATHER_PROVIDER || '').trim(),
  weatherTimeoutMs: positiveNumber(environment.VITE_YUNSYNC_WEATHER_TIMEOUT_MS, 4000),
  weatherCacheTtlMs: positiveNumber(environment.VITE_YUNSYNC_WEATHER_CACHE_MINUTES, 30) * 60 * 1000,
  weatherStaleTtlMs: positiveNumber(environment.VITE_YUNSYNC_WEATHER_STALE_HOURS, 6) * 60 * 60 * 1000,
  legalEntity: (environment.VITE_YUNSYNC_LEGAL_ENTITY || '').trim(),
  privacyContact: (environment.VITE_YUNSYNC_PRIVACY_CONTACT || '').trim(),
  privacyNoticeVersion: (environment.VITE_YUNSYNC_PRIVACY_NOTICE_VERSION || '').trim(),
  surveyEnabled: environment.VITE_YUNSYNC_SURVEY_ENABLED === 'true',
}
