// The one way the frontend talks to the backend. Every call goes to /api/... on this origin
// (Vite forwards it to FastAPI), with the session cookie. Errors are { error: code }.
import type {
  ApiAdvisorReply, ApiAdvisorTurn, ApiCheckResult, ApiCompletedCourse, ApiCourseDetail, ApiCourseList, ApiEvent,
  ApiEventIn, ApiPreferences, ApiProgress, ApiRefreshRun, ApiRun, ApiSaveSchedule, ApiScheduleDetail,
  ApiScheduleSummary, ApiSearch, ApiSettings, ApiStudent, ApiSuggestRequest, ApiSuggestResult, ApiTerm,
  CourseQuery, Uuid,
} from './types'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  code: string
  body: Record<string, unknown>
  constructor(status: number, code: string, body: Record<string, unknown> = {}) {
    super(code)
    this.status = status
    this.code = code
    this.body = body
  }
}

let unauthorizedHandler: (() => void) | null = null
/** Called on any 401 (the session ended or never started). The app sends the user to sign-in. */
export function onUnauthorized(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

type Query = Record<string, string | number | boolean | undefined | null>

function withQuery(path: string, query?: Query) {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `${path}?${text}` : path
}

export async function request<T>(method: string, path: string, options: { body?: unknown; query?: Query; quiet401?: boolean } = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(BASE + withQuery(path, options.query), {
      method,
      credentials: 'include',
      headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch {
    throw new ApiError(0, 'network_error')
  }
  if (response.status === 204) return undefined as T
  let data: unknown = null
  try {
    data = await response.json()
  } catch {
    data = null
  }
  if (!response.ok) {
    const body = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    // No { error } body on a 502-504 = the Vite proxy couldn't reach the backend at all.
    const code = typeof body.error === 'string' ? body.error
      : [502, 503, 504].includes(response.status) ? 'network_error' : response.status >= 500 ? 'server_error' : 'request_failed'
    if (response.status === 401 && !options.quiet401) unauthorizedHandler?.()
    throw new ApiError(response.status, code, body)
  }
  return data as T
}

const get = <T>(path: string, query?: Query) => request<T>('GET', path, { query })
const post = <T>(path: string, body?: unknown) => request<T>('POST', path, { body: body ?? {} })
const put = <T>(path: string, body: unknown) => request<T>('PUT', path, { body })
const del = (path: string) => request<void>('DELETE', path)

export const api = {
  // sign-in
  login: (email: string, password: string) => request<ApiStudent>('POST', '/auth/login', { body: { email, password }, quiet401: true }),
  logout: () => request<void>('POST', '/auth/logout', { quiet401: true }),
  me: (quiet401 = false) => request<ApiStudent>('GET', '/me', { quiet401 }),

  // the student's record
  progress: () => get<ApiProgress>('/me/progress'),
  completedCourses: () => get<ApiCompletedCourse[]>('/me/completed-courses'),
  connectMysau: () => post<{ runs: ApiRun[] }>('/me/connect-mysau', { fetch: ['sections', 'audit'] }),
  refreshRun: (id: Uuid) => get<ApiRefreshRun>(`/data/refresh/${id}`),

  // catalog
  terms: () => get<ApiTerm[]>('/terms'),
  courses: (query: CourseQuery) => get<ApiCourseList>('/courses', query),
  course: (id: Uuid, termId?: Uuid) => get<ApiCourseDetail>(`/courses/${id}`, { term_id: termId }),
  search: (q: string, limit = 8) => get<ApiSearch>('/search', { q, limit }),

  // schedules
  check: (termId: Uuid, sectionIds: Uuid[]) => post<ApiCheckResult>('/schedules/check', { term_id: termId, section_ids: sectionIds }),
  schedules: () => get<ApiScheduleSummary[]>('/schedules'),
  schedule: (id: Uuid) => get<ApiScheduleDetail>(`/schedules/${id}`),
  createSchedule: (body: ApiSaveSchedule) => post<ApiScheduleDetail>('/schedules', body),
  updateSchedule: (id: Uuid, body: ApiSaveSchedule) => put<ApiScheduleDetail>(`/schedules/${id}`, body),
  deleteSchedule: (id: Uuid) => del(`/schedules/${id}`),

  // planning
  events: () => get<ApiEvent[]>('/me/events'),
  createEvent: (body: ApiEventIn) => post<ApiEvent>('/me/events', body),
  updateEvent: (id: Uuid, body: ApiEventIn) => put<ApiEvent>(`/me/events/${id}`, body),
  deleteEvent: (id: Uuid) => del(`/me/events/${id}`),
  preferences: () => get<ApiPreferences>('/me/preferences'),
  savePreferences: (body: Partial<ApiPreferences>) => put<ApiPreferences>('/me/preferences', body),
  settings: () => get<ApiSettings>('/me/settings'),
  saveSettings: (body: Partial<ApiSettings>) => put<ApiSettings>('/me/settings', body),

  // Flow
  advisor: (message: string, history: ApiAdvisorTurn[]) => post<ApiAdvisorReply>('/ai/advisor', { message, history }),
  suggest: (body: ApiSuggestRequest) => post<ApiSuggestResult>('/ai/suggest', body),
}
