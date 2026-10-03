import { getRecipeById } from '../data/m2'
import type { RecipeTemplate } from '../types/domain'
import { contentUnavailableReason, isContentAvailable } from './content'
import type { ContentOptions } from './content'

const STORAGE_KEY = 'yunsync:engagement:v1'
export const engagementLimits = { favorites: 50, recent: 20, feedback: 50 }
export const feedbackLabels = {
  helpful: '有帮助',
  'too-complex': '制作太复杂',
  'unclear-steps': '步骤不清楚',
  'ingredient-issue': '食材不好准备',
} as const
export type FeedbackKind = keyof typeof feedbackLabels

export interface RecipeRecord {
  recipeId: string
  name: string
  version: string
  updatedAt: string
}
export interface RecipeFeedback extends RecipeRecord { kind: FeedbackKind }
interface EngagementState {
  favorites: RecipeRecord[]
  recent: RecipeRecord[]
  feedback: RecipeFeedback[]
}
export interface SavedRecipeView extends RecipeRecord {
  available: boolean
  statusLabel: string
  currentVersion?: string
  versionChanged: boolean
}

function isRecord(value: unknown): value is RecipeRecord {
  if (!value || typeof value !== 'object') return false
  const item = value as RecipeRecord
  return typeof item.recipeId === 'string' && item.recipeId.length > 0 && item.recipeId.length <= 100
    && typeof item.name === 'string' && item.name.length <= 100
    && typeof item.version === 'string' && item.version.length <= 100
    && typeof item.updatedAt === 'string' && Number.isFinite(Date.parse(item.updatedAt))
}

function records<T extends RecipeRecord>(value: unknown, limit: number, valid: (item: unknown) => item is T): T[] {
  if (!Array.isArray(value)) return []
  const seen = new Set<string>()
  return value.filter(valid).filter((item) => {
    if (seen.has(item.recipeId)) return false
    seen.add(item.recipeId)
    return true
  }).slice(0, limit)
}

function loadState(strict = false): EngagementState {
  try {
    const stored = uni.getStorageSync(STORAGE_KEY) as Partial<EngagementState> | undefined
    return {
      favorites: records(stored?.favorites, engagementLimits.favorites, isRecord),
      recent: records(stored?.recent, engagementLimits.recent, isRecord),
      feedback: records(stored?.feedback, engagementLimits.feedback, (value): value is RecipeFeedback =>
        isRecord(value) && Object.prototype.hasOwnProperty.call(feedbackLabels, (value as RecipeFeedback).kind)),
    }
  } catch (error) {
    if (strict) throw error
    return { favorites: [], recent: [], feedback: [] }
  }
}

function snapshot(recipe: RecipeTemplate): RecipeRecord {
  return { recipeId: recipe.id, name: recipe.name, version: recipe.version, updatedAt: new Date().toISOString() }
}

function requireAvailable(recipeId: string, options: ContentOptions): RecipeTemplate {
  const recipe = getRecipeById(recipeId)
  if (!recipe || !isContentAvailable(recipe, options)) throw new Error(contentUnavailableReason(recipe))
  return recipe
}

export function isFavorite(recipeId: string): boolean {
  return loadState().favorites.some((item) => item.recipeId === recipeId)
}

export function setFavorite(recipeId: string, favorite: boolean, options: ContentOptions = {}): void {
  const state = loadState(true)
  const existing = state.favorites.some((item) => item.recipeId === recipeId)
  if (favorite) {
    const recipe = requireAvailable(recipeId, options)
    if (existing) return
    if (state.favorites.length >= engagementLimits.favorites) throw new Error('收藏已满，请先移除一些收藏')
    state.favorites.unshift(snapshot(recipe))
  } else {
    state.favorites = state.favorites.filter((item) => item.recipeId !== recipeId)
  }
  uni.setStorageSync(STORAGE_KEY, state)
}

export function recordRecipeView(recipeId: string, options: ContentOptions = {}): void {
  const recipe = requireAvailable(recipeId, options)
  const state = loadState(true)
  state.recent = [snapshot(recipe), ...state.recent.filter((item) => item.recipeId !== recipeId)].slice(0, engagementLimits.recent)
  uni.setStorageSync(STORAGE_KEY, state)
}

export function resolveSavedRecipe(record: RecipeRecord, options: ContentOptions = {}): SavedRecipeView {
  const recipe = getRecipeById(record.recipeId)
  const available = Boolean(recipe && isContentAvailable(recipe, options))
  return {
    ...record,
    name: available && recipe ? recipe.name : record.name,
    available,
    statusLabel: available ? '可查看' : contentUnavailableReason(recipe),
    currentVersion: recipe?.version,
    versionChanged: Boolean(recipe && recipe.version !== record.version),
  }
}

export function loadSavedRecipes(kind: 'favorites' | 'recent', options: ContentOptions = {}): SavedRecipeView[] {
  return loadState()[kind].map((record) => resolveSavedRecipe(record, options))
}

export function loadRecipeFeedback(recipeId: string): RecipeFeedback | undefined {
  return loadState().feedback.find((item) => item.recipeId === recipeId)
}

export function saveRecipeFeedback(recipeId: string, kind: FeedbackKind, options: ContentOptions = {}): void {
  const recipe = requireAvailable(recipeId, options)
  if (!Object.prototype.hasOwnProperty.call(feedbackLabels, kind)) throw new Error('请选择有效反馈')
  const state = loadState(true)
  state.feedback = [{ ...snapshot(recipe), kind }, ...state.feedback.filter((item) => item.recipeId !== recipeId)].slice(0, engagementLimits.feedback)
  uni.setStorageSync(STORAGE_KEY, state)
}

export function clearEngagement(): void {
  uni.removeStorageSync(STORAGE_KEY)
}
