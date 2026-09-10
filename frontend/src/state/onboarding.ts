let healthFlowUnlocked = false

export function resetOnboardingAccess() {
  healthFlowUnlocked = false
}

export function unlockHealthFlow() {
  healthFlowUnlocked = true
}

export function canAccessHealthFlow() {
  return healthFlowUnlocked
}
