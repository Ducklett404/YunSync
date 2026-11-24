export function scaleRecipeAmount(amount: string, baseServings: number, targetServings: number): string | undefined {
  const match = /^(\d+(?:\.\d+)?)\s*(毫升|升|千克|公斤|克|个|片|根|条|颗|张|枚|汤匙|茶匙|大勺|小勺|g|kg|ml|l)$/i.exec(amount.trim())
  if (!match || !Number.isFinite(baseServings) || baseServings <= 0
    || !Number.isFinite(targetServings) || targetServings <= 0) return undefined

  const scaled = Number((Number(match[1]) * targetServings / baseServings).toFixed(3))
  return Number.isFinite(scaled) && scaled > 0 ? `${scaled}${match[2]}` : undefined
}
