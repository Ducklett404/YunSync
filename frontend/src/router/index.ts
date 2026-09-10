import { createRouter, createWebHistory } from 'vue-router'
import { canAccessHealthFlow } from '@/state/onboarding'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/start', name: 'onboarding', component: () => import('@/views/OnboardingView.vue'), meta: { title: '开始与安全说明' } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '健康总览', requiresOnboarding: true } },
    { path: '/report', name: 'report', component: () => import('@/views/ReportView.vue'), meta: { title: '报告确认', requiresOnboarding: true } },
    { path: '/actions', name: 'actions', component: () => import('@/views/ActionsView.vue'), meta: { title: '候选行动', requiresOnboarding: true } },
    { path: '/experiment', name: 'experiment', component: () => import('@/views/ExperimentView.vue'), meta: { title: '个人实验', requiresOnboarding: true } },
    { path: '/results', name: 'results', component: () => import('@/views/ResultsView.vue'), meta: { title: '结果评估', requiresOnboarding: true } },
  ],
})

router.beforeEach((to) => {
  if (to.meta.requiresOnboarding && !canAccessHealthFlow()) {
    return { name: 'onboarding' }
  }
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title)} | 云循 HealthLoop`
})
