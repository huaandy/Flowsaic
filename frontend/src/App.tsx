import { useEffect, useRef, useState } from 'react'
import { ApiError, api, onUnauthorized, saveFile } from './api/client'
import { DEFAULT_SETTINGS, MOCK_PREFERENCE_DEFAULTS, type EventDraft, type MockPreferenceFields, classEvents, defaultSection, draftSection, eventDraftToApi, eventToUi, preferencesToApi, preferencesToUi, settingsToApi, settingsToUi } from './api/adapters'
import { friendlyError } from './api/errors'
import type { ApiCatalogCourse, ApiCompletedCourse, ApiEvent, ApiPreferences, ApiProgress, ApiProposal, ApiScheduleDetail, ApiScheduleSection, ApiScheduleSummary, ApiSearchResult, ApiStudent, ApiTerm } from './api/types'
import { HeaderSearch } from './components/HeaderSearch'
import { Icon } from './components/Icon'
import { SignIn } from './components/SignIn'
import { initialPlannedTerms, completedTermName, type PlannedTerms } from './mock'
import { AIAdvisor, type AdvisorMessage } from './pages/AIAdvisor'
import { CalendarPage } from './pages/CalendarPage'
import { Catalog, type CatalogFocus } from './pages/Catalog'
import { CreateSchedule } from './pages/CreateSchedule'
import { Dashboard } from './pages/Dashboard'
import { DegreePage } from './pages/DegreePage'
import { HelpSupportPage } from './pages/HelpSupportPage'
import { Planner } from './pages/Planner'
import { type ConnectState, ProfilePage } from './pages/ProfilePage'
import { DEFAULT_PREFERENCES, SchedulingPreferencesPage } from './pages/SchedulingPreferencesPage'
import { SettingsPage } from './pages/SettingsPage'
import { EMPTY_DRAFT, type AppSettings, type Page, type ScheduleDraft, type ScheduleStatus, type SchedulingPreferences, type StudentProfile } from './types'

const nav: { label: Page; icon: string }[] = [
  { label: 'Dashboard', icon: 'grid' },
  { label: 'Degree Progress', icon: 'chart' },
  { label: 'Course Catalog', icon: 'book' },
  { label: 'Semester Planner', icon: 'layers' },
  { label: 'My Calendar', icon: 'calendar' },
  { label: 'Create Schedule', icon: 'spark' },
  { label: 'AI Advisor', icon: 'chat' },
]

// localStorage holds per-device conveniences only (the theme before sign-in, the unsaved draft,
// the mock-only fields). Everything that matters lives in the backend.
const store = {
  get<T>(key: string, fallback: T): T { try { const value = localStorage.getItem(key); return value ? JSON.parse(value) as T : fallback } catch { return fallback } },
  set(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private window */ } },
}

function applyTheme(settings: AppSettings) {
  const root = document.documentElement
  root.dataset.appearance = settings.appearance.toLowerCase()
  const dark = settings.appearance === 'System' ? window.matchMedia('(prefers-color-scheme: dark)').matches : settings.appearance === 'Dark'
  root.dataset.theme = dark ? 'dark' : 'light'
  root.classList.toggle('larger-text', settings.largerText)
  root.classList.toggle('high-contrast', settings.highContrast)
  root.classList.toggle('reduce-motion', settings.reduceMotion)
}

function estimateGraduation(progress: ApiProgress | null) {
  if (!progress?.hours.required) return 'Not known yet'
  const left = progress.hours.required - progress.hours.earned - progress.hours.in_progress
  if (left <= 0) return 'After this semester'
  const terms = Math.ceil(left / 15)
  return `About ${terms} more ${terms === 1 ? 'semester' : 'semesters'}`
}

