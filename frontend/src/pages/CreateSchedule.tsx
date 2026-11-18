import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import { defaultSection, displayToHours, draftSection, meetings, placeText, prereqText, scheduleText, toneFor } from '../api/adapters'
import type { ApiCatalogCourse, ApiCheckItem, ApiCheckResult, ApiScheduleDetail, ApiScheduleSummary } from '../api/types'
import { Icon } from '../components/Icon'
import type { CalendarEvent, ScheduleDraft, ScheduleMeeting, SchedulingPreferences } from '../types'

type BuilderCalendarItem = ScheduleMeeting & { key: string; type: 'course' | 'commitment'; title: string; subtitle: string; meta: string; tone: string; sectionId?: string; eventId?: string; fixed?: boolean }
const NO_CHECK: ApiCheckResult = { conflicts: [], warnings: [] }
const PAGE = 20
const dayNumber: Record<CalendarEvent['day'], number> = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4 }

function eligibilityLabel(course: ApiCatalogCourse) {
  if (course.eligibility === 'completed') return 'Already completed'
  if (course.eligibility === 'in_progress') return 'In progress now'
  if (course.eligibility === 'missing_prereq') return `Not eligible · Needs ${prereqText(course.missing_prereqs)}`
  return course.prereqs.length ? 'Eligible · Prerequisites met' : 'Eligible · No prerequisite'
}

