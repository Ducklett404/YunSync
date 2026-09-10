import { computed, ref } from 'vue'
import type { DemoSession, UserProfile } from '@/types'


const TOKEN_KEY = 'yunsync_demo_access_token'
const USER_KEY = 'yunsync_demo_user'

function readStoredUser(): UserProfile | null {
  const value = sessionStorage.getItem(USER_KEY)
  if (!value) return null
  try {
    return JSON.parse(value) as UserProfile
  } catch {
    sessionStorage.removeItem(USER_KEY)
    return null
  }
}

export const accessToken = ref(sessionStorage.getItem(TOKEN_KEY) || '')
export const currentUser = ref<UserProfile | null>(readStoredUser())
export const isAuthenticated = computed(() => Boolean(accessToken.value))

export function getAccessToken(): string {
  return accessToken.value
}

export function setCurrentUser(user: UserProfile): void {
  currentUser.value = user
  sessionStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function setAuthSession(session: DemoSession): void {
  accessToken.value = session.access_token
  sessionStorage.setItem(TOKEN_KEY, session.access_token)
  setCurrentUser(session.user)
}

export function clearAuthSession(): void {
  accessToken.value = ''
  currentUser.value = null
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(USER_KEY)
}
