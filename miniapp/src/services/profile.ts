import type { WellnessProfile } from '../types/domain'

const LEGACY_PROFILE_KEY = 'yunsync:wellness-profile:v1'
const PROFILE_V2_KEY = 'yunsync:wellness-profile:v2'

export const defaultProfile: WellnessProfile = {
  city: '杭州',
  ageGroup: '18—39岁',
  allergens: [],
  preferences: ['清淡'],
  medicalConditions: [],
  medications: [],
  doctorDietRestrictions: [],
  serviceScope: 'adult',
  constitutionSurveyInterest: false,
  updatedAt: new Date().toISOString(),
}

function cloneDefaultProfile(): WellnessProfile {
  return {
    ...defaultProfile,
    allergens: [],
    preferences: [...defaultProfile.preferences],
    medicalConditions: [],
    medications: [],
    doctorDietRestrictions: [],
  }
}

function normalizeProfile(stored?: Partial<WellnessProfile>): WellnessProfile {
  const fallback = cloneDefaultProfile()
  const source = stored || {}
  const reference = source.constitutionReference
  return {
    ...fallback,
    ...source,
    allergens: Array.isArray(source.allergens) ? source.allergens : fallback.allergens,
    preferences: Array.isArray(source.preferences) ? source.preferences : fallback.preferences,
    medicalConditions: Array.isArray(source.medicalConditions) ? source.medicalConditions : [],
    medications: Array.isArray(source.medications) ? source.medications : [],
    doctorDietRestrictions: Array.isArray(source.doctorDietRestrictions) ? source.doctorDietRestrictions : [],
    constitutionReference: reference
      && Array.isArray(reference.labels)
      && Array.isArray(reference.recommendationTags)
      && typeof reference.surveyVersion === 'string'
      ? {
          labels: reference.labels.filter(item => typeof item === 'string'),
          recommendationTags: reference.recommendationTags.filter(item => typeof item === 'string'),
          surveyVersion: reference.surveyVersion,
        }
      : undefined,
  }
}

export function loadProfile(): WellnessProfile {
  try {
    const stored = uni.getStorageSync(PROFILE_V2_KEY) || uni.getStorageSync(LEGACY_PROFILE_KEY)
    return normalizeProfile(stored || undefined)
  } catch {
    return cloneDefaultProfile()
  }
}

export function saveProfile(profile: WellnessProfile): void {
  uni.setStorageSync(PROFILE_V2_KEY, normalizeProfile({ ...profile, updatedAt: new Date().toISOString() }))
}
