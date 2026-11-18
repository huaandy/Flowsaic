import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { daysLabel, deliveryText, placeText, prereqText, scheduleText } from '../api/adapters'
import type { ApiCatalogCourse, CourseQuery, Delivery } from '../api/types'
import { Icon } from '../components/Icon'

const PAGE = 24
export type CatalogFocus = { code: string; id?: string; nonce: number }

const ELIGIBILITY_TEXT = { eligible: 'Eligible', completed: 'Completed', in_progress: 'In progress', missing_prereq: 'Prerequisite needed' } as const

// Courses offered in the current registration term, from GET /courses (search and filters run
// on the server, so paging stays right). Eligibility and plan flags are the student's own.
// Ratings are mock: no rating data exists yet, so courses start with no reviews.
export function Catalog({ termId, termName, focus, draftCodes, addToDraft, removeFromDraft, openSchedule, onError }: { termId: string; termName: string; focus: CatalogFocus | null; draftCodes: Set<string>; addToDraft: (course: ApiCatalogCourse) => void; removeFromDraft: (code: string) => void; openSchedule: (course: ApiCatalogCourse) => void; onError: (error: unknown) => void }) {
  const [query, setQuery] = useState(focus?.code ?? '')
  const [search, setSearch] = useState(focus?.code ?? '')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [expanded, setExpanded] = useState(focus?.code ?? '')
  const [department, setDepartment] = useState('All departments')
  const [level, setLevel] = useState('All levels')
  const [credits, setCredits] = useState('Any credits')
  const [prerequisite, setPrerequisite] = useState('Any prerequisite')
  const [delivery, setDelivery] = useState('Any format')
  const [days, setDays] = useState('Any days')
  const [availability, setAvailability] = useState('Any availability')
  const [courses, setCourses] = useState<ApiCatalogCourse[]>([])
  const [total, setTotal] = useState(0)
  const [departments, setDepartments] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [focusDetail, setFocusDetail] = useState<ApiCatalogCourse | null>(null)
  const [ratings, setRatings] = useState<Record<string, { rating: number; count: number }>>({})
  const [ratingDraft, setRatingDraft] = useState<Record<string, number>>({})
  const requestId = useRef(0)

  // A course opened from the header search, Degree Progress or Flow.
  useEffect(() => {
    if (!focus) return
    setQuery(focus.code)
    setSearch(focus.code)
    setExpanded(focus.code)
    setFocusDetail(null)
    if (focus.id) api.course(focus.id, termId).then(setFocusDetail).catch(onError)
  }, [focus?.nonce])

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), 300)
    return () => clearTimeout(timer)
  }, [query])

  const buildQuery = (offset: number): CourseQuery => ({
    term_id: termId, search: search || undefined, limit: PAGE, offset,
    department: department === 'All departments' ? undefined : department,
    level: level === 'All levels' ? undefined : Number(level),
    credits: credits === 'Any credits' ? undefined : Number(credits),
    eligible_only: prerequisite === 'Eligible now', on_my_plan: prerequisite === 'On my plan',
    delivery: delivery === 'Any format' ? undefined : (delivery === 'Online' ? 'online' : 'in_person') as Delivery,
    days: days === 'Any days' ? undefined : days,
    open_only: availability === 'Open sections',
  })

  const load = (offset: number) => {
    if (!termId) return
    const id = ++requestId.current
    setLoading(true)
    api.courses(buildQuery(offset)).then(result => {
      if (id !== requestId.current) return
      setCourses(current => offset ? [...current, ...result.courses] : result.courses)
      setTotal(result.total)
      setDepartments(result.departments)
    }).catch(onError).finally(() => { if (id === requestId.current) setLoading(false) })
  }
  useEffect(() => load(0), [termId, search, department, level, credits, prerequisite, delivery, days, availability])

  const visible = focusDetail && !courses.some(course => course.code === focusDetail.code) ? [focusDetail, ...courses] : courses
  const submitRating = (course: ApiCatalogCourse) => {
    const value = ratingDraft[course.code]
    if (!value) return
    const current = ratings[course.code] || { rating: 0, count: 0 }
    setRatings({ ...ratings, [course.code]: { rating: (current.rating * current.count + value) / (current.count + 1), count: current.count + 1 } })
    setRatingDraft({ ...ratingDraft, [course.code]: 0 })
  }
  const clearFilters = () => { setDepartment('All departments'); setLevel('All levels'); setCredits('Any credits'); setPrerequisite('Any prerequisite'); setDelivery('Any format'); setDays('Any days'); setAvailability('Any availability') }

  return <>
    <div className="catalog-tools card"><div className="searchbar"><Icon name="search" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by course, subject, or keyword…" /><button onClick={() => setFiltersOpen(value => !value)}>Filters {filtersOpen ? '−' : '+'}</button></div>{filtersOpen && <div className="catalog-filters"><label>Department<select value={department} onChange={event => setDepartment(event.target.value)}><option>All departments</option>{departments.map(value => <option key={value}>{value}</option>)}</select></label><label>Level<select value={level} onChange={event => setLevel(event.target.value)}><option>All levels</option><option>1000</option><option>2000</option><option>3000</option><option>4000</option></select></label><label>Credits<select value={credits} onChange={event => setCredits(event.target.value)}><option>Any credits</option><option value="1">1 credit</option><option value="2">2 credits</option><option value="3">3 credits</option><option value="4">4 credits</option></select></label><label>Prerequisites<select value={prerequisite} onChange={event => setPrerequisite(event.target.value)}><option>Any prerequisite</option><option>Eligible now</option><option>On my plan</option></select></label><label>Delivery<select value={delivery} onChange={event => setDelivery(event.target.value)}><option>Any format</option><option>In person</option><option>Online</option></select></label><label>Days<select value={days} onChange={event => setDays(event.target.value)}><option>Any days</option><option value="MW">Mon/Wed</option><option value="TR">Tue/Thu</option><option value="MWF">Mon/Wed/Fri</option></select></label><label>Availability<select value={availability} onChange={event => setAvailability(event.target.value)}><option>Any availability</option><option>Open sections</option></select></label><button className="ghost clear-filters" onClick={clearFilters}>Clear filters</button></div>}</div>
    <div className="catalog-results-head"><span>{loading && !courses.length ? 'Loading…' : `${total} ${total === 1 ? 'course' : 'courses'} in ${termName}`}</span><small>Eligibility uses your completed and in-progress courses. The schedule checker in Create Schedule has the final word on conflicts.</small></div>
    <div className="catalog-grid">{visible.map(course => {
      const isExpanded = expanded === course.code
      const eligible = course.eligibility !== 'missing_prereq'
      const activeSections = course.sections.filter(section => section.active)
      const full = course.offered && course.seats_open === 0
      const planned = draftCodes.has(course.code)
      const rating = ratings[course.code]
      const typicalDays = Array.from(new Set(activeSections.map(section => daysLabel(section.days)).filter(Boolean))).join(' or ') || 'Online / TBA'
      return <article className={`card course catalog-course ${focus && course.code === focus.code ? 'focused-course' : ''} ${!eligible ? 'course-ineligible' : ''}`} key={course.id}>
        <div className="catalog-course-top"><span className="course-code">{course.code}</span><span className="catalog-badges"><span className="pill">{course.credits} credits</span><span className={`eligibility ${eligible ? 'eligible' : 'ineligible'}`}>{ELIGIBILITY_TEXT[course.eligibility]}</span></span></div>
        <h2>{course.title}</h2><p>{course.description || 'No catalog description.'}</p>
        <div className="course-meta-row"><span>{course.department ?? 'Department not listed'} · {course.level}-level</span><span>{course.offered ? deliveryText(course.sections) : `Not offered in ${termName}`}</span></div>
        <div className="professor-rating"><span className="stars">★</span><strong>{rating ? rating.rating.toFixed(1) : '—'}</strong><span>{rating ? `${rating.count} student ${rating.count === 1 ? 'review' : 'reviews'}` : 'No reviews yet'}</span></div>
        <div className="course-status-stack">
          {course.eligibility === 'missing_prereq' && <span className="course-status prerequisite-status"><Icon name="book" size={14} />Complete {prereqText(course.missing_prereqs)} before enrolling</span>}
          {course.eligibility === 'completed' && <span className="course-status prerequisite-status"><Icon name="check" size={14} />You already passed this course</span>}
          {course.eligibility === 'in_progress' && <span className="course-status prerequisite-status"><Icon name="calendar" size={14} />You’re taking this course now</span>}
          {full && <span className="course-status enrolled-conflict"><Icon name="calendar" size={14} />Every section is full</span>}
          {!course.offered && <span className="course-status commitment-conflict"><Icon name="calendar" size={14} />Not offered in {termName}</span>}
          {course.on_my_plan && <span className="course-status eligible-status"><Icon name="check" size={14} />Counts toward {course.requirement_names[0]}</span>}
          {course.eligibility === 'eligible' && !course.on_my_plan && course.offered && <span className="course-status eligible-status"><Icon name="check" size={14} />Prerequisites met{course.requirement_names.length ? '' : ' · not on your degree plan'}</span>}
        </div>
        <div className="course-foot"><button className="course-detail-button" onClick={() => setExpanded(isExpanded ? '' : course.code)}>{isExpanded ? 'Hide details' : 'Course details'} <Icon name="arrow" size={14} /></button><span className="catalog-plan-action">{planned && <small>In your {termName} draft</small>}<button disabled={!course.offered} className={planned ? 'ghost' : 'primary'} onClick={() => planned ? removeFromDraft(course.code) : addToDraft(course)}>{planned ? 'Remove from plan' : 'Add to plan'}</button></span></div>
        {isExpanded && <div className="course-detail-panel"><div className="detail-facts"><span><b>Requirement</b>{course.requirement_names.join(' · ') || 'Not on your degree plan'}</span><span><b>Prerequisite</b>{prereqText(course.prereqs)}</span><span><b>Typical days</b>{typicalDays}</span></div>{course.other_requirements && <p>{course.other_requirements}</p>}<h3>{course.offered ? 'Available sections' : `No sections in ${termName}`}</h3>{course.sections.map(section => <div className="catalog-section" key={section.id}><div><strong>Section {section.section_number} · {scheduleText(section)}</strong><span>{section.instructor} · {placeText(section)}</span></div><div className="section-rating"><span>{section.delivery === 'online' ? 'Online / TBA' : 'In person'}</span><small>{section.active ? `${section.enrolled}/${section.capacity} enrolled` : 'No longer offered'}</small></div><span className={section.seats_open && section.active ? 'seats-open' : 'seats-full'}>{!section.active ? 'Dropped' : section.seats_open ? `${section.seats_open} seats` : 'Full'}</span></div>)}<div className="rating-form"><span>Rate this course</span><div>{[1, 2, 3, 4, 5].map(value => <button className={(ratingDraft[course.code] || 0) >= value ? 'selected' : ''} key={value} onClick={() => setRatingDraft({ ...ratingDraft, [course.code]: value })}>★</button>)}</div><button className="ghost" disabled={!ratingDraft[course.code]} onClick={() => submitRating(course)}>Submit rating</button></div><button className="schedule-section-link" disabled={!course.offered} onClick={() => openSchedule(course)}>Select a section in Create Schedule <Icon name="arrow" size={14} /></button></div>}
      </article>
    })}</div>
    {courses.length < total && <div className="catalog-results-head"><button className="ghost" disabled={loading} onClick={() => load(courses.length)}>{loading ? 'Loading…' : `Load more (${total - courses.length} left)`}</button></div>}
    {!visible.length && !loading && <div className="card catalog-empty"><Icon name="search" /><strong>No courses match these filters</strong><span>Clear one or more filters to broaden the results.</span></div>}
  </>
}
