import type { DailyCheckIn, FeelingOption } from '../types/domain'

const CHECKIN_PREFIX = 'yunsync:daily-checkin:v1:'

export function createDefaultCheckIn(dateKey: string): DailyCheckIn {
  return {
    dateKey,
    feelings: ['正常'],
    note: '',
    updatedAt: new Date().toISOString(),
  }
}

export function loadDailyCheckIn(dateKey: string): DailyCheckIn {
  try {
    const stored = uni.getStorageSync(`${CHECKIN_PREFIX}${dateKey}`) as Partial<DailyCheckIn> | undefined
    if (!stored) return createDefaultCheckIn(dateKey)
    return {
      dateKey,
      feelings: Array.isArray(stored.feelings) && stored.feelings.length
        ? stored.feelings as FeelingOption[]
        : ['正常'],
      note: typeof stored.note === 'string' ? stored.note : '',
      updatedAt: stored.updatedAt || new Date().toISOString(),
    }
  } catch {
    return createDefaultCheckIn(dateKey)
  }
}

export function saveDailyCheckIn(checkIn: DailyCheckIn): void {
  uni.setStorageSync(`${CHECKIN_PREFIX}${checkIn.dateKey}`, {
    ...checkIn,
    updatedAt: new Date().toISOString(),
  })
}