function App() {
  const [auth, setAuth] = useState<'loading' | 'signedOut' | 'signedIn'>('loading')
  const [signedOutNote, setSignedOutNote] = useState(false)
  const [me, setMe] = useState<ApiStudent | null>(null)
  const [page, setPage] = useState<Page>('Dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [toast, setToast] = useState('')
  // Backend data for the signed-in student.
  const [term, setTerm] = useState<ApiTerm | null>(null)
  const [progress, setProgress] = useState<ApiProgress | null>(null)
  const [completed, setCompleted] = useState<ApiCompletedCourse[]>([])
  const [schedules, setSchedules] = useState<ApiScheduleSummary[]>([])
  const [events, setEvents] = useState<ApiEvent[]>([])
  const [apiPreferences, setApiPreferences] = useState<ApiPreferences | null>(null)
  const [settings, setSettings] = useState<AppSettings>(() => store.get('flowsaic-theme', DEFAULT_SETTINGS))
  const [photo, setPhoto] = useState('')
  // Travel distance and minimum rating are mock (this device only), kept per student. A student who
  // never saved preferences (users 4 and 5 at first) always starts from the defaults.
  const [mockPreferences, setMockPreferences] = useState<MockPreferenceFields>(MOCK_PREFERENCE_DEFAULTS)
  // The Create Schedule draft, and the saved schedule whose classes show on the calendar.
  const [draft, setDraftState] = useState<ScheduleDraft>(EMPTY_DRAFT)
  const [calendarScheduleId, setCalendarScheduleId] = useState('')
  const [calendarSections, setCalendarSections] = useState<ApiScheduleSection[]>([])
  const [catalogFocus, setCatalogFocus] = useState<CatalogFocus | null>(null)
  const [flowMessages, setFlowMessages] = useState<AdvisorMessage[]>([])
  const [flowLoading, setFlowLoading] = useState(false)
  const [connect, setConnect] = useState<ConnectState>({ status: 'idle', message: '' })
  // Mock-only (src/mock.ts): the multi-term planner and the approval status.
  const [plannedTerms, setPlannedTerms] = useState<PlannedTerms>(() => ({ ...initialPlannedTerms, ...store.get('flowsaic-planned-terms', {}), [completedTermName]: initialPlannedTerms[completedTermName] }))
  const [scheduleStatus, setScheduleStatus] = useState<ScheduleStatus>(() => store.get('flowsaic-schedule-status', 'Draft Saved'))
  const [accountMenu, setAccountMenu] = useState<'sidebar' | 'header' | null>(null)
  const [accountReturnPage, setAccountReturnPage] = useState<Page>('Dashboard')
  const [signOutConfirm, setSignOutConfirm] = useState(false)
  const accountMenuRef = useRef<HTMLDivElement>(null)
  const sidebarProfileRef = useRef<HTMLButtonElement>(null)
  const headerProfileRef = useRef<HTMLButtonElement>(null)
  const connectTimer = useRef<number | null>(null)

  const showError = (error: unknown, fallback?: string) => {
    if (error instanceof ApiError && error.status === 401) return // the sign-in screen takes over
    setToast(friendlyError(error, fallback))
  }
  const termId = term?.id ?? ''
  const termName = term?.name ?? 'Next term'
  const termSchedules = schedules.filter(item => item.term.id === termId)
  const preferences: SchedulingPreferences = apiPreferences ? preferencesToUi(apiPreferences, mockPreferences) : { ...DEFAULT_PREFERENCES, ...mockPreferences }
  const draftKey = me ? `flowsaic-draft:${me.id}` : ''
  const setDraft = (next: ScheduleDraft) => { setDraftState(next); if (draftKey) store.set(draftKey, next) }

  const resetSession = () => {
    setMe(null); setProgress(null); setCompleted([]); setSchedules([]); setEvents([]); setApiPreferences(null); setPhoto('')
    setDraftState(EMPTY_DRAFT); setCalendarScheduleId(''); setCalendarSections([]); setFlowMessages([]); setFlowLoading(false)
    setMockPreferences(MOCK_PREFERENCE_DEFAULTS)
    setCatalogFocus(null); setConnect({ status: 'idle', message: '' }); setPage('Dashboard')
    if (connectTimer.current) window.clearTimeout(connectTimer.current)
  }

  const loadStudentData = async (student: ApiStudent) => {
    setMe(student)
    setDraftState(store.get(`flowsaic-draft:${student.id}`, EMPTY_DRAFT))
    const [terms, progressResult, completedResult, schedulesResult, eventsResult, preferencesResult, settingsResult] = await Promise.allSettled([
      api.terms(), api.progress(), api.completedCourses(), api.schedules(), api.events(), api.preferences(), api.settings(),
    ])
    if (terms.status === 'fulfilled') setTerm(terms.value.find(item => item.is_current_registration) ?? terms.value[0] ?? null)
    if (progressResult.status === 'fulfilled') setProgress(progressResult.value)
    if (completedResult.status === 'fulfilled') setCompleted(completedResult.value)
    if (schedulesResult.status === 'fulfilled') setSchedules(schedulesResult.value)
    if (eventsResult.status === 'fulfilled') setEvents(eventsResult.value)
    if (preferencesResult.status === 'fulfilled') setApiPreferences(preferencesResult.value)
    const savedBefore = preferencesResult.status === 'fulfilled' && preferencesResult.value.updated_at !== null
    setMockPreferences(savedBefore ? store.get(`flowsaic-preference-mock:${student.id}`, MOCK_PREFERENCE_DEFAULTS) : MOCK_PREFERENCE_DEFAULTS)
    if (settingsResult.status === 'fulfilled') {
      const saved = settingsToUi(settingsResult.value)
      setSettings(saved)
      setPhoto(settingsResult.value.photo ?? '')
      store.set('flowsaic-theme', saved)
    }
    const failed = [terms, progressResult, completedResult, schedulesResult, eventsResult, preferencesResult, settingsResult].find(result => result.status === 'rejected')
    if (failed && failed.status === 'rejected') showError(failed.reason, 'Some of your data didn’t load. Try refreshing.')
  }

  // On load: am I signed in? Any later 401 sends the student back to sign-in.
  useEffect(() => {
    onUnauthorized(() => { resetSession(); setSignedOutNote(true); setAuth('signedOut'); setToast(friendlyError(new ApiError(401, 'not_authenticated'))) })
    api.me(true).then(student => { setAuth('signedIn'); return loadStudentData(student) }).catch(error => {
      setAuth('signedOut')
      if (!(error instanceof ApiError && error.status === 401)) showError(error)
    })
    return () => onUnauthorized(null)
  }, [])

  // The calendar shows the classes of one saved schedule: the newest for this term by default.
  useEffect(() => {
    if (calendarScheduleId && !termSchedules.some(item => item.id === calendarScheduleId)) setCalendarScheduleId('')
    if (!calendarScheduleId && termSchedules.length) setCalendarScheduleId(termSchedules[0].id)
  }, [schedules, termId])
  useEffect(() => {
    if (!calendarScheduleId) { setCalendarSections([]); return }
    api.schedule(calendarScheduleId).then(detail => setCalendarSections(detail.sections.filter(section => section.active !== false))).catch(showError)
  }, [calendarScheduleId])

  useEffect(() => store.set('flowsaic-planned-terms', plannedTerms), [plannedTerms])
  useEffect(() => {
    applyTheme(settings)
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)')
    const follow = () => applyTheme(settings)
    systemTheme.addEventListener('change', follow)
    return () => systemTheme.removeEventListener('change', follow)
  }, [settings, page]) // leaving Settings without saving drops its preview
  useEffect(() => {
    const close = (event: MouseEvent) => { const target = event.target as Node; if (!accountMenuRef.current?.contains(target) && !sidebarProfileRef.current?.contains(target) && !headerProfileRef.current?.contains(target)) setAccountMenu(null) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 6000); return () => clearTimeout(timer) }, [toast])

  const signIn = async (username: string, password: string) => {
    const student = await api.login(username, password || 'prototype')
    resetSession()
    setAuth('signedIn')
    setSignedOutNote(false)
    await loadStudentData(student)
  }
  const signOut = async () => {
    try { await api.logout() } catch { /* signed out either way */ }
    resetSession()
    setSignedOutNote(true)
    setAuth('signedOut')
  }

  const updateScheduleStatus = (status: ScheduleStatus) => { setScheduleStatus(status); store.set('flowsaic-schedule-status', status) }
  // Create Schedule's "Submit for approval": downloads the saved schedule as a PDF for an advisor
  // (GET /schedules/{id}/pdf). There is no advisor side yet, so nothing is submitted anywhere.
  const downloadSchedulePdf = async () => {
    if (!draft.scheduleId) return
    try {
      const { blob, filename } = await api.schedulePdf(draft.scheduleId)
      saveFile(blob, filename)
      setToast(`Schedule PDF downloaded (${filename}). Share it with your advisor.`)
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) showError(error, 'The schedule PDF couldn’t be made. Try again.')
    }
  }
  const go = (p: Page) => { if (p === 'Course Catalog') setCatalogFocus(null); setPage(p); setSidebarOpen(false) }
  const openAccountPage = (destination: 'My Profile' | 'Scheduling Preferences' | 'Settings' | 'Help & Support') => { if (!['My Profile', 'Scheduling Preferences', 'Settings', 'Help & Support'].includes(page)) setAccountReturnPage(page); setPage(destination); setAccountMenu(null); setSidebarOpen(false) }
  const openCourseInCatalog = (code: string, id?: string) => { setCatalogFocus({ code, id, nonce: Date.now() }); setPage('Course Catalog') }

  // --- the Create Schedule draft ---------------------------------------------------------------
  const draftCodes = new Set(draft.sections.map(section => section.code))
  const addCourseToDraft = (course: ApiCatalogCourse) => {
    if (draftCodes.has(course.code)) { setToast(`${course.code} is already in your ${termName} draft`); return false }
    const section = defaultSection(course)
    if (!section) { setToast(`${course.code} has no open sections in ${termName}`); return false }
    setDraft({ ...draft, sections: [...draft.sections, draftSection(course, section)] })
    setToast(`${course.code} added to your ${termName} draft (section ${section.section_number})`)
    return true
  }
  const addCodeToDraft = async (code: string) => {
    if (!termId) return
    try {
      const { courses } = await api.courses({ term_id: termId, search: code, limit: 10 })
      const course = courses.find(item => item.code === code)
      if (course) addCourseToDraft(course)
      else setToast(`${code} isn’t offered in ${termName}`)
    } catch (error) { showError(error) }
  }
  const removeCodeFromDraft = (code: string) => { setDraft({ ...draft, sections: draft.sections.filter(section => section.code !== code) }); setToast(`${code} removed from your draft`) }
  const openCourseSchedule = (course: ApiCatalogCourse) => { if (!draftCodes.has(course.code)) addCourseToDraft(course); setPage('Create Schedule') }
  const loadSavedSchedule = async (id: string) => {
    try {
      const detail = await api.schedule(id)
      const active = detail.sections.filter(section => section.active !== false)
      setDraft({ scheduleId: detail.id, name: detail.name, source: detail.source, sections: active })
      if (active.length < detail.sections.length) setToast('Some sections in this schedule are no longer offered and were left out')
    } catch (error) { showError(error) }
  }
  const refreshSchedules = () => api.schedules().then(setSchedules).catch(showError)
  const onScheduleSaved = (detail: ApiScheduleDetail) => {
    refreshSchedules()
    if (detail.id === calendarScheduleId) setCalendarSections(detail.sections.filter(section => section.active !== false))
    else if (!calendarScheduleId) setCalendarScheduleId(detail.id)
  }

  // --- calendar events (/me/events) -------------------------------------------------------------
  const personalEvents = events.map(eventToUi)
  const scheduleClasses = classEvents(calendarSections)
  const proposedEvents = draft.sections.length && draft.scheduleId !== calendarScheduleId
    ? classEvents(draft.sections, 'proposed', 'proposed').map(event => ({ ...event, title: `Proposed · ${event.title.split(' · ')[0]}` }))
    : []
  const addEvent = async (eventDraft: EventDraft) => {
    try { const created = await api.createEvent(eventDraftToApi(eventDraft)); setEvents(current => [...current, created]); setToast('Event added'); return true } catch (error) { showError(error); return false }
  }
  const updateEvent = async (id: string, eventDraft: EventDraft) => {
    try { const saved = await api.updateEvent(id, eventDraftToApi(eventDraft)); setEvents(current => current.map(item => item.id === id ? saved : item)); setToast('Event saved'); return true } catch (error) { showError(error); return false }
  }
  const removeEvent = async (id: string) => {
    try { await api.deleteEvent(id); setEvents(current => current.filter(item => item.id !== id)); setToast('Event removed'); return true } catch (error) { showError(error); return false }
  }

  // --- Flow (/ai/advisor) ------------------------------------------------------------------------
  const sendToFlow = async (text: string) => {
    if (flowLoading) return
    const earlier = flowMessages.filter(message => !message.error)
    const history = earlier.slice(-20).map(message => ({ role: message.role === 'user' ? 'user' as const : 'assistant' as const, text: (message.role === 'ai' ? message.memory ?? message.text : message.text).slice(0, 6000) }))
    setFlowMessages(current => [...current, { role: 'user', text }])
    setFlowLoading(true)
    try {
      const reply = await api.advisor(text.slice(0, 2000), history)
      setFlowMessages(current => [...current, { role: 'ai', text: reply.reply, memory: reply.memory, proposals: reply.proposals, suggestions: reply.suggestions ?? [] }])
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) setFlowMessages(current => [...current, { role: 'ai', text: friendlyError(error, 'Flow couldn’t answer that. Try again.'), error: true }])
    } finally { setFlowLoading(false) }
  }
  const askFlow = (question: string) => { setPage('AI Advisor'); setSidebarOpen(false); sendToFlow(question) }
  const saveProposal = async (proposal: ApiProposal) => {
    try {
      const detail = await api.createSchedule({ name: proposal.name.slice(0, 80) || `${termName} (Flow)`, term_id: proposal.term_id ?? termId, section_ids: proposal.section_ids, source: 'ai' })
      onScheduleSaved(detail)
      setToast(`Saved “${detail.name}”`)
      return detail.name
    } catch (error) { showError(error); return null }
  }
  const openProposal = (proposal: ApiProposal) => { setDraft({ scheduleId: null, name: '', source: 'ai', sections: proposal.sections }); setPage('Create Schedule') }

  // --- Connect mySAU (users 4 and 5) -----------------------------------------------------------
  const startConnect = async () => {
    try {
      const { runs } = await api.connectMysau()
      setConnect({ status: 'running', message: 'A browser window opened on this laptop. Sign in to mySAU there (Microsoft and Duo); Flowsaic waits up to 5 minutes.' })
      const deadline = Date.now() + 7 * 60_000
      const poll = async () => {
        try {
          const states = await Promise.all(runs.map(run => api.refreshRun(run.id)))
          if (states.some(run => run.status === 'running') && Date.now() < deadline) { connectTimer.current = window.setTimeout(poll, 3000); return }
          const ok = states.filter(run => run.status === 'ok').map(run => run.kind === 'audit' ? 'your degree audit' : 'this term’s course schedule')
          const failed = states.filter(run => run.status !== 'ok')
          setConnect({ status: failed.length ? 'failed' : 'done', message: [ok.length ? `Loaded ${ok.join(' and ')}.` : '', failed.length ? `Didn’t finish: ${failed.map(run => run.kind === 'audit' ? 'degree audit' : 'course schedule').join(', ')}${failed[0].error ? ` (${failed[0].error})` : ''}.` : ''].filter(Boolean).join(' ') })
          if (ok.length) { const student = await api.me(); await loadStudentData(student) }
        } catch (error) { setConnect({ status: 'failed', message: friendlyError(error) }) }
      }
      connectTimer.current = window.setTimeout(poll, 3000)
    } catch (error) { setConnect({ status: 'failed', message: friendlyError(error) }); showError(error) }
  }

  // --- preferences, settings, photo ------------------------------------------------------------
  const savePreferences = async (ui: SchedulingPreferences) => {
    try {
      setApiPreferences(await api.savePreferences(preferencesToApi(ui)))
      const mock = { distance: ui.distance, minRating: ui.minRating }
      setMockPreferences(mock)
      if (me) store.set(`flowsaic-preference-mock:${me.id}`, mock)
      setToast('Scheduling preferences saved')
      return true
    } catch (error) { showError(error); return false }
  }
  const saveSettings = async (ui: AppSettings) => {
    try {
      const saved = settingsToUi(await api.saveSettings(settingsToApi(ui)))
      setSettings(saved)
      store.set('flowsaic-theme', saved)
      setToast('Settings saved across Flowsaic')
      return true
    } catch (error) { showError(error); applyTheme(settings); return false }
  }
  const savePhoto = async (value: string | null) => {
    try { const saved = await api.saveSettings({ photo: value }); setPhoto(saved.photo ?? ''); setToast(value ? 'Profile photo updated' : 'Profile photo removed') } catch (error) { showError(error) }
  }

  if (auth === 'loading') return <main className="signed-out-screen"><section className="card login-card"><span className="top-brand-symbol"><img src="/assets/flow-koi.png" alt="Flowsaic koi" /></span><span className="eyebrow">FLOWSAIC</span><p>Loading…</p></section></main>
  if (auth === 'signedOut' || !me) return <><SignIn onSignIn={signIn} signedOutNote={signedOutNote} />{toast && <div className="toast"><span className="soft-icon mint"><Icon name="check" /></span>{toast}<button onClick={() => setToast('')}>Dismiss</button></div>}</>

  const profile: StudentProfile = {
    name: me.name, email: me.email, university: 'Southern Arkansas University',
    major: me.major ?? me.degree_plan?.name ?? (me.connected_mysau ? 'From your mySAU audit' : 'Not connected yet'),
    minor: '', degree: me.degree_plan?.name ?? (me.connected_mysau ? 'Your mySAU degree audit' : 'Connect mySAU to load your program'),
    standing: [me.classification ?? 'Classification not known yet', me.has_hold ? 'hold on your account, check mySAU' : ''].filter(Boolean).join(' · '),
    graduation: estimateGraduation(progress), photo,
  }
  const initials = profile.name.split(' ').map(part => part[0]).join('').slice(0, 2).toUpperCase()
  // Users 4 and 5 start as "Returning Student" / "New Student" until Connect mySAU brings their
  // real name: greet them without a name until then.
  const greetingName = ['Returning Student', 'New Student'].includes(me.name) && me.email.endsWith('@demo.flowsaic.test') ? '' : profile.name
  const title = page === 'Dashboard' ? 'Overview' : page
  const calendarAll = [...scheduleClasses, ...personalEvents]
  const backButton = <button className="ghost account-back" onClick={() => go(accountReturnPage)}><span className="previous-arrow"><Icon name="arrow" size={15} /></span>Back to {accountReturnPage === 'Dashboard' ? 'Overview' : accountReturnPage}</button>
  const openSearchResult = (result: ApiSearchResult) => openCourseInCatalog(result.code, result.course_id)

  return <div className="app">
    <aside className={`sidebar ${sidebarOpen ? 'open' : ''} ${sidebarCollapsed ? 'collapsed' : ''}`}>
      <div className="brand"><button className="sidebar-collapse" aria-label={sidebarCollapsed ? 'Expand navigation' : 'Collapse navigation'} onClick={() => setSidebarCollapsed(value => !value)}><Icon name="arrow" size={16} /></button></div>
      <nav>{nav.slice(0, 5).map(n => <button className={page === n.label ? 'active' : ''} key={n.label} onClick={() => go(n.label)}><Icon name={n.icon} /><span>{n.label}</span></button>)}<div className="nav-section-label"><span>PLANNING TOOLS</span></div>{nav.slice(5).map(n => <button className={page === n.label ? 'active' : ''} key={n.label} onClick={() => go(n.label)}><Icon name={n.icon} /><span>{n.label}</span>{n.label === 'AI Advisor' && <em>AI</em>}</button>)}</nav>
      <button ref={sidebarProfileRef} className={`profile ${accountMenu === 'sidebar' ? 'menu-open' : ''}`} onClick={() => setAccountMenu(current => current === 'sidebar' ? null : 'sidebar')} aria-expanded={accountMenu === 'sidebar'}>{profile.photo ? <img className="avatar profile-avatar-image" src={profile.photo} alt={profile.name} /> : <div className="avatar">{initials}</div>}<span><strong>{profile.name}</strong><small>{profile.major}</small></span><Icon name="arrow" size={15} /></button>
    </aside>
    <main>
      <header><div className="header-left"><button className="mobile-menu" onClick={() => setSidebarOpen(!sidebarOpen)}><Icon name="menu" /></button><button className="top-brand" onClick={() => go('Dashboard')}><span style={{ fontSize: 25 }}>flowsaic</span></button><i className="header-divider" /><span className="breadcrumb">Workspace /</span> <strong>{title}</strong></div><HeaderSearch onOpen={openSearchResult} onError={showError} /><div className="header-actions"><button className="notify" title="Notifications (preview)"><Icon name="bell" /><i /></button><button ref={headerProfileRef} className={`header-profile ${accountMenu === 'header' ? 'menu-open' : ''}`} onClick={() => setAccountMenu(current => current === 'header' ? null : 'header')} aria-expanded={accountMenu === 'header'}>{profile.photo ? <img className="avatar profile-avatar-image" src={profile.photo} alt={profile.name} /> : <div className="avatar">{initials}</div>}<span><strong>{profile.name.split(' ')[0]}</strong><small>Student</small></span><Icon name="arrow" size={13} /></button></div></header>
      <div className="canvas">
        {page === 'Dashboard' && <Dashboard go={go} calendarEvents={calendarAll} onAddEvent={addEvent} scheduleStatus={scheduleStatus} savedScheduleCount={termSchedules.length} askFlow={askFlow} viewSchedule={() => { if (!draft.sections.length && termSchedules[0]) loadSavedSchedule(termSchedules[0].id); go('Create Schedule') }} studentName={greetingName} progress={progress} completed={completed} termName={termName} />}
        {page === 'Degree Progress' && <><section className="page-title"><div><span className="eyebrow">ACADEMIC OVERVIEW</span><h1 className="degree-page-title">Your degree progress</h1><p className="degree-page-subtitle">Track every requirement on your path to graduation.</p></div></section><DegreePage progress={progress} termName={termName} draftCodes={draftCodes} openCatalog={code => openCourseInCatalog(code)} addToPlan={addCodeToDraft} askFlow={askFlow} /></>}
        {page === 'Course Catalog' && <><section className="page-title catalog-page-title"><div><span className="eyebrow">EXPLORE COURSES</span><h1>Course catalog</h1><p>Find classes that fit your goals and your schedule.</p></div></section><Catalog termId={termId} termName={termName} focus={catalogFocus} draftCodes={draftCodes} addToDraft={addCourseToDraft} removeFromDraft={removeCodeFromDraft} openSchedule={openCourseSchedule} onError={showError} /></>}
        {page === 'Semester Planner' && <><section className="page-title"><div><span className="eyebrow">YOUR ROADMAP · PREVIEW</span><h1 style={{ fontSize: 36 }}>Semester planner</h1><p style={{ fontSize: 16 }}>Drag courses to map out your path to graduation. This multi-term planner is a preview with sample courses.</p></div></section><Planner plannedTerms={plannedTerms} setPlannedTerms={setPlannedTerms} openCatalog={code => openCourseInCatalog(code)} openSchedule={(_codes, plannedTerm) => { setToast(`The planner uses sample courses. Build ${plannedTerm === termName ? 'it' : termName} with real sections here.`); setPage('Create Schedule') }} askFlow={askFlow} preferences={preferences} /></>}
        {page === 'My Calendar' && <><section className="page-title"><div><span className="eyebrow">YOUR WEEK</span><h1 style={{ fontSize: 36 }}>My calendar</h1><p style={{ fontSize: 16 }}>Classes, work, and life — all in one place.</p></div></section><CalendarPage events={personalEvents} classEvents={scheduleClasses} proposedEvents={proposedEvents} schedules={termSchedules.map(item => ({ id: item.id, name: item.name }))} activeScheduleId={calendarScheduleId} onScheduleChange={setCalendarScheduleId} onAdd={addEvent} onUpdate={updateEvent} onRemove={removeEvent} askFlow={() => askFlow('Look at my calendar commitments and help me plan my classes around them.')} /></>}
        {page === 'Create Schedule' && <><section className="page-title create-schedule-title"><div><span className="eyebrow">SCHEDULE BUILDER</span><h1>Create your schedule</h1><p>Search courses, build your week, or let Flowsaic create a balanced schedule for you.</p></div></section><CreateSchedule termId={termId} termName={termName} hasPlan={progress ? progress.source !== 'none' : Boolean(me.degree_plan)} preferences={preferences} draft={draft} setDraft={setDraft} commitments={personalEvents} savedSchedules={termSchedules} onLoadSchedule={loadSavedSchedule} onSaved={onScheduleSaved} onDeleted={id => { refreshSchedules(); if (id === calendarScheduleId) setCalendarScheduleId('') }} submit={downloadSchedulePdf} askAdvisor={() => go('AI Advisor')} openPreferences={() => openAccountPage('Scheduling Preferences')} onToast={setToast} onError={showError} /></>}
        {page === 'AI Advisor' && <><section className="page-title ai-advisor-title"><div><span className="eyebrow">PERSONALIZED GUIDANCE</span><h1>Meet Flow, your AI advisor</h1><p>Friendly guidance grounded in your degree plan, courses, and commitments.</p></div></section><AIAdvisor messages={flowMessages} loading={flowLoading} studentName={greetingName} onSend={sendToFlow} onNew={() => setFlowMessages([])} onSaveProposal={saveProposal} onOpenProposal={openProposal} /></>}
        {page === 'Advisor Dashboard' && <><section className="page-title"><div><span className="eyebrow">ADVISOR WORKSPACE · PREVIEW</span><h1>Student schedule reviews</h1><p>Review plans, share feedback, and keep students on track.</p></div></section><article className="card review"><div className="avatar">{initials}</div><div><h2>{profile.name}</h2><p>{termName} · {termSchedules[0]?.credits ?? 0} credits · Submitted (preview)</p></div><span className="pill orange">Pending review</span><button className="ghost" onClick={() => setToast(`Revision request sent to ${profile.name.split(' ')[0]} (preview)`)}>Request revision</button><button className="primary" onClick={() => { updateScheduleStatus('Approved'); setToast(`${profile.name.split(' ')[0]}’s schedule was approved (preview)`) }}>Approve schedule</button></article></>}
        {page === 'My Profile' && <><section className="page-title account-page-title"><div><span className="eyebrow">ACCOUNT</span><h1>My profile</h1><p style={{ fontSize: 16 }}>Manage your student information and review your academic summary.</p></div>{backButton}</section><ProfilePage me={me} profile={profile} progress={progress} onPhotoSave={savePhoto} onPhotoError={setToast} go={go} connect={connect} onConnect={startConnect} /></>}
        {page === 'Scheduling Preferences' && <><section className="page-title account-page-title"><div><span className="eyebrow">ACCOUNT</span><h1>Scheduling preferences</h1><p>Tell Flowsaic how to prioritize sections and build your schedule.</p></div>{backButton}</section><SchedulingPreferencesPage preferences={preferences} onSave={savePreferences} /></>}
        {page === 'Settings' && <><section className="page-title account-page-title"><div><span className="eyebrow">ACCOUNT</span><h1>Settings</h1><p>Manage notifications, appearance, privacy, and accessibility.</p></div>{backButton}</section><SettingsPage settings={settings} onSave={saveSettings} onNotify={setToast} profile={profile} onPreview={applyTheme} /></>}
        {page === 'Help & Support' && <><section className="page-title account-page-title"><div><span className="eyebrow">SUPPORT</span><h1>Help & Support</h1><p>Find answers and get help with Flowsaic.</p></div>{backButton}</section><HelpSupportPage onNotify={setToast} /></>}
      </div>
    </main>
    {accountMenu && <div ref={accountMenuRef} className={`profile-popover ${accountMenu}-anchor ${sidebarCollapsed ? 'rail-collapsed' : ''}`} role="menu"><div className="profile-popover-head">{profile.photo ? <img className="avatar profile-avatar-image" src={profile.photo} alt={profile.name} /> : <div className="avatar">{initials}</div>}<div><strong>{profile.name}</strong><small>{profile.major}</small></div></div><div className="profile-menu-list"><button role="menuitem" onClick={() => openAccountPage('My Profile')}><span className="feature-icon blue"><Icon name="user" size={17} /></span><span>My Profile</span></button><button role="menuitem" onClick={() => openAccountPage('Scheduling Preferences')}><span className="feature-icon purple"><Icon name="sliders" size={17} /></span><span>Scheduling Preferences</span></button><button role="menuitem" onClick={() => openAccountPage('Settings')}><span className="feature-icon teal"><Icon name="settings" size={17} /></span><span>Settings</span></button><button role="menuitem" onClick={() => openAccountPage('Help & Support')}><span className="feature-icon orange"><Icon name="help" size={17} /></span><span>Help & Support</span></button><button role="menuitem" className="sign-out-item" onClick={() => { setAccountMenu(null); setSignOutConfirm(true) }}><span className="feature-icon pink"><Icon name="logout" size={17} /></span><span>Sign Out</span></button></div></div>}
    <nav className="mobile-bottom-nav">{(['Dashboard', 'Degree Progress', 'Semester Planner', 'My Calendar', 'AI Advisor'] as Page[]).map(item => { const itemData = nav.find(entry => entry.label === item)!; return <button className={page === item ? 'active' : ''} key={item} onClick={() => go(item)}><Icon name={itemData.icon} size={19} /><span>{item === 'Degree Progress' ? 'Degree' : item === 'Semester Planner' ? 'Plan' : item === 'My Calendar' ? 'Calendar' : item === 'AI Advisor' ? 'Flow' : 'Home'}</span></button> })}</nav>
    {signOutConfirm && <div className="modal-backdrop" onMouseDown={() => setSignOutConfirm(false)}><section className="event-dialog sign-out-dialog" onMouseDown={event => event.stopPropagation()}><span className="feature-icon pink"><Icon name="logout" /></span><h2>Sign out of Flowsaic?</h2><p>Your saved schedules, calendar and preferences stay in your Flowsaic account.</p><div className="event-dialog-actions"><button className="ghost" onClick={() => setSignOutConfirm(false)}>Cancel</button><button className="sign-out-confirm" onClick={() => { setSignOutConfirm(false); signOut() }}>Sign out</button></div></section></div>}
    {toast && <div className="toast"><span className="soft-icon mint"><Icon name="check" /></span>{toast}<button onClick={() => setToast('')}>Dismiss</button></div>}
  </div>
}

export default App
