// Backend shapes <-> the UI's shapes. Day letters (MTWRF, R = Thursday) <-> the UI's day keys
// and day index (0 = Monday), "HH:MM" <-> decimal hours and "2:10 PM".
import type {
  ApiCatalogCourse, ApiCatalogSection, ApiEvent, ApiEventIn, ApiPreferences, ApiScheduleSection, ApiSettings,
  Delivery, EventCategory as ApiCategory, PreferredTime,
} from './types'
import type { AppSettings, CalendarEvent, DayKey, DraftSection, EventCategory, ScheduleMeeting, SchedulingPreferences } from '../types'

export const DAY_KEYS: DayKey[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
const LETTERS = 'MTWRF'
const DAY_NAMES: Record<string, string> = { M: 'Mon', T: 'Tue', W: 'Wed', R: 'Thu', F: 'Fri', S: 'Sat', U: 'Sun' }

export const letterToKey = (letter: string): DayKey => DAY_KEYS[LETTERS.indexOf(letter)] ?? 'Mon'
export const keyToLetter = (key: DayKey) => LETTERS[DAY_KEYS.indexOf(key)] as ApiEventIn['day']
/** "MWF" -> "Mon/Wed/Fri" */
export const daysLabel = (letters: string | null) => (letters ? letters.split('').map(l => DAY_NAMES[l] ?? l).join('/') : '')
/** Today's weekday key, or null on a weekend. */
export function todayKey(date = new Date()): DayKey | null {
  const weekday = date.getDay()
  return weekday >= 1 && weekday <= 5 ? DAY_KEYS[weekday - 1] : null
}

export function hhmmToHours(value: string) {
  const [hours, minutes] = value.split(':').map(Number)
  return hours + minutes / 60
}
export function hoursToHHMM(value: number) {
  const hours = Math.floor(value)
  const minutes = Math.round((value - hours) * 60)
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}
/** "14:10" -> "2:10 PM" */
export function hhmmToDisplay(value: string) {
  const [hourText, minute] = value.split(':')
  const hour = Number(hourText)
  return `${hour % 12 || 12}:${minute} ${hour >= 12 ? 'PM' : 'AM'}`
}
/** "2:10 PM" -> "14:10" */
export function displayToHHMM(value: string) {
  const [clock, period] = value.split(' ')
  const [hourText, minute] = clock.split(':')
  let hour = Number(hourText) % 12
  if (period === 'PM') hour += 12
  return `${String(hour).padStart(2, '0')}:${minute}`
}
export const displayToHours = (value: string) => hhmmToHours(displayToHHMM(value))

type Timed = { days: string | null; start_time: string | null; end_time: string | null }

/** No days or times = online or TBA: never on the timetable. */
export const isOnlineOrTba = (section: Timed) => !(section.days && section.start_time && section.end_time)

/** Weekday meetings (M-F only) in the timetable's day index and decimal hours. */
export function meetings(section: Timed): ScheduleMeeting[] {
  if (isOnlineOrTba(section)) return []
  return section.days!.split('').filter(letter => LETTERS.includes(letter)).map(letter => ({
    day: LETTERS.indexOf(letter), start: hhmmToHours(section.start_time!), end: hhmmToHours(section.end_time!),
  }))
}

/** "MW · 2:10–3:30 PM" style, or "Online / TBA". */
export function scheduleText(section: Timed) {
  if (isOnlineOrTba(section)) return 'Online / TBA'
  const start = hhmmToDisplay(section.start_time!)
  const end = hhmmToDisplay(section.end_time!)
  const sameHalf = start.slice(-2) === end.slice(-2)
  return `${daysLabel(section.days)} · ${sameHalf ? start.slice(0, -3) : start}–${end}`
}

export const placeText = (section: Pick<ApiCatalogSection, 'building' | 'room' | 'location'>) =>
  [section.building, section.room].filter(Boolean).join(' ') || section.location || 'Location TBA'

/** A catalog course + one of its sections -> a schedule-draft section. */
export function draftSection(course: Pick<ApiCatalogCourse, 'code' | 'title' | 'credits'>, section: ApiCatalogSection): DraftSection {
  return {
    id: section.id, code: course.code, section_number: section.section_number, title: course.title,
    credits: course.credits, days: section.days, start_time: section.start_time, end_time: section.end_time,
    instructor: section.instructor, location: placeText(section), enrolled: section.enrolled,
    capacity: section.capacity, seats_open: section.seats_open, active: section.active,
  }
}

/** The section to add when the student hasn't picked one: open seats, then meets in person. */
export function defaultSection(course: ApiCatalogCourse): ApiCatalogSection | undefined {
  const active = course.sections.filter(s => s.active)
  return active.find(s => s.seats_open > 0 && s.delivery === 'in_person') ?? active.find(s => s.seats_open > 0) ?? active[0]
}

const TONES = ['blue', 'purple', 'orange', 'mint']
/** A stable color for a course code (by subject). */
export function toneFor(code: string) {
  const subject = code.split(' ')[0] ?? code
  let hash = 0
  for (const char of subject) hash = (hash * 31 + char.charCodeAt(0)) % 997
  return TONES[hash % TONES.length]
}

/** [["CSCI 3213"], ["MATH 1023", "MATH 1053"]] -> "CSCI 3213 and (MATH 1023 or MATH 1053)" */
export function prereqText(groups: string[][]) {
  if (!groups.length) return 'None'
  return groups.map(group => (group.length > 1 ? `(${group.join(' or ')})` : group[0])).join(' and ')
}

export function deliveryText(sections: ApiCatalogSection[]) {
  const kinds = new Set(sections.filter(s => s.active).map(s => s.delivery))
  if (kinds.size === 2) return 'In person & online'
  return kinds.has('online') ? 'Online' : 'In person'
}

// --- calendar events ---------------------------------------------------------------------------

const CATEGORY_TO_UI: Record<ApiCategory, EventCategory> = { work: 'Work', personal_study: 'Personal / Study', extracurricular: 'Extracurricular' }
const CATEGORY_TO_API: Record<string, ApiCategory> = { Work: 'work', 'Personal / Study': 'personal_study', Extracurricular: 'extracurricular', Academic: 'personal_study' }
export const CATEGORY_TONE: Record<EventCategory, string> = { Academic: 'blue', Work: 'orange', 'Personal / Study': 'purple', Extracurricular: 'mint' }

export function eventToUi(event: ApiEvent): CalendarEvent {
  const category = CATEGORY_TO_UI[event.category]
  return {
    id: event.id, day: letterToKey(event.day), time: hhmmToDisplay(event.start_time), endTime: hhmmToDisplay(event.end_time),
    title: event.title, meta: event.location || 'No location added', tone: CATEGORY_TONE[category],
    type: 'Personal commitment', category, recurrence: event.recurrence === 'weekly' ? 'Weekly' : 'None',
    priority: event.priority === 'high' ? 'High' : event.priority === 'low' ? 'Low' : 'Normal',
    fixed: event.fixed, readOnly: false,
  }
}

export type EventDraft = { day: DayKey; title: string; start: string; end: string; meta: string; category: EventCategory; recurrence: CalendarEvent['recurrence']; priority: CalendarEvent['priority']; fixed: boolean }

/** start/end are "HH:MM" from a time input. */
export function eventDraftToApi(draft: EventDraft): ApiEventIn {
  const location = draft.meta.trim()
  return {
    title: draft.title.trim(), day: keyToLetter(draft.day), start_time: draft.start, end_time: draft.end,
    location: location && location !== 'No location added' ? location : null,
    category: CATEGORY_TO_API[draft.category] ?? 'personal_study', recurrence: draft.recurrence === 'Weekly' ? 'weekly' : 'none',
    priority: draft.priority.toLowerCase() as ApiEventIn['priority'], fixed: draft.fixed,
  }
}

/** A saved schedule's sections as read-only class events (one per weekday meeting). */
export function classEvents(sections: ApiScheduleSection[], tone?: string, prefix = 'class'): CalendarEvent[] {
  return sections.flatMap(section => isOnlineOrTba(section) ? [] : section.days!.split('').filter(l => LETTERS.includes(l)).map(letter => ({
    id: `${prefix}-${section.id}-${letter}`, day: letterToKey(letter), time: hhmmToDisplay(section.start_time!),
    endTime: hhmmToDisplay(section.end_time!), title: `${section.code} · ${section.title ?? ''}`.replace(/ · $/, ''),
    meta: `Section ${section.section_number} · ${section.location || 'Location TBA'}`, tone: tone ?? 'blue', type: 'Class' as const,
    category: 'Academic' as const, recurrence: 'Weekly' as const, priority: 'High' as const, fixed: true, readOnly: true,
  })))
}

// --- preferences and settings -------------------------------------------------------------------

const TIME_TO_UI: Record<PreferredTime, string> = { morning: 'Morning', midday: 'Midday', afternoon: 'Afternoon', evening: 'Evening', none: 'No preference' }
const DELIVERY_TO_UI: Record<Delivery, string> = { in_person: 'Face-to-face', online: 'Online' }

/** Travel distance and minimum rating stay mock (this device only); the rest is the backend's. */
export type MockPreferenceFields = Pick<SchedulingPreferences, 'distance' | 'minRating'>
export const MOCK_PREFERENCE_DEFAULTS: MockPreferenceFields = { distance: 'No preference', minRating: 4 }

export function preferencesToUi(api: ApiPreferences, mock: MockPreferenceFields): SchedulingPreferences {
  return {
    time: TIME_TO_UI[api.preferred_time], days: api.preferred_days.split('').map(letterToKey),
    minCredits: api.min_credits, maxCredits: api.max_credits, delivery: api.delivery.map(d => DELIVERY_TO_UI[d]),
    flexibility: (api.flexibility[0].toUpperCase() + api.flexibility.slice(1)) as SchedulingPreferences['flexibility'], ...mock,
  }
}

export function preferencesToApi(ui: SchedulingPreferences): Partial<ApiPreferences> {
  const time = (Object.entries(TIME_TO_UI).find(([, label]) => label === ui.time)?.[0] ?? 'none') as PreferredTime
  const delivery = (Object.entries(DELIVERY_TO_UI).filter(([, label]) => ui.delivery.includes(label)).map(([key]) => key)) as Delivery[]
  return {
    preferred_time: time,
    preferred_days: DAY_KEYS.filter(day => ui.days.includes(day)).map(keyToLetter).join(''),
    min_credits: ui.minCredits, max_credits: ui.maxCredits,
    delivery: delivery.length ? delivery : ['in_person', 'online'],
    flexibility: ui.flexibility.toLowerCase() as ApiPreferences['flexibility'],
  }
}

const APPEARANCE_TO_UI = { light: 'Light', dark: 'Dark', system: 'System' } as const
const VISIBILITY_TO_UI = { private: 'Private', advisors: 'Advisors only', community: 'University community' } as const

export function settingsToUi(api: ApiSettings): AppSettings {
  return {
    emailNotifications: api.email_notifications, pushNotifications: api.push_notifications, advisorUpdates: api.advisor_updates,
    scheduleAlerts: api.schedule_alerts, appearance: APPEARANCE_TO_UI[api.appearance], highContrast: api.high_contrast,
    largerText: api.larger_text, reduceMotion: api.reduce_motion, profileVisibility: VISIBILITY_TO_UI[api.profile_visibility],
  }
}

export function settingsToApi(ui: AppSettings): Partial<ApiSettings> {
  const appearance = (Object.entries(APPEARANCE_TO_UI).find(([, label]) => label === ui.appearance)?.[0] ?? 'light') as ApiSettings['appearance']
  const visibility = (Object.entries(VISIBILITY_TO_UI).find(([, label]) => label === ui.profileVisibility)?.[0] ?? 'advisors') as ApiSettings['profile_visibility']
  return {
    email_notifications: ui.emailNotifications, push_notifications: ui.pushNotifications, advisor_updates: ui.advisorUpdates,
    schedule_alerts: ui.scheduleAlerts, appearance, high_contrast: ui.highContrast, larger_text: ui.largerText,
    reduce_motion: ui.reduceMotion, profile_visibility: visibility,
  }
}

export const DEFAULT_SETTINGS: AppSettings = { emailNotifications: true, pushNotifications: true, advisorUpdates: true, scheduleAlerts: true, appearance: 'Light', highContrast: false, largerText: false, reduceMotion: false, profileVisibility: 'Advisors only' }
