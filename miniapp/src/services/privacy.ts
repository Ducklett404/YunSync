const STORAGE_PREFIX = 'yunsync:'

export interface LocalDataExport {
  schemaVersion: 'yunsync-local-export-v1'
  generatedAt: string
  storageScope: 'current-device-only'
  keys: string[]
  data: Record<string, unknown>
}

export interface LocalDataDeletionResult {
  deletedKeys: string[]
}

function localKeys(): string[] {
  const info = uni.getStorageInfoSync()
  return (Array.isArray(info.keys) ? info.keys : [])
    .filter((key): key is string => typeof key === 'string' && key.startsWith(STORAGE_PREFIX))
    .sort()
}

export function buildLocalDataExport(now = new Date()): LocalDataExport {
  const keys = localKeys()
  const data: Record<string, unknown> = {}
  for (const key of keys) data[key] = uni.getStorageSync(key)
  return {
    schemaVersion: 'yunsync-local-export-v1',
    generatedAt: now.toISOString(),
    storageScope: 'current-device-only',
    keys,
    data,
  }
}

export function deleteAllLocalData(): LocalDataDeletionResult {
  const keys = localKeys()
  const failed: string[] = []
  for (const key of keys) {
    try { uni.removeStorageSync(key) }
    catch { failed.push(key) }
  }
  if (failed.length) throw new Error(`以下本机数据未能删除：${failed.join('、')}`)
  return { deletedKeys: keys }
}
