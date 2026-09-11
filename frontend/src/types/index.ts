export interface HealthMetric {
  id: string
  code: string
  name: string
  value: number
  unit: string
  reference_range: string
  flag: 'normal' | 'attention' | string
  confirmed: boolean
  review_status: 'pending' | 'confirmed' | 'corrected' | string
  raw_text: string
  extracted_value: number | null
  extracted_unit: string
  extracted_reference_range: string
  confidence: number
  source_page: number
  source_bbox: number[]
}

export interface ActionTemplate {
  id: string
  code: string
  template_version: string
  review_status: string
  review_scope: string
  review_label: string
  title: string
  category: string
  description: string
  evidence_summary: string
  suitable_if: string
  safety_note: string
  primary_metric: string
  risk_level: string
  score: number
  score_components: {
    evidence_weight: number
    observability_weight: number
    ease_weight: number
    evidence_points: number
    observability_points: number
    ease_points: number
    total: number
  }
  ranking_policy_version: string
  rank_reason: string
  explanation: string
  explanation_source: string
  explanation_policy_version: string
  safety_checks: string[]
}

export interface ScheduleDay {
  day: number
  date: string
  treatment: boolean
  label: string
  completed: boolean
}

export interface ExperimentResult {
  experiment_id: string
  status: string
  message: string
  metric_code: string
  metric_label: string
  metric_unit: string
  improvement_direction: 'higher' | 'lower' | string
  treatment_days: number
  control_days: number
  treatment_average: number | null
  control_average: number | null
  observed_difference: number | null
  completion_rate: number
  caveats: string[]
}

export interface Experiment {
  id: string
  user_id?: string
  action_id?: string
  action_code: string
  action_title: string
  primary_metric: string
  status: string
  start_date: string
  end_date: string
  progress: number
  schedule: ScheduleDay[]
  result?: ExperimentResult
}

export interface DashboardData {
  user: {
    id: string
    nickname: string
    age_range: string
    goal: string
    high_risk: boolean
  } | null
  report: {
    id: string
    filename: string
    status: string
    source: string
  } | null
  metrics: HealthMetric[]
  experiment: Experiment | null
  actions: ActionTemplate[]
  notice: string
}

export interface ReportAnalysis {
  report_id: string
  filename: string
  source: string
  status: string
  storage_provider: string
  content_type: string
  file_size: number
  ocr_provider: string
  ocr_status: 'processing' | 'completed' | 'failed' | string
  ocr_attempts: number
  ocr_error_code: string | null
  ocr_page_count: number
  processed_at: string | null
  synthetic_notice: string
  metrics: HealthMetric[]
}

export interface UserProfile {
  id: string
  nickname: string
  role: 'participant' | 'reviewer' | string
  age_range: string
  goal: string
  sleep_schedule: string
  activity_baseline: string
  constraints: string
  preferences: string
  high_risk: boolean
  screening_status: 'pending' | 'eligible' | 'needs_professional_review' | string
  screening_answers: Record<string, boolean>
  screened_at: string | null
}

export interface DemoSession {
  access_token: string
  token_type: string
  expires_at: string
  user: UserProfile
}

export interface ConsentRecord {
  id: string
  version: string
  status: string
  accepted_at: string
  withdrawn_at: string | null
}

export interface ConsentNotice {
  version: string
  title: string
  items: string[]
}

export interface AccountStatus {
  user: UserProfile
  consent: ConsentRecord | null
  required_consent_version: string
}
