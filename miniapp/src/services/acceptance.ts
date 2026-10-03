import type { M1AcceptanceScenario, M2AcceptanceDateScenario } from '../types/domain'

const STORAGE_KEY = 'yunsync:m1-acceptance-scenario'
const M2_DATE_STORAGE_KEY = 'yunsync:m2-acceptance-date'
const scenarios: M1AcceptanceScenario[] = ['normal', 'slow', 'weather-offline', 'error', 'empty']
const m2DateScenarios: M2AcceptanceDateScenario[] = [
  'today', 'laba', 'spring-festival', 'duanwu', 'mid-autumn', 'lichun', 'qingming', 'bailu', 'dongzhi',
]

export const acceptanceScenarioLabels: Record<M1AcceptanceScenario, string> = {
  normal: '正常',
  slow: '加载中',
  'weather-offline': '无天气',
  error: '错误',
  empty: '空数据',
}

export function loadAcceptanceScenario(): M1AcceptanceScenario {
  const stored = uni.getStorageSync(STORAGE_KEY)
  return scenarios.includes(stored) ? stored : 'normal'
}

export function saveAcceptanceScenario(scenario: M1AcceptanceScenario) {
  uni.setStorageSync(STORAGE_KEY, scenario)
}

export function loadM2AcceptanceDateScenario(): M2AcceptanceDateScenario {
  const stored = uni.getStorageSync(M2_DATE_STORAGE_KEY)
  return m2DateScenarios.includes(stored) ? stored : 'today'
}

export function saveM2AcceptanceDateScenario(scenario: M2AcceptanceDateScenario) {
  uni.setStorageSync(M2_DATE_STORAGE_KEY, scenario)
}
