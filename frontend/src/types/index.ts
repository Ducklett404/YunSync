export interface HealthMetric {
  id: string
  code: string
  name: string
  value: number
  unit: string
  reference_range: string
  method: string
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
  measured_at: string
  unit_projection?: {
    status: 'unconfirmed' | 'as_reported' | 'converted' | 'unsupported_unit' | 'outside_catalog' | 'identity_conflict' | 'invalid_value'
    standard_unit: string | null
    standard_value: number | null
    rule_version: string
  }
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
  recorded: boolean
  completed: boolean
  observation: Observation | null
}

export type MissingReason =
  | 'forgot'
  | 'device_unavailable'
  | 'physical_discomfort'
  | 'unplanned_event'
  | 'other'

export type DiscomfortLevel = 'none' | 'mild' | 'significant'

export interface Observation {
  id: string
  observed_on: string
  treatment: boolean
  completed: boolean
  steps_30m: number | null
  sleep_hours: number | null
  sugary_drinks: number | null
  subjective_score: number | null
  missing_reason: MissingReason | null
  discomfort_level: DiscomfortLevel
  discomfort_details: string | null
  unplanned_event: string | null
  notes: string | null
}

export interface ObservationImportResult {
  message: string
  imported_days: number
  created_days: number
  updated_days: number
}

export type ExperimentTransition = 'pause' | 'resume' | 'terminate' | 'complete'

export type NextStepCode = 'keep' | 'adjust' | 'extend' | 'stop'

export interface NextStepOption {
  code: NextStepCode
  title: string
  description: string
  recommended: boolean
  selected: boolean
}

export interface AnalysisPoint {
  observed_on: string
  group: 'reminder' | 'routine'
  value: number
  outlier: boolean
}

