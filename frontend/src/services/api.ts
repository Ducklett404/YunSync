import axios from 'axios'
import { clearAuthSession, getAccessToken } from '@/state/auth'
import { resetOnboardingAccess } from '@/state/onboarding'
import type {
  AccountStatus,
  ActionTemplate,
  ConsentNotice,
  ConsentRecord,
  BulkContentValidation,
  ContentComparison,
  ContentItem,
  ContentReview,
  ContentStatus,
  ContentType,
  CarePlan,
  CarePlanRequest,
  AdherenceLog,
  AdherenceLogInput,
  FollowUpComparison,
  FollowUpReminder,
  FollowUpReminderInput,
  PlanRevision,
  DashboardData,
  DemoSession,
  Experiment,
  NextStepCode,
  ExperimentTransition,
  ExperimentResult,
  FoodSafetyProfile,
  FoodSafetyProfileInput,
  EvidenceSource,
  MetricHistory,
  ObservationImportResult,
  ReportAnalysis,
  ReportList,
  SafetyDecision,
  UserProfile,
} from '@/types'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 12000,
})

client.interceptors.request.use((config) => {
  const token = getAccessToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      clearAuthSession()
      resetOnboardingAccess()
      if (window.location.pathname !== '/start') window.location.replace('/start')
    }
    return Promise.reject(error)
  },
)

export async function loginDemo(accountId = 'demo-student'): Promise<DemoSession> {
  const { data } = await client.post<DemoSession>('/auth/demo', { account_id: accountId })
  return data
}

export async function logoutDemo(): Promise<void> {
  await client.post('/auth/logout')
}

export async function fetchConsentNotice(): Promise<ConsentNotice> {
  const { data } = await client.get<ConsentNotice>('/consents/notice')
  return data
}

export async function fetchAccountStatus(): Promise<AccountStatus> {
  const { data } = await client.get<AccountStatus>('/account/status')
  return data
}

export async function acceptConsent(version: string): Promise<ConsentRecord> {
  const { data } = await client.post<ConsentRecord>('/consents/accept', { version })
  return data
}

export async function withdrawConsent(): Promise<void> {
  await client.post('/consents/withdraw')
}

export async function fetchProfile(): Promise<UserProfile> {
  const { data } = await client.get<UserProfile>('/profile')
  return data
}

export async function updateProfile(payload: Partial<UserProfile>): Promise<UserProfile> {
  const { data } = await client.patch<UserProfile>('/profile', payload)
  return data
}

export async function fetchFoodSafetyProfile(): Promise<FoodSafetyProfile> {
  const { data } = await client.get<FoodSafetyProfile>('/profile/food-safety')
  return data
}

export async function updateFoodSafetyProfile(payload: FoodSafetyProfileInput): Promise<FoodSafetyProfile> {
  const { data } = await client.patch<FoodSafetyProfile>('/profile/food-safety', payload)
  return data
}

export async function fetchSafetyDecision(): Promise<SafetyDecision> {
  const { data } = await client.get<SafetyDecision>('/safety/decision')
  return data
}

export async function fetchCurrentCarePlan(): Promise<CarePlan | null> {
  const { data } = await client.get<CarePlan | null>('/care-plans/current')
  return data
}

export async function fetchCarePlanHistory(): Promise<CarePlan[]> {
  const { data } = await client.get<CarePlan[]>('/care-plans')
  return data
}

export async function fetchCarePlanLogs(planId: string): Promise<AdherenceLog[]> {
  const { data } = await client.get<AdherenceLog[]>(`/care-plans/${planId}/logs`)
  return data
}

export async function putCarePlanLog(planId: string, day: number, payload: AdherenceLogInput): Promise<AdherenceLog> {
  const { data } = await client.put<AdherenceLog>(`/care-plans/${planId}/logs/${day}`, payload)
  return data
}

export async function fetchFollowUpReminder(planId: string): Promise<FollowUpReminder | null> {
  const { data } = await client.get<FollowUpReminder | null>(`/care-plans/${planId}/reminder`)
  return data
}

export async function putFollowUpReminder(planId: string, payload: FollowUpReminderInput): Promise<FollowUpReminder> {
  const { data } = await client.put<FollowUpReminder>(`/care-plans/${planId}/reminder`, payload)
  return data
}

