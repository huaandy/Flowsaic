import { useState } from 'react'
import { DAY_KEYS, type EventDraft, displayToHours, todayKey, toneFor } from '../api/adapters'
import type { ApiCompletedCourse, ApiProgress } from '../api/types'
import { Icon } from '../components/Icon'
import type { CalendarEvent, Page, ScheduleStatus } from '../types'

const timeValue = (time: string) => displayToHours(time) * 60

/** "About 3 semesters" at 15 credits a term, from what's left after this term. */
function semestersLeft(remaining: number) {
  if (remaining <= 0) return 'Requirements covered by current enrollment'
  const terms = Math.ceil(remaining / 15)
  return `About ${terms} ${terms === 1 ? 'semester' : 'semesters'} at 15 credits a term`
}

export function Dashboard({ go, calendarEvents, onAddEvent, scheduleStatus, savedScheduleCount, askFlow, viewSchedule, studentName, progress, completed, termName }: { go: (p: Page) => void; calendarEvents: CalendarEvent[]; onAddEvent: (draft: EventDraft) => Promise<boolean>; scheduleStatus: ScheduleStatus; savedScheduleCount: number; askFlow: (question: string) => void; viewSchedule: () => void; studentName: string; progress: ApiProgress | null; completed: ApiCompletedCourse[]; termName: string }) {
  const [scheduleView, setScheduleView] = useState<'day' | 'week'>('day')
  const [eventDialogOpen, setEventDialogOpen] = useState(false)
  const [newEvent, setNewEvent] = useState({ title: '', time: '12:00', location: '' })
  const [flowQuestion, setFlowQuestion] = useState('')
  const now = new Date()
  const today = todayKey(now)
  const hour = now.getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  // Degree progress, from /me/progress.
  const earned = progress?.hours.earned ?? 0
  const inProgressHours = progress?.hours.in_progress ?? 0
  const required = progress?.hours.required ?? null
  const percent = required ? Math.min(100, Math.round((earned / required) * 100)) : null
  const remaining = required ? Math.max(0, required - earned) : null
  const planLabel = progress?.source === 'audit' ? 'From your mySAU audit' : progress?.source === 'degree_plan' ? progress.plan?.name ?? 'Degree map' : 'No degree plan yet'

  // Current semester: the in-progress rows of /me/completed-courses.
  const currentCourses = completed.filter(course => course.status === 'in_progress')
  const currentTerm = currentCourses.find(course => course.term)?.term ?? 'This semester'
  const currentCredits = currentCourses.reduce((total, course) => total + (course.credits ?? 3), 0)
  const scheduleStarted = savedScheduleCount > 0
  const shownStatus = scheduleStarted ? scheduleStatus : 'Not started'
  const scheduleNextStep = !scheduleStarted ? 'Build your schedule in Create Schedule' : scheduleStatus === 'Approved' ? 'Ready for registration' : scheduleStatus === 'Pending Approval' ? 'Advisor review in progress' : `${savedScheduleCount} saved · review conflicts and submit`
  const nextCourse = progress?.can_take[0]

  const todayEvents = today ? calendarEvents.filter(event => event.day === today).sort((first, second) => timeValue(first.time) - timeValue(second.time)) : []
  const minutesNow = hour * 60 + now.getMinutes()
  const nextEvent = todayEvents.find(event => timeValue(event.endTime) > minutesNow)
  const nextLabel = nextEvent ? (timeValue(nextEvent.time) <= minutesNow ? 'Now' : timeValue(nextEvent.time) - minutesNow <= 120 ? `In ${Math.round(timeValue(nextEvent.time) - minutesNow)} min` : '') : ''
  const monday = new Date(now)
  monday.setDate(now.getDate() - ((now.getDay() + 6) % 7))
  const weekDates = DAY_KEYS.map((_, index) => { const date = new Date(monday); date.setDate(monday.getDate() + index); return date })
  const weekSchedule = DAY_KEYS.map((day, index) => ({ day, date: String(weekDates[index].getDate()), items: calendarEvents.filter(event => event.day === day).sort((first, second) => timeValue(first.time) - timeValue(second.time)) }))
  const weekRange = `${weekDates[0].toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}–${weekDates[4].toLocaleDateString('en-US', weekDates[0].getMonth() === weekDates[4].getMonth() ? { day: 'numeric' } : { month: 'long', day: 'numeric' })}`

  const addEvent = async () => {
    if (!newEvent.title.trim()) return
    const [hours, minutes] = newEvent.time.split(':').map(Number)
    const end = `${String(Math.min(hours + 1, 23)).padStart(2, '0')}:${String(hours >= 23 ? 59 : minutes).padStart(2, '0')}`
    const ok = await onAddEvent({ day: today ?? 'Mon', title: newEvent.title.trim(), start: newEvent.time, end, meta: newEvent.location.trim(), category: 'Personal / Study', recurrence: 'None', priority: 'Normal', fixed: false })
    if (!ok) return
    setNewEvent({ title: '', time: '12:00', location: '' })
    setEventDialogOpen(false)
    setScheduleView('day')
  }
  const submitFlowQuestion = () => {
    if (!flowQuestion.trim()) return
    askFlow(flowQuestion.trim())
    setFlowQuestion('')
  }
  return <>
    <section className="hero">
      <div><span className="eyebrow dashboard-date">{now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).toUpperCase()}</span><h1>{greeting}{studentName ? `, ${studentName.split(' ')[0]}` : ''}.</h1><p>{progress?.source === 'none' ? 'Connect mySAU on your profile to see your degree progress.' : 'Here’s what your day looks like.'}</p></div>
      <button className="primary" onClick={() => go('Create Schedule')}><Icon name="spark" /> Create schedule</button>
    </section>
    <div className="stats-grid">
      <article className="card progress-card degree-progress-card">
        <div className="card-head"><h2 className="module-title"><span className="feature-icon blue"><Icon name="chart" size={17} /></span>Degree Progress</h2><span className="pill success dashboard-status">{planLabel}</span></div>
        <div className="degree-completion-summary"><strong>{percent === null ? '—' : `${percent}%`}</strong><span>Degree completion</span></div>
        <div className="bar"><i style={{ width: `${percent ?? 0}%` }} /></div>
        <p className="credit-summary"><strong>{required ? `${earned} of ${required} credits completed` : `${earned} credits completed`}</strong>{remaining !== null && <span> · {remaining} remaining</span>}</p>
        <div className="degree-projection"><span className="degree-projection-icon"><Icon name="calendar" size={18} /></span><div><span>Left after this semester</span><strong>{remaining === null ? 'Not known yet' : `${Math.max(0, remaining - inProgressHours)} credits`}</strong><p>{remaining === null ? 'Needs a degree plan or mySAU audit' : `${semestersLeft(remaining - inProgressHours)} (estimate)`}</p></div></div>
        <button className="text-btn degree-progress-link" onClick={() => go('Degree Progress')}>View degree progress <Icon name="arrow" size={15} /></button>
      </article>
      <article className="card semester-card">
        <div className="semester-head">
          <div><span className="label current-semester-label"><span className="feature-icon purple"><Icon name="layers" size={16} /></span>Current semester</span><h2>{currentTerm}</h2></div>
          <span className="semester-total"><strong>{currentCredits}</strong> credits</span>
        </div>
        <div className="semester-courses">
          {currentCourses.map(course => <div className="semester-course" key={`${course.course_code}-${course.term}`}>
            <i className={toneFor(course.course_code)} />
            <span className="semester-code">{course.course_code}</span>
            <strong className="semester-course-name">{course.title ?? 'Course'}</strong>
            <span className="course-credits">{course.credits ?? 3} cr</span>
          </div>)}
          {!currentCourses.length && <p className="credit-summary"><span>No courses in progress right now.</span></p>}
        </div>
        <button className="text-btn semester-plan-link" onClick={() => go('Semester Planner')}>View semester plan <Icon name="arrow" size={15} /></button>
        <div className="semester-schedule-status"><div className="semester-schedule-copy"><span>{termName} Schedule</span><strong className={`schedule-status-${shownStatus.toLowerCase().replace(' ', '-')}`}>{shownStatus}</strong><small>{scheduleNextStep}</small></div><button onClick={viewSchedule}>{scheduleStarted ? (scheduleStatus === 'Draft Saved' ? 'Continue' : 'View schedule') : 'Start'} <Icon name="arrow" size={14} /></button></div>
      </article>
    </div>
    <article className="ai-card dashboard-insight ask-flow-card"><img className="ai-orb flow-koi-icon" src="/assets/flow-koi.png" alt="Flow koi icon" /><div className="insight-copy"><h3>Ask Flow</h3><span className="ask-flow-support">Get personalized academic guidance</span><p>{nextCourse ? `You can take ${nextCourse.code}${nextCourse.title ? ` ${nextCourse.title}` : ''} in ${termName}, and Flow can help compare sections, review requirements, or fit courses around your commitments.` : 'Flow can review your requirements, compare sections, or fit courses around your commitments.'}</p><form className="ask-flow-form" onSubmit={event => { event.preventDefault(); submitFlowQuestion() }}><input value={flowQuestion} onChange={event => setFlowQuestion(event.target.value)} placeholder="Ask Flow about your academic plan..." /><button type="submit"><Icon name="chat" size={16} /> Ask Flow</button></form><div className="ask-flow-prompts"><button onClick={() => askFlow('Am I on track to graduate?')}>Am I on track?</button><button onClick={() => askFlow(`What courses should I take in ${termName}?`)}>What should I take next?</button><button onClick={() => askFlow(`Build a balanced ${termName} schedule around my commitments.`)}>Build my schedule</button></div></div></article>
    <div className="dashboard-main">
      <article className="card schedule-card">
        <div className="section-head schedule-head"><div><h2 className="schedule-title module-title"><span className="feature-icon teal"><Icon name="calendar" size={17} /></span>{scheduleView === 'day' ? 'Today’s schedule' : 'This week'}</h2><p className="schedule-summary">{scheduleView === 'day' ? (today ? `${todayEvents.length} commitments · Next at ${nextEvent?.time || '—'}` : 'No classes on the weekend') : `${calendarEvents.length} commitments · ${weekRange}`}</p></div><div className="schedule-actions"><div className="view-tabs"><button className={scheduleView === 'day' ? 'active' : ''} onClick={() => setScheduleView('day')}>Day</button><button className={scheduleView === 'week' ? 'active' : ''} onClick={() => setScheduleView('week')}>Week</button></div><button className="ghost add-event-button" onClick={() => setEventDialogOpen(true)}><Icon name="plus" size={15} /> Add event</button><button className="ghost" onClick={() => go('My Calendar')}>View calendar</button></div></div>
        {scheduleView === 'day'
          ? <div className="timeline">{todayEvents.map(e => <button className="event" key={e.id} onClick={() => alert(`${e.title}\n${e.time} · ${e.meta}\n${e.type}`)}><span className={`event-time ${e === nextEvent ? 'primary-event-time' : 'selected-event-time'}`}>{e.time}</span><i className={`event-dot ${e.tone}`} /><span className="event-copy"><strong className="selected-event-title">{e.title}</strong><small className="selected-event-meta">{e.meta}</small></span>{e === nextEvent && nextLabel && <span className="pill live dashboard-live-pill">{nextLabel}</span>}<Icon name="arrow" size={16} /></button>)}{!todayEvents.length && <p className="schedule-summary">Nothing on your calendar today.</p>}</div>
          : <div className="dashboard-week">{weekSchedule.map(day => <div className={`dashboard-day ${day.day === today ? 'today' : ''}`} key={day.day}><div className="dashboard-day-head"><span>{day.day}</span><strong>{day.date}</strong><small>{day.items.length} events</small></div><div className="dashboard-day-events">{day.items.map(item => <button key={item.id} onClick={() => alert(`${item.title}\n${item.time} · ${item.meta}\n${item.type}`)}><i className={item.tone} /><span><small>{item.time}</small><strong>{item.title}</strong></span></button>)}</div></div>)}</div>}
      </article>
    </div>
    {eventDialogOpen && <div className="modal-backdrop" onMouseDown={() => setEventDialogOpen(false)}><form className="event-dialog" onMouseDown={event => event.stopPropagation()} onSubmit={event => { event.preventDefault(); addEvent() }}><div className="event-dialog-head"><div><span className="eyebrow">NEW COMMITMENT</span><h2>Add an event</h2><p>Add work, activities, appointments, or anything else you need to attend{today ? ' today' : ' on Monday'}.</p></div></div><label>Event name<input autoFocus required value={newEvent.title} onChange={event => setNewEvent({ ...newEvent, title: event.target.value })} placeholder="e.g. Career fair" /></label><div className="event-dialog-row"><label>Time<input required type="time" value={newEvent.time} onChange={event => setNewEvent({ ...newEvent, time: event.target.value })} /></label><label>Location or details<input value={newEvent.location} onChange={event => setNewEvent({ ...newEvent, location: event.target.value })} placeholder="e.g. Student Center" /></label></div><div className="event-dialog-actions"><button type="button" className="ghost" onClick={() => setEventDialogOpen(false)}>Cancel</button><button className="primary" type="submit"><Icon name="plus" size={15} /> Add to schedule</button></div></form></div>}
  </>
}
