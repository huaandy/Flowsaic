// Shapes the UI works with (the pages were designed around these). src/api/adapters.ts converts
// between them and the backend's shapes in src/api/types.ts.
import type { ApiScheduleSection } from './api/types'

export type Page = 'Dashboard' | 'Degree Progress' | 'Course Catalog' | 'Semester Planner' | 'My Calendar' | 'Create Schedule' | 'AI Advisor' | 'Advisor Dashboard' | 'My Profile' | 'Scheduling Preferences' | 'Settings' | 'Help & Support'

export type DayKey = 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri'
export type ScheduleStatus = 'Draft Saved' | 'Pending Approval' | 'Approved'
export type EventCategory = 'Academic' | 'Work' | 'Personal / Study' | 'Extracurricular'
/** time/endTime are display strings like "9:00 AM". Personal events use the backend event id. */
export type CalendarEvent = { id: string; day: DayKey; time: string; endTime: string; title: string; meta: string; tone: string; type: 'Class' | 'Personal commitment'; category: EventCategory; recurrence: 'None' | 'Weekly'; priority: 'Low' | 'Normal' | 'High'; fixed: boolean; readOnly: boolean }
/** day: 0 = Monday ... 4 = Friday; start/end in decimal hours (14.5 = 2:30 PM). */
export type ScheduleMeeting = { day: number; start: number; end: number }

export type StudentProfile = { name: string; email: string; university: string; major: string; minor: string; degree: string; standing: string; graduation: string; photo: string }
export type SchedulingPreferences = { time: string; days: string[]; minCredits: number; maxCredits: number; delivery: string[]; distance: string; minRating: number; flexibility: 'Flexible' | 'Balanced' | 'Strict' }
export type AppSettings = { emailNotifications: boolean; pushNotifications: boolean; advisorUpdates: boolean; scheduleAlerts: boolean; appearance: 'Light' | 'Dark' | 'System'; highContrast: boolean; largerText: boolean; reduceMotion: boolean; profileVisibility: 'Private' | 'Advisors only' | 'University community' }

/** The schedule being built in Create Schedule (one section per course). */
export type DraftSection = ApiScheduleSection
export type ScheduleDraft = { scheduleId: string | null; name: string; source: 'manual' | 'ai'; sections: DraftSection[] }
export const EMPTY_DRAFT: ScheduleDraft = { scheduleId: null, name: '', source: 'manual', sections: [] }