export async function compareFollowUpReports(previousReportId: string, currentReportId: string): Promise<FollowUpComparison> {
  const { data } = await client.post<FollowUpComparison>('/follow-ups/compare', {
    previous_report_id: previousReportId, current_report_id: currentReportId,
  })
  return data
}

export async function reviseCarePlan(planId: string, payload: CarePlanRequest): Promise<CarePlan> {
  const { data } = await client.post<CarePlan>(`/care-plans/${planId}/revise`, payload)
  return data
}

export async function fetchPlanRevision(planId: string): Promise<PlanRevision | null> {
  const { data } = await client.get<PlanRevision | null>(`/care-plans/${planId}/revision`)
  return data
}

export async function createCarePlan(payload: CarePlanRequest): Promise<CarePlan> {
  const { data } = await client.post<CarePlan>('/care-plans', payload)
  return data
}

export async function activateCarePlan(planId: string): Promise<CarePlan> {
  const { data } = await client.post<CarePlan>(`/care-plans/${planId}/activate`)
  return data
}

export async function downloadCarePlan(planId: string): Promise<Blob> {
  const { data } = await client.get<Blob>(`/care-plans/${planId}/export`, { responseType: 'blob' })
  return data
}

export async function saveSafetyScreening(payload: Record<string, boolean>): Promise<UserProfile> {
  const { data } = await client.post<UserProfile>('/profile/screening', payload)
  return data
}

export async function fetchDashboard(): Promise<DashboardData> {
  const { data } = await client.get<DashboardData>('/dashboard')
  return data
}

export async function fetchLatestReport(): Promise<ReportAnalysis> {
  const { data } = await client.get<ReportAnalysis>('/reports/latest')
  return data
}

export async function fetchReports(limit = 20, offset = 0): Promise<ReportList> {
  const { data } = await client.get<ReportList>('/reports', { params: { limit, offset } })
  return data
}

export async function fetchReport(reportId: string): Promise<ReportAnalysis> {
  const { data } = await client.get<ReportAnalysis>(`/reports/${reportId}`)
  return data
}

export async function fetchMetricHistory(): Promise<MetricHistory> {
  const { data } = await client.get<MetricHistory>('/metrics/summary')
  return data
}

export async function analyzeReport(file: File): Promise<ReportAnalysis> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post<ReportAnalysis>('/reports/analyze', form)
  return data
}

export async function createManualReport(payload: {
  title: string
  institution: string
  measured_at: string
  metrics: { name: string; value: number; unit: string; reference_range: string; method: string }[]
}): Promise<ReportAnalysis> {
  const { data } = await client.post<ReportAnalysis>('/reports/manual', payload)
  return data
}

export async function updateReportMetadata(
  reportId: string,
  payload: { institution: string; examined_at: string },
): Promise<ReportAnalysis> {
  const { data } = await client.patch<ReportAnalysis>(`/reports/${reportId}/metadata`, payload)
  return data
}

export async function retryReport(reportId: string): Promise<ReportAnalysis> {
  const { data } = await client.post<ReportAnalysis>(`/reports/${reportId}/retry`)
  return data
}

export async function updateReportCriticalMarker(
  reportId: string,
  status: ReportAnalysis['critical_marker_status'],
): Promise<ReportAnalysis> {
  const { data } = await client.patch<ReportAnalysis>(`/reports/${reportId}/critical-marker`, { status })
  return data
}

export async function confirmReportMetric(
  reportId: string,
  metricId: string,
): Promise<ReportAnalysis['metrics'][number]> {
  const { data } = await client.post<ReportAnalysis['metrics'][number]>(
    `/reports/${reportId}/metrics/${metricId}/confirm`,
  )
  return data
}

export async function correctReportMetric(
  reportId: string,
  metricId: string,
  payload: { name: string; value: number; unit: string; reference_range: string; method: string },
): Promise<ReportAnalysis['metrics'][number]> {
  const { data } = await client.patch<ReportAnalysis['metrics'][number]>(
    `/reports/${reportId}/metrics/${metricId}`,
    payload,
  )
  return data
}

