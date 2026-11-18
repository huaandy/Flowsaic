// Backend response and request shapes, snake_case as the API sends them.
// The source of truth is the backend's /docs (http://127.0.0.1:8000/docs). Keep these in step.

export type Uuid = string
/** Letters from MTWRFSU (R = Thursday). */
export type DayLetters = string
/** 24-hour "HH:MM". */
export type HHMM = string

export type ApiPlan = { id: Uuid; name: string; catalog_year: string }

export type ApiStudent = {
  id: Uuid
  name: string
  email: string
  classification: string | null
  major: string | null
  catalog_year: string | null
  degree_plan: ApiPlan | null
  has_hold: boolean
  total_hours_earned: number | null
  total_hours_needed: number | null
  audit_refreshed_at: string | null
  connected_mysau: boolean
}

export type ApiTerm = { id: Uuid; code: string; name: string; is_current_registration: boolean }

export type ApiCompletedCourse = {
  course_code: string
  title: string | null
  status: 'completed' | 'in_progress'
  grade: string | null
  credits: number | null
  term: string | null
  source: string
  requirement_name: string | null
}

export type ProgressCourseStatus = 'passed' | 'in_progress' | 'needed' | 'option' | 'counted_elsewhere'
export type RequirementStatus = 'met' | 'in_progress' | 'not_met' | 'not_tracked'

export type ApiProgressCourse = { code: string; title: string | null; status: ProgressCourseStatus }
export type ApiProgressElective = {
  text: string
  hours_required: number | null
  hours_done: number
  hours_in_progress: number
  status: string
  courses: ApiProgressCourse[]
}
export type ApiRequirementNode = {
  name: string
  rule: string
  status: RequirementStatus
  hours_done: number
  hours_in_progress: number
  hours_required: number | null
  courses: ApiProgressCourse[]
  note: string | null
  electives: ApiProgressElective[]
  children: ApiRequirementNode[]
}
export type ApiEligibleCourse = {
  code: string
  title: string | null
  credits: number
  kind: 'required' | 'choice' | 'elective'
  counts_toward: string[]
  sections: number
  seats_open: number
}
export type ApiBlockedCourse = { code: string; title: string | null; missing_prereqs: string[][]; counts_toward: string[] }
export type ApiProgress = {
  source: 'audit' | 'degree_plan' | 'none'
  plan: { name: string; catalog_year: string } | null
  term: { id: Uuid; name: string } | null
  hours: { earned: number; in_progress: number; required: number | null }
  requirements: ApiRequirementNode[]
  can_take: ApiEligibleCourse[]
  blocked: ApiBlockedCourse[]
  open_electives: string[]
}

export type Delivery = 'in_person' | 'online'
export type Eligibility = 'eligible' | 'missing_prereq' | 'completed' | 'in_progress'

export type ApiCatalogSection = {
  id: Uuid
  section_number: string
  instructor: string
  location: string | null
  building: string | null
  room: string | null
  days: DayLetters | null
  start_time: HHMM | null
  end_time: HHMM | null
  division: string | null
  enrolled: number
  capacity: number
  seats_open: number
  active: boolean
  delivery: Delivery
}

export type ApiCatalogCourse = {
  id: Uuid
  code: string
  title: string
  department: string | null
  credits: number
  description: string | null
  other_requirements: string | null
  level: number
  prereqs: string[][]
  eligibility: Eligibility
  missing_prereqs: string[][]
  on_my_plan: boolean
  requirement_names: string[]
  offered: boolean
  seats_open: number
  sections: ApiCatalogSection[]
}

export type ApiCourseList = { total: number; courses: ApiCatalogCourse[]; departments: string[] }
export type ApiCourseDetail = ApiCatalogCourse & { term: ApiTerm | null }

export type CourseQuery = {
  term_id: Uuid
  search?: string
  department?: string
  on_my_plan?: boolean
  eligible_only?: boolean
  level?: number
  delivery?: Delivery
  open_only?: boolean
  credits?: number
  days?: string
  limit?: number
  offset?: number
}

