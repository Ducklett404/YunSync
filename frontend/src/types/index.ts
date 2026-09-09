export interface HealthMetric {
  id: string
  code: string
  name: string
  value: number
  unit: string
  reference_range: string
  flag: 'normal' | 'attention' | string
  confirmed: boolean
}

export interface ActionTemplate {
  id: string
  code: string
  title: string
  category: string
  description: string
  evidence_summary: string
  suitable_if: string
  safety_note: string
  primary_metric: string
  risk_level: string
  score: number
  rank_reason: string
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
  synthetic_notice: string
  metrics: HealthMetric[]
}
