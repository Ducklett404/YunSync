interface RecommendationHistoryItem {
  dateKey: string
  recipeId: string
  updatedAt: string
}

const HISTORY_KEY = 'yunsync:recommendation-history:v1'

function loadHistory(): RecommendationHistoryItem[] {
  try {
    const stored = uni.getStorageSync(HISTORY_KEY)
    return Array.isArray(stored) ? stored : []
  } catch {
    return []
  }
}

export function loadRecentMainRecipeIds(excludeDateKey?: string): string[] {
  return loadHistory()
    .filter((item) => item.dateKey !== excludeDateKey)
    .slice(-7)
    .reverse()
    .map((item) => item.recipeId)
}

export function saveMainRecommendation(dateKey: string, recipeId: string): void {
  const next = loadHistory().filter((item) => item.dateKey !== dateKey)
  next.push({ dateKey, recipeId, updatedAt: new Date().toISOString() })
  uni.setStorageSync(HISTORY_KEY, next.slice(-14))
}
