import axios from 'axios'
import type { ActionTemplate, DashboardData, Experiment, ExperimentResult, ReportAnalysis } from '@/types'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 12000,
})

export async function fetchDashboard(): Promise<DashboardData> {
  const { data } = await client.get<DashboardData>('/dashboard')
  return data
}

export async function fetchLatestReport(): Promise<ReportAnalysis> {
  const { data } = await client.get<ReportAnalysis>('/reports/latest')
  return data
}

export async function analyzeReport(file: File): Promise<ReportAnalysis> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<ReportAnalysis>('/reports/analyze', form)
  return data
}

export async function confirmReport(reportId: string): Promise<void> {
  await client.post(`/reports/${reportId}/confirm`)
}

export async function fetchActions(): Promise<ActionTemplate[]> {
  const { data } = await client.get<ActionTemplate[]>('/actions')
  return data
}

export async function createExperiment(actionId: string): Promise<Experiment> {
  const { data } = await client.post<Experiment>('/experiments', {
    user_id: 'demo-user',
    action_id: actionId,
  })
  return data
}

export async function fetchCurrentExperiment(): Promise<Experiment> {
  const { data } = await client.get<Experiment>('/experiments/current')
  return data
}

export async function saveObservation(
  experimentId: string,
  payload: {
    observed_on: string
    completed: boolean
    steps_30m?: number
    sleep_hours?: number
    sugary_drinks?: number
    subjective_score?: number
    notes?: string
  },
): Promise<void> {
  await client.post(`/experiments/${experimentId}/observations`, payload)
}

export async function fetchExperimentResult(experimentId: string): Promise<ExperimentResult> {
  const { data } = await client.get<ExperimentResult>(`/experiments/${experimentId}/result`)
  return data
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.detail || error.message || '请求失败'
  }
  return error instanceof Error ? error.message : '发生未知错误'
}
