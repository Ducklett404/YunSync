import { defineStore } from 'pinia'
import { fetchDashboard, getApiErrorMessage } from '@/services/api'
import type { DashboardData } from '@/types'

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    dashboard: null as DashboardData | null,
    loading: false,
    error: '',
  }),
  actions: {
    async loadDashboard(force = false) {
      if (this.dashboard && !force) return
      this.loading = true
      this.error = ''
      try {
        this.dashboard = await fetchDashboard()
      } catch (error) {
        this.error = getApiErrorMessage(error)
      } finally {
        this.loading = false
      }
    },
  },
})

