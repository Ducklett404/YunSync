import { createRouter, createWebHistory } from 'vue-router'
import { canAccessHealthFlow } from '@/state/onboarding'
import { currentUser, isAuthenticated } from '@/state/auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/start', name: 'onboarding', component: () => import('@/views/OnboardingView.vue'), meta: { title: '开始与安全说明' } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '健康总览', requiresOnboarding: true } },
    { path: '/report', name: 'report', component: () => import('@/views/ReportView.vue'), meta: { title: '报告确认', requiresOnboarding: true } },
    { path: '/safety', name: 'safety', component: () => import('@/views/SafetyView.vue'), meta: { title: '安全提示', requiresAuth: true } },
    { path: '/care-plan', name: 'care-plan', component: () => import('@/views/CarePlanView.vue'), meta: { title: '食养方案', requiresOnboarding: true } },
    { path: '/actions', name: 'actions', component: () => import('@/views/ActionsView.vue'), meta: { title: '候选行动', requiresOnboarding: true } },
    { path: '/experiment', name: 'experiment', component: () => import('@/views/ExperimentView.vue'), meta: { title: '个人实验', requiresOnboarding: true } },
    { path: '/results', name: 'results', component: () => import('@/views/ResultsView.vue'), meta: { title: '结果评估', requiresOnboarding: true } },
    { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue'), meta: { title: '账号与档案', requiresAuth: true } },
    { path: '/admin/content', name: 'content-admin', component: () => import('@/views/AdminContentView.vue'), meta: { title: '内容知识库', requiresReviewer: true } },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresReviewer && (!isAuthenticated.value || currentUser.value?.role !== 'reviewer')) {
    return { name: 'onboarding' }
  }
  if (to.meta.requiresAuth && !isAuthenticated.value) {
    return { name: 'onboarding' }
  }
  if (to.meta.requiresOnboarding && (!isAuthenticated.value || !canAccessHealthFlow())) {
    return { name: 'onboarding' }
  }
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title)} | 云循 HealthLoop`
})