// The schedule checker on the backend is the only judge of conflicts: every change to the draft
// runs POST /schedules/check, and what it returns (conflicts block saving, warnings don't) is
// what this page shows, commitment overlaps included. Auto-generate is POST /ai/suggest.
export function CreateSchedule({ termId, termName, hasPlan, preferences, draft, setDraft, commitments, savedSchedules, onLoadSchedule, onSaved, onDeleted, submit, askAdvisor, openPreferences, onToast, onError }: { termId: string; termName: string; hasPlan: boolean; preferences: SchedulingPreferences; draft: ScheduleDraft; setDraft: (draft: ScheduleDraft) => void; commitments: CalendarEvent[]; savedSchedules: ApiScheduleSummary[]; onLoadSchedule: (id: string) => void; onSaved: (detail: ApiScheduleDetail) => void; onDeleted: (id: string) => void; submit: () => void; askAdvisor: () => void; openPreferences: () => void; onToast: (message: string) => void; onError: (error: unknown) => void }) {
  const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
  const hours = Array.from({ length: 13 }, (_, index) => index + 8)
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [department, setDepartment] = useState('All departments')
  const [scope, setScope] = useState(hasPlan ? 'On my plan' : 'All courses')
  const [courses, setCourses] = useState<ApiCatalogCourse[]>([])
  const [total, setTotal] = useState(0)
  const [departments, setDepartments] = useState<string[]>([])
  const [listLoading, setListLoading] = useState(false)
  const [sectionChoices, setSectionChoices] = useState<Record<string, string>>({})
  const [showCommitments, setShowCommitments] = useState(true)
  const [creditWarningDismissed, setCreditWarningDismissed] = useState(false)
  const [sidePanelOpen, setSidePanelOpen] = useState(true)
  const [flowPanelOpen, setFlowPanelOpen] = useState(true)
  const [catalogPanelOpen, setCatalogPanelOpen] = useState(true)
  const [reviewingConflicts, setReviewingConflicts] = useState(false)
  const [check, setCheck] = useState<ApiCheckResult>(NO_CHECK)
  const [checking, setChecking] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [explanation, setExplanation] = useState('')
  const [saveOpen, setSaveOpen] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saving, setSaving] = useState(false)
  const listRequest = useRef(0)
  const checkRequest = useRef(0)

  const sectionIds = draft.sections.map(section => section.id)
  const sectionKey = sectionIds.join(',')

  // Live check: every change to the draft goes through the backend checker.
  useEffect(() => {
    if (!termId || !sectionIds.length) { setCheck(NO_CHECK); return }
    const id = ++checkRequest.current
    setChecking(true)
    const timer = setTimeout(() => {
      api.check(termId, sectionIds).then(result => { if (id === checkRequest.current) setCheck(result) })
        .catch(error => { if (id === checkRequest.current) onError(error) })
        .finally(() => { if (id === checkRequest.current) setChecking(false) })
    }, 200)
    return () => clearTimeout(timer)
  }, [termId, sectionKey, commitments.map(c => `${c.id}${c.day}${c.time}${c.endTime}${c.fixed}`).join('|')])

  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 300); return () => clearTimeout(timer) }, [query])
  const loadCourses = (offset: number) => {
    if (!termId) return
    const id = ++listRequest.current
    setListLoading(true)
    api.courses({ term_id: termId, search: search || undefined, department: department === 'All departments' ? undefined : department, on_my_plan: scope === 'On my plan', eligible_only: scope === 'Eligible now', limit: PAGE, offset })
      .then(result => { if (id !== listRequest.current) return; setCourses(current => offset ? [...current, ...result.courses] : result.courses); setTotal(result.total); setDepartments(result.departments) })
      .catch(onError).finally(() => { if (id === listRequest.current) setListLoading(false) })
  }
  useEffect(() => loadCourses(0), [termId, search, department, scope])

  const inDraft = (code: string) => draft.sections.find(section => section.code === code)
  const chosenSection = (course: ApiCatalogCourse) => {
    const active = course.sections.filter(section => section.active)
    return active.find(section => section.id === (inDraft(course.code)?.id ?? sectionChoices[course.code])) ?? defaultSection(course)
  }
  const replaceDraft = (sections: ScheduleDraft['sections'], extra: Partial<ScheduleDraft> = {}) => setDraft({ ...draft, ...extra, sections })
  const toggleCourse = (course: ApiCatalogCourse) => {
    if (inDraft(course.code)) return replaceDraft(draft.sections.filter(section => section.code !== course.code))
    const section = chosenSection(course)
    if (section) replaceDraft([...draft.sections, draftSection(course, section)])
  }
  const chooseSection = (course: ApiCatalogCourse, sectionId: string) => {
    setSectionChoices(current => ({ ...current, [course.code]: sectionId }))
    const section = course.sections.find(item => item.id === sectionId)
    if (section && inDraft(course.code)) replaceDraft(draft.sections.map(item => item.code === course.code ? draftSection(course, section) : item))
  }
  const removeSection = (sectionId: string) => replaceDraft(draft.sections.filter(section => section.id !== sectionId))

  const conflictSections = new Set(check.conflicts.flatMap(item => item.section_ids))
  const conflictEvents = new Set(check.conflicts.flatMap(item => item.event_ids ?? []))
  const totalCredits = Object.values(Object.fromEntries(draft.sections.map(section => [section.code, section.credits]))).reduce((sum, credits) => sum + credits, 0)
  const overLimit = check.warnings.some(item => item.code === 'over_credit_limit')
  const formatHour = (hour: number) => hour === 12 ? '12 PM' : hour < 12 ? `${hour} AM` : `${hour - 12} PM`
  const courseEvents: BuilderCalendarItem[] = draft.sections.flatMap(section => meetings(section).map((meeting, index) => ({ key: `${section.id}-${index}`, type: 'course' as const, title: section.code, subtitle: section.title ?? '', meta: `Section ${section.section_number} · ${section.location || 'TBA'}`, tone: toneFor(section.code), sectionId: section.id, ...meeting })))
  const offGrid = draft.sections.filter(section => !meetings(section).length)
  const commitmentItems: BuilderCalendarItem[] = commitments.map(event => ({ key: event.id, type: 'commitment', title: event.title, subtitle: event.fixed ? 'Fixed commitment' : 'Flexible activity', meta: event.meta, tone: event.tone, fixed: event.fixed, eventId: event.id, day: dayNumber[event.day], start: displayToHours(event.time), end: displayToHours(event.endTime) }))
  const visibleCalendarItems = showCommitments ? [...courseEvents, ...commitmentItems] : courseEvents
  const isConflict = (item: BuilderCalendarItem) => (item.sectionId && conflictSections.has(item.sectionId)) || (item.eventId && conflictEvents.has(item.eventId))
  const overlapsOnGrid = (first: ScheduleMeeting, second: ScheduleMeeting) => first.day === second.day && first.start < second.end && second.start < first.end
  const calendarItemStyle = (item: BuilderCalendarItem) => {
    // Layout only: items sharing a time slot sit side by side. Conflicts come from the checker.
    const sharing = visibleCalendarItems.filter(other => overlapsOnGrid(item, other)).sort((first, second) => first.key.localeCompare(second.key))
    const lane = Math.max(0, sharing.findIndex(other => other.key === item.key))
    const count = sharing.length
    const startRow = Math.max(2, Math.floor(item.start) - 6)
    return { gridColumn: item.day + 2, gridRow: `${startRow} / span ${Math.max(1, Math.ceil(item.end - Math.max(item.start, 8)))}`, ...(count > 1 ? { width: `calc(${100 / count}% - 6px)`, marginLeft: `calc(${lane * 100 / count}% + 3px)`, marginRight: 0 } : {}) }
  }

  const autoGenerate = async () => {
    setGenerating(true)
    setExplanation('')
    try {
      const result = await api.suggest({ term_id: termId })
      if (!result.sections.length) { setExplanation(result.explanation || 'Flow couldn’t build a schedule from your record. Try adding courses by hand.'); return }
      setDraft({ scheduleId: null, name: '', source: 'ai', sections: result.sections })
      setExplanation(result.explanation)
      onToast(result.conflicts.length ? 'Flow’s schedule still has conflicts. They’re listed below.' : 'Flow built a schedule. Review it, then save.')
    } catch (error) { onError(error) } finally { setGenerating(false) }
  }

  const openSave = () => { setSaveName(draft.name || `${termName} schedule${savedSchedules.length ? ` ${savedSchedules.length + 1}` : ''}`); setSaveOpen(true) }
  const save = async (asNew: boolean) => {
    if (!saveName.trim() || saving) return
    setSaving(true)
    const body = { name: saveName.trim().slice(0, 80), term_id: termId, section_ids: sectionIds, source: draft.source }
    try {
      const detail = draft.scheduleId && !asNew ? await api.updateSchedule(draft.scheduleId, body) : await api.createSchedule(body)
      setDraft({ ...draft, scheduleId: detail.id, name: detail.name })
      setCheck({ conflicts: detail.conflicts, warnings: detail.warnings })
      onSaved(detail)
      setSaveOpen(false)
      onToast(`Saved “${detail.name}”`)
    } catch (error) {
      if (error instanceof ApiError && error.code === 'schedule_has_conflicts') {
        setCheck(current => ({ ...current, conflicts: (error.body.conflicts as ApiCheckItem[]) ?? current.conflicts }))
        setSaveOpen(false)
      }
      onError(error)
    } finally { setSaving(false) }
  }
  const remove = async () => {
    if (!draft.scheduleId || !window.confirm(`Delete “${draft.name}”? This can’t be undone.`)) return
    try {
      await api.deleteSchedule(draft.scheduleId)
      onDeleted(draft.scheduleId)
      setDraft({ scheduleId: null, name: '', source: 'manual', sections: [] })
      onToast('Schedule deleted')
    } catch (error) { onError(error) }
  }

  const conflicts = check.conflicts
  // over_credit_limit shows as the compact advisory next to the credit total instead.
  const warnings = check.warnings.filter(item => item.code !== 'over_credit_limit')
  return <div className={`schedule-builder ${sidePanelOpen ? '' : 'side-collapsed'} ${reviewingConflicts ? 'reviewing-conflicts' : ''}`}>
    <article className="card timetable-card">
      <div className="builder-head"><div><span className="eyebrow">{termName.toUpperCase()}</span><h2 className="weekly-schedule-title">Weekly schedule</h2><p>{preferences.flexibility} preferences · {preferences.time === 'No preference' ? 'any time' : `${preferences.time.toLowerCase()} classes`} · {preferences.minCredits}–{preferences.maxCredits} credits</p><select className="builder-schedule-picker" aria-label="Saved schedules" value={draft.scheduleId ?? ''} onChange={event => event.target.value ? onLoadSchedule(event.target.value) : setDraft({ scheduleId: null, name: '', source: 'manual', sections: [] })}><option value="">{draft.scheduleId ? 'New schedule' : savedSchedules.length ? 'Unsaved draft' : 'New schedule'}</option>{savedSchedules.map(item => <option key={item.id} value={item.id}>{item.name} · {item.credits} cr</option>)}</select></div><div className="builder-head-actions"><button className="ghost" onClick={openPreferences}><Icon name="sliders" size={15} /> Preferences</button><button className="ghost panel-toggle" onClick={() => setSidePanelOpen(value => !value)}><Icon name="layers" size={15} />{sidePanelOpen ? 'Hide panels' : 'Show panels'}</button><button className="ghost" disabled={!draft.sections.length} onClick={() => { replaceDraft([], { source: 'manual' }); setExplanation('') }}>Clear</button><button className="primary" disabled={generating} onClick={autoGenerate}><Icon name="spark" size={16} /> {generating ? 'Flow is building…' : 'Auto-generate'}</button></div></div>
      <div className="builder-summary"><div><span>Courses</span><strong>{new Set(draft.sections.map(s => s.code)).size}</strong></div><div className="credit-stat"><span>Credit hours</span><strong>{totalCredits}</strong>{overLimit && !creditWarningDismissed && <div className="compact-credit-advisory"><Icon name="book" size={15} /><span><strong>High load:</strong> {totalCredits} credits is over the 18-credit limit.</span><button aria-label="Dismiss high credit load warning" onClick={() => setCreditWarningDismissed(true)}>×</button></div>}</div><div className={conflicts.length ? 'has-conflicts' : ''}><span>Conflicts</span><strong>{checking && draft.sections.length ? '…' : conflicts.length}</strong></div><div className="commitment-controls"><button className={`commitment-toggle ${showCommitments ? 'active' : ''}`} aria-pressed={showCommitments} onClick={() => setShowCommitments(value => !value)}><i /><span>{showCommitments ? 'Hide' : 'Show'} commitments</span></button><small><b className="fixed-key" /> Fixed <b className="flexible-key" /> Flexible</small></div></div>
      {(conflicts.length > 0 || warnings.length > 0 || explanation) && <div className="builder-alerts">
        {explanation && <div className="schedule-warning"><Icon name="spark" size={18} /><div><strong>Flow’s suggestion</strong><span>{explanation}</span></div></div>}
        {conflicts.length > 0 && <div className="schedule-warning conflict-warning"><Icon name="calendar" size={18} /><div><strong>{conflicts.length} schedule {conflicts.length === 1 ? 'conflict' : 'conflicts'} detected</strong>{conflicts.map((item, index) => <span key={`c${index}`}>{item.message}</span>)}<span className="conflict-actions"><button onClick={() => setReviewingConflicts(value => !value)}>{reviewingConflicts ? 'Show all events' : 'Review on timetable'}</button></span></div></div>}
        {warnings.length > 0 && <div className="schedule-warning"><Icon name="book" size={18} /><div><strong>{warnings.length} {warnings.length === 1 ? 'warning' : 'warnings'} (saving is still allowed)</strong>{warnings.map((item, index) => <span key={`w${index}`}>{item.message}</span>)}</div></div>}
      </div>}
      <div className="timetable-scroll">
        <div className="builder-timetable">
          <div className="timetable-corner">TIME</div>
          {days.map(day => <div className="timetable-day" key={day}>{day}</div>)}
          {hours.map((hour, hourIndex) => <div className="timetable-hour-row" key={hour}><div className="timetable-time" style={{ gridColumn: 1, gridRow: hourIndex + 2 }}>{formatHour(hour)}</div>{days.map((day, dayIndex) => <div className="timetable-cell" style={{ gridColumn: dayIndex + 2, gridRow: hourIndex + 2 }} key={`${day}-${hour}`} />)}</div>)}
          {visibleCalendarItems.map(item => item.type === 'course'
            ? <button className={`builder-course-event ${item.tone} ${isConflict(item) ? 'event-conflict' : ''} ${reviewingConflicts && isConflict(item) ? 'conflict-focused' : ''}`} style={calendarItemStyle(item)} key={item.key} onClick={() => item.sectionId && removeSection(item.sectionId)} title={`Remove ${item.title}`}><strong>{item.title}</strong><span>{item.subtitle}</span><small>{item.meta}</small>{isConflict(item) && <em>Conflict</em>}</button>
            : <div className={`builder-course-event commitment-event ${item.tone} ${isConflict(item) ? 'event-conflict' : ''} ${reviewingConflicts && isConflict(item) ? 'conflict-focused' : ''}`} style={calendarItemStyle(item)} key={item.key}><strong>{item.title}</strong><span>{item.subtitle}</span><small>{item.meta}</small>{isConflict(item) && <em>Conflict</em>}</div>)}
        </div>
      </div>
      {offGrid.length > 0 && <div className="builder-online-list"><span className="eyebrow">ONLINE / TBA · NOT ON THE GRID</span><div>{offGrid.map(section => <button key={section.id} className={`builder-online-item ${conflictSections.has(section.id) ? 'event-conflict' : ''}`} onClick={() => removeSection(section.id)} title={`Remove ${section.code}`}><i className={toneFor(section.code)} /><strong>{section.code}-{section.section_number}</strong><span>{section.title}</span><small>{scheduleText(section)} · {section.credits} cr</small></button>)}</div></div>}
      <div className="builder-footer"><span className={conflicts.length ? 'conflict-status' : ''}><i className="status-dot" /> {!draft.sections.length ? 'Add courses to start' : conflicts.length ? `${conflicts.length} conflicts need attention` : checking ? 'Checking…' : 'No schedule conflicts'}</span><div className="builder-submit-actions">{draft.scheduleId && <button className="ghost" onClick={remove}>Delete</button>}<button className="ghost" disabled={!draft.sections.length} title={conflicts.length ? 'The checker will refuse a schedule with conflicts' : ''} onClick={openSave}>Save draft</button><button className="primary" disabled={!draft.scheduleId || conflicts.length > 0} title={!draft.scheduleId ? 'Save the schedule first' : conflicts.length ? 'Resolve conflicts before submitting' : ''} onClick={submit}>Submit for approval</button></div></div>
    </article>
    {sidePanelOpen && <div className="builder-side">
      <article className={`ai-card builder-ai-insight ${flowPanelOpen ? '' : 'panel-collapsed'}`}><img className="ai-orb flow-koi-icon" src="/assets/flow-koi.png" alt="Flow koi icon" /><div><span className="eyebrow">AI INSIGHT</span><h3>Need schedule help?</h3>{flowPanelOpen && <><p>Balance sections and resolve conflicts.</p><button onClick={askAdvisor}><Icon name="chat" size={15} /> Consult AI Advisor</button></>}</div><button className="insight-collapse" aria-label={flowPanelOpen ? 'Collapse Flow assistance' : 'Expand Flow assistance'} onClick={() => setFlowPanelOpen(value => !value)}>{flowPanelOpen ? '−' : '+'}</button></article>
      <aside className="card builder-catalog">
        <div className="catalog-panel-head"><div><span className="eyebrow">COURSE CATALOG</span><h2>Find courses</h2></div><span className="panel-head-actions"><span className="pill">{total} results</span><button className="panel-collapse-button" aria-label={catalogPanelOpen ? 'Collapse course catalog' : 'Expand course catalog'} onClick={() => setCatalogPanelOpen(value => !value)}>{catalogPanelOpen ? '−' : '+'}</button></span></div>
        {catalogPanelOpen && <><div className="builder-search"><Icon name="search" size={17} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search courses…" /></div>
          <div className="builder-filters"><select value={department} onChange={event => setDepartment(event.target.value)}><option>All departments</option>{departments.map(value => <option key={value}>{value}</option>)}</select><select value={scope} onChange={event => setScope(event.target.value)}>{hasPlan && <option>On my plan</option>}<option>Eligible now</option><option>All courses</option></select></div>
          <div className="builder-course-list">{courses.map(course => {
            const eligible = course.eligibility === 'eligible'
            const added = Boolean(inDraft(course.code))
            const active = course.sections.filter(section => section.active)
            const selectedSection = chosenSection(course)
            return <article className={`builder-course ${added ? 'added' : ''} ${!eligible ? 'ineligible-course' : ''}`} key={course.id}><div className="builder-course-top"><span className="course-code">{course.code}</span><span className={`eligibility ${eligible ? 'eligible' : 'ineligible'}`}>{eligibilityLabel(course)}</span></div><h3>{course.title}</h3><div className="section-picker"><label>Available section<select value={selectedSection?.id ?? ''} onChange={event => chooseSection(course, event.target.value)}>{active.map(section => <option value={section.id} key={section.id}>Section {section.section_number} · {scheduleText(section)}{section.seats_open ? '' : ' · full'}</option>)}</select></label></div>{selectedSection && <div className="course-section-details"><p><strong>{scheduleText(selectedSection)}</strong></p><p>{selectedSection.instructor} · {placeText(selectedSection)} · {selectedSection.seats_open} open seats</p><p>Prerequisite: {prereqText(course.prereqs)}{course.requirement_names.length ? ` · Counts toward ${course.requirement_names[0]}` : ''}</p></div>}<div className="course-card-foot"><span>{course.credits} credits</span><button disabled={!selectedSection} className={added ? 'remove-course' : 'add-catalog-course'} onClick={() => toggleCourse(course)}>{added ? <><Icon name="check" size={15} /> Added — remove</> : <><Icon name="plus" size={15} /> Add to schedule</>}</button></div></article>
          })}</div>
          {courses.length < total && <button className="ghost wide" disabled={listLoading} onClick={() => loadCourses(courses.length)}>{listLoading ? 'Loading…' : `Load more (${total - courses.length} left)`}</button>}
          {!courses.length && !listLoading && <div className="catalog-empty"><Icon name="search" /><strong>No courses found</strong><span>Try changing your search or filters.</span></div>}</>}
      </aside>
    </div>}
    {saveOpen && <div className="modal-backdrop" onMouseDown={() => setSaveOpen(false)}><form className="event-dialog" onMouseDown={event => event.stopPropagation()} onSubmit={event => { event.preventDefault(); save(false) }}><div className="event-dialog-head"><div><span className="eyebrow">{termName.toUpperCase()}</span><h2>{draft.scheduleId ? 'Save changes' : 'Save this schedule'}</h2><p>You can keep several schedules for {termName} and compare them later.</p></div></div><label>Schedule name<input autoFocus required maxLength={80} value={saveName} onChange={event => setSaveName(event.target.value)} placeholder="e.g. Plan A: mornings" /></label><div className="event-dialog-actions"><button type="button" className="ghost" onClick={() => setSaveOpen(false)}>Cancel</button>{draft.scheduleId && <button type="button" className="ghost" disabled={saving} onClick={() => save(true)}>Save as new</button>}<button className="primary" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save'}</button></div></form></div>}
  </div>
}
