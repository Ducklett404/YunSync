export type ReviewStatus = 'demo' | 'draft' | 'approved' | 'disabled'

export interface TraceableData {
  source: string
  isDemo: boolean
  version: string
  reviewStatus: ReviewStatus
  updatedAt: string
}

export interface WeatherSnapshot extends TraceableData {
  city: string
  temperature?: number
  feelsLike?: number
  humidity?: number
  precipitation?: number
  minTemperature?: number
  maxTemperature?: number
  text: string
  available: boolean
  delivery?: 'live' | 'fresh-cache' | 'stale-cache' | 'fallback' | 'demo'
}

export interface CalendarContext extends TraceableData {
  dateKey: string
  gregorianDate: string
  weekday: string
  lunarYear?: string
  lunarMonth?: number
  lunarDay?: number
  lunarDate: string
  solarTerm?: string
  solarTermTime?: string
  festival?: string
}

export interface RecipeSummary extends TraceableData {
  id: string
  name: string
  category: '菜' | '饭' | '粥' | '汤' | '饮品' | '节庆食品'
  minutes: number
  tags: string[]
  reason: string
}

export interface RecipeIngredient {
  name: string
  amount: string
  preparation?: string
  allergenTags: string[]
  isKey: boolean
}

export interface RecipeStep {
  order: number
  action: string
}

export interface RecipeSubstitution {
  from: string
  to: string
  note: string
}

export type RegionTag = '全国' | '江南' | '华北' | '华南' | '西南' | '东北'

export interface RecipeTemplate extends RecipeSummary {
  servings: number
  ingredients: RecipeIngredient[]
  tools: string[]
  steps: RecipeStep[]
  substitutions: RecipeSubstitution[]
  allergens: string[]
  exclusions: string[]
  regions: RegionTag[]
  sceneTags: string[]
  sourceNote: string
  reviewer?: string
}

export interface CalendarContentRule {
  kind: 'lunar' | 'solar-term'
  lunarMonth?: number
  lunarDay?: number
  solarTerm?: string
  gregorianFixtures: Record<string, string>
}

export interface FestivalContentBundle extends TraceableData {
  id: string
  name: string
  kind: 'festival' | 'solar-term'
  cultureNote: string
  dateRule: CalendarContentRule
  regions: RegionTag[]
  recipeIds: string[]
}

export interface WellnessProfile {
  city: string
  ageGroup: string
  allergens: string[]
  preferences: string[]
  medicalConditions: string[]
  medications: string[]
  doctorDietRestrictions: string[]
  serviceScope: ServiceScope
  constitutionSurveyInterest: boolean
  constitutionReference?: {
    labels: string[]
    recommendationTags: string[]
    surveyVersion: string
  }
  updatedAt: string
}

export type ServiceScope =
  | 'adult'
  | 'child'
  | 'pregnant-or-breastfeeding'
  | 'complex-chronic'
  | 'oncology-treatment'
  | 'dialysis'
  | 'eating-disorder'

export type FeelingOption =
  | '正常'
  | '有点着凉'
  | '胃口较差'
  | '睡眠不足'
  | '口干'
  | '排便不规律'
  | '其他轻微不适'

export interface DailyCheckIn {
  dateKey: string
  feelings: FeelingOption[]
  note: string
  updatedAt: string
}

export type SafetyLevel = 'clear' | 'urgent' | 'out-of-scope' | 'medical-review'

export interface SafetyDecision {
  blocked: boolean
  level: SafetyLevel
  matchedTriggers: string[]
  title: string
  message: string
}

export interface TodayViewModel {
  calendar: CalendarContext
  weather: WeatherSnapshot
  main: RecipeTemplate
  alternatives: RecipeTemplate[]
  contentBundle?: FestivalContentBundle
  recommendationReasons: string[]
  fallbackUsed: boolean
}

export interface TodayExperienceResult {
  safety: SafetyDecision
  model?: TodayViewModel
}

export type PantryCategory = '主食' | '蔬菜水果' | '肉蛋奶' | '豆制品' | '调味品'
export type PantryMatchKind = 'complete' | 'substitution' | 'missing'

export interface PantrySession {
  ingredients: string[]
  maxMinutes: number
  tools: string[]
  targetServings: 1 | 2 | 4
  maxAdditionalIngredients: 0 | 1 | 2
}

export interface PantrySubstitutionMatch {
  from: string
  to: string
  note: string
}

export interface PantryRecipeMatch {
  recipe: RecipeTemplate
  kind: PantryMatchKind
  matchedIngredients: string[]
  missingIngredients: string[]
  substitutionsUsed: PantrySubstitutionMatch[]
  targetServings: 1 | 2 | 4
}

export interface PantryMatchResult {
  safety: SafetyDecision
  matches: PantryRecipeMatch[]
  safetyFilteredCount: number
  contentFilteredCount: number
  constraintFilteredCount: number
  message: string
}

export type M1AcceptanceScenario = 'normal' | 'slow' | 'weather-offline' | 'error' | 'empty'

export type M2AcceptanceDateScenario =
  | 'today'
  | 'laba'
  | 'spring-festival'
  | 'duanwu'
  | 'mid-autumn'
  | 'lichun'
  | 'qingming'
  | 'bailu'
  | 'dongzhi'

export type M3AcceptanceScenario = 'profile' | 'high-fever' | 'chest-pain' | 'breathing' | 'garlic' | 'out-of-scope'