export async function downloadReportSource(reportId: string): Promise<Blob> {
  const { data } = await client.get<Blob>(`/reports/${reportId}/source`, {
    responseType: 'blob',
  })
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
    action_id: actionId,
  })
  return data
}

export async function fetchCurrentExperiment(): Promise<Experiment> {
  const { data } = await client.get<Experiment>('/experiments/current')
  return data
}

export async function transitionExperiment(
  experimentId: string,
  transition: ExperimentTransition,
): Promise<Experiment> {
  const { data } = await client.post<Experiment>(`/experiments/${experimentId}/${transition}`)
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
    missing_reason?: string
    discomfort_level?: string
    discomfort_details?: string
    unplanned_event?: string
    notes?: string
  },
): Promise<{ message: string }> {
  const { data } = await client.post<{ message: string }>(
    `/experiments/${experimentId}/observations`,
    payload,
  )
  return data
}

export async function downloadObservationTemplate(
  experimentId: string,
  format: 'csv' | 'json',
): Promise<Blob> {
  const { data } = await client.get<Blob>(
    `/experiments/${experimentId}/observations/template`,
    { params: { format }, responseType: 'blob' },
  )
  return data
}

export async function importObservations(
  experimentId: string,
  format: 'csv' | 'json',
  content: string,
): Promise<ObservationImportResult> {
  const { data } = await client.post<ObservationImportResult>(
    `/experiments/${experimentId}/observations/import`,
    { format, content },
  )
  return data
}

export async function fetchExperimentResult(experimentId: string): Promise<ExperimentResult> {
  const { data } = await client.get<ExperimentResult>(`/experiments/${experimentId}/result`)
  return data
}

export async function downloadExperimentExport(experimentId: string): Promise<Blob> {
  const { data } = await client.get<Blob>(`/experiments/${experimentId}/export`, {
    responseType: 'blob',
  })
  return data
}

export async function saveNextStep(
  experimentId: string,
  code: NextStepCode,
): Promise<{ experiment_id: string; code: NextStepCode; selected_at: string }> {
  const { data } = await client.post<{
    experiment_id: string
    code: NextStepCode
    selected_at: string
  }>(`/experiments/${experimentId}/next-step`, { code })
  return data
}

export async function fetchContentItems(filters: {
  content_type?: ContentType
  status?: ContentStatus
  q?: string
} = {}): Promise<ContentItem[]> {
  const { data } = await client.get<ContentItem[]>('/admin/content/items', { params: filters })
  return data
}

export async function fetchEvidenceSources(): Promise<EvidenceSource[]> {
  const { data } = await client.get<EvidenceSource[]>('/admin/content/sources')
  return data
}

export async function reviewContentItem(
  itemId: string,
  payload: {
    decision: 'approved' | 'rejected'
    reviewer_qualification: string
    review_scope: string
    evidence_ref: string
    attested: true
    notes: string
  },
): Promise<ContentReview> {
  const { data } = await client.post<ContentReview>(`/admin/content/items/${itemId}/review`, payload)
  return data
}

export async function changeContentItemStatus(
  itemId: string,
  action: 'publish' | 'retire' | 'rollback',
): Promise<ContentItem> {
  const { data } = await client.post<ContentItem>(`/admin/content/items/${itemId}/${action}`)
  return data
}

export async function validateContentItems(itemIds: string[]): Promise<BulkContentValidation> {
  const { data } = await client.post<BulkContentValidation>('/admin/content/validate', { item_ids: itemIds })
  return data
}

export async function compareContentVersions(
  contentType: ContentType,
  code: string,
  fromVersion: string,
  toVersion: string,
): Promise<ContentComparison> {
  const { data } = await client.get<ContentComparison>(
    `/admin/content/${contentType}/${code}/compare`,
    { params: { from_version: fromVersion, to_version: toVersion } },
  )
  return data
}

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail.message === 'string') return detail.message
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') {
      return detail[0].msg.replace(/^Value error, /, '')
    }
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return '网络响应超时，请检查连接后重试。'
    }
    if (!error.response) return '暂时无法连接服务，请检查网络后重试。'
    return error.message || '请求失败'
  }
  return error instanceof Error ? error.message : '发生未知错误'
}
