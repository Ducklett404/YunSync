import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/start', name: 'onboarding', component: () => import('@/views/OnboardingView.vue'), meta: { title: '开始与安全说明' } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '健康总览' } },
    { path: '/report', name: 'report', component: () => import('@/views/ReportView.vue'), meta: { title: '报告确认' } },
    { path: '/actions', name: 'actions', component: () => import('@/views/ActionsView.vue'), meta: { title: '候选行动' } },
    { path: '/experiment', name: 'experiment', component: () => import('@/views/ExperimentView.vue'), meta: { title: '个人实验' } },
    { path: '/results', name: 'results', component: () => import('@/views/ResultsView.vue'), meta: { title: '结果评估' } },
  ],
})

router.afterEach((to) => {
  document.title = `${String(to.meta.title)} | 云循 HealthLoop`
})