export interface ExperimentResult {
  experiment_id: string
  analysis_version: string
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
  treatment_median: number | null
  control_median: number | null
  observed_difference: number | null
  completion_rate: number
  effective_rate: number
  valid_days: number
  missing_days: number
  missing_reason_counts: Record<string, number>
  bootstrap_ci_lower: number | null
  bootstrap_ci_upper: number | null
  bootstrap_iterations: number
  outlier_count: number
  outlier_days: string[]
  sensitivity_difference: number | null
  analysis_points: AnalysisPoint[]
  explanation: string
  explanation_source: string
  explanation_policy_version: string
  recommended_next_step: NextStepCode
  next_step_options: NextStepOption[]
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
  status_label: string
  start_date: string
  end_date: string
  randomization_seed: number
  schedule_version: string
  schedule_locked_at: string
  started_at: string
  paused_at: string | null
  terminated_at: string | null
  completed_at: string | null
  next_step: NextStepCode | null
  next_step_selected_at: string | null
  progress: number
  recorded_days: number
  completed_days: number
  allowed_transitions: ExperimentTransition[]
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
  institution: string
  examined_at: string | null
  source: string
  status: string
  critical_marker_status: 'unknown' | 'no' | 'yes'
  critical_marker_reviewed_at: string | null
  storage_provider: string
  source_available: boolean
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

export interface ReportSummary {
  report_id: string
  filename: string
  status: string
  ocr_status: string
  critical_marker_status: 'unknown' | 'no' | 'yes'
  created_at: string
}

export interface ReportList {
  items: ReportSummary[]
  total: number
  limit: number
  offset: number
}

export interface MetricHistoryPoint {
  report_id: string
  metric_id: string
  report_created_at: string
  examined_at: string | null
  institution: string
  measured_at: string
  value: number
  unit: string
  reference_range: string
  method: string
  standard_value: number | null
  projection_status: NonNullable<HealthMetric['unit_projection']>['status']
}

export interface MetricHistoryPair {
  previous_report_id: string
  current_report_id: string
  status: 'numeric_only' | 'not_projected' | 'duplicate_in_report' | 'metadata_missing' | 'method_changed' | 'reference_range_missing' | 'reference_range_changed'
  arithmetic_change: number | null
  direction: 'higher' | 'lower' | 'same' | null
  reference_range_changed: boolean
  source_unit_changed: boolean
  institution_changed: boolean
  method_changed: boolean
  limitations: string[]
}

export interface MetricHistory {
  rule_version: string
  reports_considered: number
  report_limit: number
  series: {
    code: string
    name: string
    standard_unit: string
    points: MetricHistoryPoint[]
    latest_pair: MetricHistoryPair | null
  }[]
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
  reminder_enabled: boolean
  reminder_time: string
  high_risk: boolean
  screening_status: 'pending' | 'eligible' | 'needs_professional_review' | string
  screening_answers: Record<string, boolean>
  screened_at: string | null
}

export type FoodSafetyAnswerStatus = 'unknown' | 'none' | 'present'
export type FoodSafetySpecialStatus = 'unknown' | 'none' | 'pregnant' | 'breastfeeding' | 'other'

export interface FoodSafetyProfileInput {
  allergy_status: FoodSafetyAnswerStatus
  allergens: string[]
  medication_status: FoodSafetyAnswerStatus
  medications: string[]
  condition_status: FoodSafetyAnswerStatus
  conditions: string[]
  liver_kidney_status: FoodSafetyAnswerStatus
  liver_kidney_conditions: string[]
  clinician_restriction_status: FoodSafetyAnswerStatus
  clinician_restrictions: string[]
  special_status: FoodSafetySpecialStatus
  special_details: string
}

export interface FoodSafetyProfile extends FoodSafetyProfileInput {
  readiness: 'needs_information' | 'needs_professional_review' | 'awaiting_review_rules'
  updated_at: string | null
}

export interface SafetyDecision {
  decision: 'urgent_care' | 'consult_professional' | 'complete_information' | 'awaiting_review_rules' | 'ready_general_guidance'
  tier: 'A' | 'B' | 'C' | null
  can_generate_plan: boolean
  rule_version: string
  message: string
  missing_items: string[]
}

export interface CarePlanRequest {
  selected_metric_codes: string[]
  servings: number
  start_on: string | null
  max_minutes: number | null
  max_budget_yuan_per_serving: number | null
  available_cookware: string[]
  preferred_taste: string
  region: string
  unavailable_ingredient_codes: string[]
}

export interface CarePlan {
  id: string
  report_id: string
  status: 'READY' | 'ACTIVE' | 'PAUSED' | 'SUPERSEDED'
  version: number
  previous_plan_id: string | null
  pause_reason: string | null
  superseded_at: string | null
  created_at: string
  activated_at: string | null
  paused_at: string | null
  snapshot: {
    schema_version: string
    report_date: string
    safety_rule_version: string
    goals: { metric_id: string; code: string; name: string; value: number; unit: string; reference_range: string; report_date: string; statement: string }[]
    recipes: {
      code: string; version: string; title: string; servings: number; score: number
      score_breakdown: Record<string, number>
      matched_metric_codes: string[]; reason: string; goal_statement: string
      materials: { code: string; version: string; title: string; grams: number; edible_part: string; preparation: string; substituted_for: string | null; alternatives: { code: string; version: string; title: string; grams: number; note: string }[] }[]
      preprocessing: string[]
      steps: { order: number; instruction: string; duration_minutes: number; heat: string; cookware: string[] }[]
      frequency: string; max_weekly_uses: number; cycle: string; serving_note: string; caution: string
      nutrition_tags: string[]; dining_alternatives: string[]; total_minutes: number; estimated_cost_yuan_per_serving: number | null
      source_refs: string[]; review_id: string; published_at: string
    }[]
    schedule: { day: number; date: string; recipe_code: string; recipe_version: string; servings: number }[]
    shopping_list: { code: string; version: string; title: string; total_grams: number; edible_part: string }[]
    contraindication_refs: string[]
    source_refs: string[]
    constraints: CarePlanRequest
    explanation_mode: 'reviewed_template'
    ranking_policy_version: string
    general_principle: string
    professional_consultation: string
    follow_up: string
    disclaimer: string
  }
}

export interface AdherenceLogInput {
  status: 'completed' | 'skipped' | 'replaced'
  replacement: string
  discomfort: boolean
  note: string
}

export interface AdherenceLog extends AdherenceLogInput {
  id: string
  plan_id: string
  day: number
  created_at: string
  updated_at: string
}

export interface FollowUpReminderInput {
  remind_on: string
  basis: 'doctor' | 'report' | 'personal'
  note: string
  enabled: boolean
}

export interface FollowUpReminder extends FollowUpReminderInput {
  id: string
  plan_id: string
  due: boolean
  updated_at: string
}

export interface FollowUpComparison {
  previous_report_id: string
  current_report_id: string
  previous_examined_at: string | null
  current_examined_at: string | null
  days_between: number | null
  rule_version: string
  limitation: string
  adherence_summary?: {
    scheduled_days: number
    logged_days: number
    completed_days: number
    skipped_days: number
    replaced_days: number
    discomfort_recorded: boolean
    limitation: string
  }
  metrics: {
    code: string
    name: string
    standard_unit: string
    previous: MetricHistoryPoint | null
    current: MetricHistoryPoint | null
    pair: MetricHistoryPair | null
    status: 'paired' | 'only_previous' | 'only_current'
  }[]
}

export interface PlanRevision {
  id: string
  old_plan_id: string
  new_plan_id: string
  new_report_id: string
  changes: { type: 'continued' | 'reduced' | 'increased' | 'replaced' | 'paused' | 'added'; subject: string; reason: string }[]
  comparison: FollowUpComparison
  created_at: string
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

export interface PrivacyRequest {
  id: string
  request_type: 'account_deletion'
  status: 'pending' | 'cancelled' | 'completed'
  requested_at: string
  execute_after: string
  cancelled_at: string | null
  completed_at: string | null
  attempt_count: number
}

export interface PrivacyStatus {
  active_consent: boolean
  pending_deletion: PrivacyRequest | null
  deletion_grace_hours: number
}

export type ContentType = 'ingredient' | 'recipe' | 'contraindication'
export type ContentStatus = 'draft' | 'reviewed' | 'published' | 'retired'

export interface EvidenceSource {
  id: string
  code: string
  version: string
  ref: string
  title: string
  publisher: string
  url_or_archive_ref: string
  published_on: string
  jurisdiction: string
  content_hash: string
  status: 'active' | 'superseded' | 'withdrawn'
  checked_at: string
  created_at: string
}

export interface ContentItem {
  id: string
  content_type: ContentType
  code: string
  version: string
  title: string
  payload: Record<string, unknown>
  status: ContentStatus
  is_active: boolean
  created_by: string
  created_at: string
  published_at: string | null
  retired_at: string | null
}

export interface ContentReview {
  id: string
  item_id: string
  decision: 'approved' | 'rejected'
  reviewer_id: string
  reviewer_qualification: string
  review_scope: string
  evidence_ref: string
  attested: boolean
  notes: string
  created_at: string
}

export interface ContentValidationResult {
  item_id: string
  content_type: ContentType | null
  code: string | null
  version: string | null
  valid: boolean
  errors: string[]
  warnings: string[]
}

export interface BulkContentValidation {
  valid: boolean
  results: ContentValidationResult[]
}

export interface ContentComparison {
  content_type: ContentType
  code: string
  from_version: string
  to_version: string
  changed_fields: Record<string, { from: unknown; to: unknown }>
}