export type ApiSearchResult = {
  course_id: Uuid
  code: string
  title: string
  snippet: string | null
  match_type: 'code' | 'title' | 'description'
  offered: boolean
}
export type ApiSearch = { query: string; results: ApiSearchResult[] }

export type CheckCode =
  | 'time_overlap' | 'missing_prereq' | 'duplicate_course' | 'commitment_overlap'
  | 'already_completed' | 'section_full' | 'not_on_plan' | 'over_credit_limit' | 'commitment_overlap_flexible'

export type ApiCheckItem = { code: CheckCode | string; section_ids: Uuid[]; message: string; event_ids?: Uuid[] }
export type ApiCheckResult = { conflicts: ApiCheckItem[]; warnings: ApiCheckItem[] }

/** A section as /schedules and /ai return it (with its course code and title). */
export type ApiScheduleSection = {
  id: Uuid
  code: string
  section_number: string
  title: string | null
  credits: number
  days: DayLetters | null
  start_time: HHMM | null
  end_time: HHMM | null
  instructor: string
  location: string | null
  enrolled?: number
  capacity: number
  seats_open: number
  active?: boolean
}

export type ApiScheduleSummary = {
  id: Uuid
  name: string
  term: { id: Uuid; name: string }
  source: 'manual' | 'ai'
  created_at: string
  credits: number
  section_count: number
}
export type ApiScheduleDetail = ApiScheduleSummary & ApiCheckResult & { sections: ApiScheduleSection[] }
export type ApiSaveSchedule = { name: string; term_id: Uuid; section_ids: Uuid[]; source: 'manual' | 'ai' }

export type EventCategory = 'work' | 'personal_study' | 'extracurricular'
export type ApiEventIn = {
  title: string
  day: 'M' | 'T' | 'W' | 'R' | 'F'
  start_time: HHMM
  end_time: HHMM
  location: string | null
  category: EventCategory
  recurrence: 'none' | 'weekly'
  priority: 'low' | 'normal' | 'high'
  fixed: boolean
}
export type ApiEvent = ApiEventIn & { id: Uuid; created_at: string; updated_at: string }

export type PreferredTime = 'morning' | 'midday' | 'afternoon' | 'evening' | 'none'
export type ApiPreferences = {
  preferred_time: PreferredTime
  preferred_days: DayLetters
  min_credits: number
  max_credits: number
  delivery: Delivery[]
  flexibility: 'flexible' | 'balanced' | 'strict'
  updated_at: string | null
}

export type ApiSettings = {
  email_notifications: boolean
  push_notifications: boolean
  advisor_updates: boolean
  schedule_alerts: boolean
  appearance: 'light' | 'dark' | 'system'
  high_contrast: boolean
  larger_text: boolean
  reduce_motion: boolean
  profile_visibility: 'private' | 'advisors' | 'community'
  photo: string | null
  updated_at: string | null
}

export type ApiProposal = ApiCheckResult & {
  name: string
  explanation: string
  term_id: Uuid | null
  section_ids: Uuid[]
  sections: ApiScheduleSection[]
  credits: number
}
export type ApiAdvisorTurn = { role: 'user' | 'assistant'; text: string }
/** suggestions: up to 3 quick replies for buttons (send one as the next message). */
export type ApiAdvisorReply = { reply: string; memory: string; proposals: ApiProposal[]; suggestions: string[]; tools_used: string[] }

export type ApiSuggestRequest = {
  term_id?: Uuid
  target_credits?: number
  min_credits?: number
  max_credits?: number
  preferred_time?: PreferredTime
  preferred_days?: DayLetters
  delivery?: Delivery[]
  notes?: string
}
export type ApiSuggestResult = ApiCheckResult & {
  section_ids: Uuid[]
  sections: ApiScheduleSection[]
  explanation: string
}

export type ApiRun = { id: Uuid; kind: string }
export type ApiRefreshRun = {
  id: Uuid
  kind: string
  status: 'running' | 'ok' | 'failed'
  started_at: string
  finished_at: string | null
  rows_changed: number | null
  error: string | null
}
