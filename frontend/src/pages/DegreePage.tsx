import { useState } from 'react'
import { prereqText } from '../api/adapters'
import type { ApiProgress, ApiProgressCourse, ApiRequirementNode, RequirementStatus } from '../api/types'
import { Icon } from '../components/Icon'

type RowStatus = 'Completed' | 'In progress' | 'Planned' | 'Remaining'
const TONES = ['blue', 'purple', 'orange', 'mint']
const STATUS_TEXT: Record<RequirementStatus, string> = { met: 'Met', in_progress: 'In progress', not_met: 'Not met', not_tracked: 'Not tracked' }

/** Every course listed under a requirement, its child groups and its electives. */
function allCourses(node: ApiRequirementNode): ApiProgressCourse[] {
  return [...node.courses, ...node.electives.flatMap(e => e.courses), ...node.children.flatMap(allCourses)]
}

function nodePercent(node: ApiRequirementNode) {
  if (node.status === 'met') return 100
  if (node.hours_required) return Math.min(100, Math.round(((node.hours_done + node.hours_in_progress * 0.65) / node.hours_required) * 100))
  const courses = allCourses(node).filter(c => c.status !== 'option' && c.status !== 'counted_elsewhere')
  if (!courses.length) return 0
  return Math.round((courses.filter(c => c.status === 'passed').length + courses.filter(c => c.status === 'in_progress').length * 0.65) / courses.length * 100)
}

// The requirement tree, can-take and blocked lists all come from GET /me/progress (the student's
// mySAU audit, or their public degree map). "Planned" = in the Create Schedule draft.
export function DegreePage({ progress, termName, draftCodes, openCatalog, addToPlan, askFlow }: { progress: ApiProgress | null; termName: string; draftCodes: Set<string>; openCatalog: (code: string) => void; addToPlan: (code: string) => void; askFlow: (question: string) => void }) {
  const [expanded, setExpanded] = useState<string[]>([])
  const [auditOpen, setAuditOpen] = useState(false)
  if (!progress) return <div className="card catalog-empty"><Icon name="chart" /><strong>Loading your degree progress…</strong></div>
  const statusFor = (course: ApiProgressCourse): RowStatus => course.status === 'passed' ? 'Completed' : course.status === 'in_progress' ? 'In progress' : draftCodes.has(course.code) ? 'Planned' : 'Remaining'
  const rowLabel = (course: ApiProgressCourse) => course.status === 'option' && !draftCodes.has(course.code) ? 'Option' : course.status === 'counted_elsewhere' ? 'Counted elsewhere' : statusFor(course)
  const canTake = new Map(progress.can_take.map(course => [course.code, course]))
  const blocked = new Map(progress.blocked.map(course => [course.code, course]))
  const { earned, in_progress: inProgressCredits, required } = progress.hours
  const plannedCredits = progress.can_take.filter(c => draftCodes.has(c.code)).reduce((total, c) => total + c.credits, 0)
  const projectedCredits = earned + inProgressCredits + plannedCredits
  const remainingAfter = required ? Math.max(0, required - projectedCredits) : null
  const projection = remainingAfter === null ? 'Not known yet' : remainingAfter === 0 ? 'Requirements covered' : `About ${Math.ceil(remainingAfter / 15)} more ${Math.ceil(remainingAfter / 15) === 1 ? 'semester' : 'semesters'}`
  const program = progress.source === 'audit' ? 'Your mySAU degree audit' : progress.plan ? `${progress.plan.name} · ${progress.plan.catalog_year} catalog` : 'No degree plan yet'
  const remainingCourses = progress.requirements.flatMap(allCourses).filter(c => statusFor(c) === 'Remaining' && c.status === 'needed')

  const courseRow = (course: ApiProgressCourse, key: string) => {
    const status = statusFor(course)
    const offer = canTake.get(course.code)
    const block = blocked.get(course.code)
    const detail = offer ? `${offer.credits} credits · offered in ${termName} · ${offer.seats_open} open seats` : block ? `Needs ${prereqText(block.missing_prereqs)}` : status === 'Remaining' ? `Not available in ${termName}` : course.title ? 'On your record' : ''
    return <div className="audit-course" key={key}><span className={`audit-status ${status.toLowerCase().replace(' ', '-')}`}><Icon name={status === 'Completed' ? 'check' : status === 'Remaining' ? 'plus' : 'calendar'} size={14} /></span><span><strong>{course.code}{course.title ? ` · ${course.title}` : ''}</strong><small>{detail}</small></span><em className={`record-label ${status.toLowerCase().replace(' ', '-')}`}>{rowLabel(course)}</em>{status === 'Remaining' && <span className="audit-actions"><button onClick={() => openCatalog(course.code)}>View course</button>{offer && <button onClick={() => addToPlan(course.code)}>Add to plan</button>}</span>}</div>
  }
  const details = (node: ApiRequirementNode, depth: number, path: string): React.ReactNode[] => [
    ...(depth > 0 ? [<div className="audit-course" key={`${path}-head`}><span className={`audit-status ${node.status === 'met' ? 'completed' : node.status === 'in_progress' ? 'in-progress' : 'remaining'}`}><Icon name={node.status === 'met' ? 'check' : 'layers'} size={14} /></span><span><strong>{node.name}</strong><small>{node.hours_required ? `${node.hours_done}${node.hours_in_progress ? ` + ${node.hours_in_progress} in progress` : ''} of ${node.hours_required} hours` : node.rule === 'choose_hours' ? 'Choose courses' : 'Every course below'}</small></span><em className={`record-label ${node.status === 'met' ? 'completed' : node.status === 'in_progress' ? 'in-progress' : 'remaining'}`}>{STATUS_TEXT[node.status]}</em></div>] : []),
    ...node.courses.map((course, index) => courseRow(course, `${path}-c${index}`)),
    ...node.electives.map((elective, index) => <div className="audit-course" key={`${path}-e${index}`}><span className={`audit-status ${elective.status === 'met' ? 'completed' : elective.status === 'in_progress' ? 'in-progress' : 'remaining'}`}><Icon name={elective.status === 'met' ? 'check' : 'book'} size={14} /></span><span><strong>{elective.text}</strong><small>{elective.hours_done} hours done{elective.hours_in_progress ? ` · ${elective.hours_in_progress} in progress` : ''}{elective.courses.length ? ` · ${elective.courses.map(c => c.code).join(', ')}` : ''}</small></span><em className={`record-label ${elective.status === 'met' ? 'completed' : elective.status === 'in_progress' ? 'in-progress' : 'remaining'}`}>{elective.status === 'met' ? 'Met' : elective.status === 'in_progress' ? 'In progress' : 'Elective'}</em></div>),
    ...(node.note && (node.status === 'not_tracked' || !node.courses.length) ? [<div className="audit-course" key={`${path}-note`}><span className="audit-status planned"><Icon name="help" size={14} /></span><span><strong>Note</strong><small>{node.note}</small></span></div>] : []),
    ...node.children.flatMap((child, index) => details(child, depth + 1, `${path}-${index}`)),
  ]

  return <>
    <div className="degree-summary-strip card">
      <div><span>Official record</span><strong>{required ? `${earned} / ${required} credits` : `${earned} credits`}</strong><small>{progress.source === 'audit' ? 'From your mySAU degree audit' : 'From your completed courses'}</small></div>
      <div><span>In progress</span><strong>{inProgressCredits} credits</strong><small>Counts once grades are posted</small></div>
      <div><span>You can take in {termName}</span><strong>{progress.can_take.length} courses</strong><small className="estimate-label">{progress.blocked.length} more blocked by prerequisites</small></div>
    </div>
    <div className="degree-layout">
      <article className="card degree-requirements">
        <div className="section-head degree-section-head"><div><h2 className="module-title"><span className="feature-icon green"><Icon name="check" size={17} /></span>Requirement groups</h2><p>Southern Arkansas University · {program}</p></div></div>
        {!progress.requirements.length && <div className="catalog-empty"><Icon name="book" /><strong>No requirements to show yet</strong><span>{progress.source === 'none' ? 'Connect mySAU on your profile to load your degree audit.' : 'This plan has no requirement groups.'}</span></div>}
        {progress.requirements.map((group, groupIndex) => {
          const courses = allCourses(group)
          const satisfied = courses.filter(c => statusFor(c) === 'Completed').length
          const inProgress = courses.filter(c => statusFor(c) === 'In progress').length
          const planned = courses.filter(c => statusFor(c) === 'Planned').length
          const remaining = courses.filter(c => statusFor(c) === 'Remaining' && c.status === 'needed').length
          const percent = nodePercent(group)
          const isExpanded = expanded.includes(group.name)
          return <section className={`audit-group ${isExpanded ? 'expanded' : ''}`} key={`${group.name}-${groupIndex}`}>
            <button className="requirement-summary" onClick={() => setExpanded(current => current.includes(group.name) ? current.filter(name => name !== group.name) : [...current, group.name])}>
              <span className={`soft-icon ${TONES[groupIndex % TONES.length]}`}><Icon name={groupIndex === 0 ? 'book' : 'check'} /></span>
              <span className="requirement-copy"><strong>{group.name}</strong><small>{STATUS_TEXT[group.status]} · {satisfied} completed · {inProgress} in progress · {planned} planned · {remaining} remaining</small></span>
              <span className="req-progress"><b>{percent}%</b><span className="bar"><i style={{ width: `${percent}%` }} /></span></span>
              <span className={`disclosure ${isExpanded ? 'open' : ''}`}><Icon name="arrow" size={17} /></span>
            </button>
            {isExpanded && <div className="requirement-details">{details(group, 0, String(groupIndex))}</div>}
          </section>
        })}
        {[{ key: 'can-take', name: `You can take in ${termName}`, small: `${progress.can_take.length} courses offered, not taken yet, prerequisites met`, tone: 'blue', icon: 'book' },
          { key: 'blocked', name: 'Blocked by prerequisites', small: `${progress.blocked.length} needed courses wait on a prerequisite`, tone: 'orange', icon: 'calendar' }].map(extraGroup => {
          const isExpanded = expanded.includes(extraGroup.key)
          return <section className={`audit-group ${isExpanded ? 'expanded' : ''}`} key={extraGroup.key}>
            <button className="requirement-summary" onClick={() => setExpanded(current => current.includes(extraGroup.key) ? current.filter(name => name !== extraGroup.key) : [...current, extraGroup.key])}>
              <span className={`soft-icon ${extraGroup.tone}`}><Icon name={extraGroup.icon} /></span>
              <span className="requirement-copy"><strong>{extraGroup.name}</strong><small>{extraGroup.small}</small></span>
              <span className="req-progress" />
              <span className={`disclosure ${isExpanded ? 'open' : ''}`}><Icon name="arrow" size={17} /></span>
            </button>
            {isExpanded && extraGroup.key === 'can-take' && <div className="requirement-details">{progress.can_take.map(course => <div className="audit-course" key={course.code}><span className={`audit-status ${draftCodes.has(course.code) ? 'planned' : 'remaining'}`}><Icon name={draftCodes.has(course.code) ? 'calendar' : 'plus'} size={14} /></span><span><strong>{course.code}{course.title ? ` · ${course.title}` : ''}</strong><small>{course.credits} credits · {course.kind} · {course.seats_open} open seats · {course.counts_toward.join('; ')}</small></span><em className={`record-label ${draftCodes.has(course.code) ? 'planned' : 'remaining'}`}>{draftCodes.has(course.code) ? 'Planned' : 'Can take'}</em>{!draftCodes.has(course.code) && <span className="audit-actions"><button onClick={() => openCatalog(course.code)}>View course</button><button onClick={() => addToPlan(course.code)}>Add to plan</button></span>}</div>)}{!progress.can_take.length && <div className="audit-course"><span /><span><small>Nothing listed for {termName}.</small></span></div>}</div>}
            {isExpanded && extraGroup.key === 'blocked' && <div className="requirement-details">{progress.blocked.map(course => <div className="audit-course" key={course.code}><span className="audit-status remaining"><Icon name="book" size={14} /></span><span><strong>{course.code}{course.title ? ` · ${course.title}` : ''}</strong><small>Needs {prereqText(course.missing_prereqs)} (passed or in progress) · {course.counts_toward.join('; ')}</small></span><em className="record-label remaining">Blocked</em><span className="audit-actions"><button onClick={() => openCatalog(course.code)}>View course</button></span></div>)}{!progress.blocked.length && <div className="audit-course"><span /><span><small>Nothing is blocked.</small></span></div>}</div>}
          </section>
        })}
      </article>
      <aside className="degree-side">
        <article className="card projection degree-projection-card"><span className="eyebrow">GRADUATION PROJECTION</span><h2>{projection}</h2><p>Estimate at 15 credits a term. Completed credits, current enrollment and your {termName} draft are kept separate.</p><div className="projection-meter"><div className="bar"><i style={{ width: `${required ? Math.min(100, projectedCredits / required * 100) : 0}%` }} /></div><span><b>{projectedCredits}</b> projected credits</span></div><div className="projection-legend"><span><i className="confirmed" />{earned} completed</span><span><i className="in-progress" />{inProgressCredits} in progress</span><span><i className="estimated" />{plannedCredits} planned</span></div><button className="primary wide" onClick={() => setAuditOpen(true)}>View detailed audit</button></article>
        <article className="ai-card builder-ai-insight degree-ai-insight"><img className="ai-orb flow-koi-icon" src="/assets/flow-koi.png" alt="Flow koi icon" /><div><span className="eyebrow">AI INSIGHT</span><h3>Need degree guidance?</h3><p>Review requirements, course sequencing, and graduation timing.</p><button onClick={() => askFlow('Review my degree requirements and tell me what I should prioritize next.')}><Icon name="chat" size={15} /> Ask Flow</button></div></article>
      </aside>
    </div>
    {auditOpen && <div className="modal-backdrop" onMouseDown={() => setAuditOpen(false)}><section className="event-dialog degree-audit-dialog" onMouseDown={event => event.stopPropagation()}><div className="audit-dialog-head"><div><span className="eyebrow">DETAILED DEGREE AUDIT</span><h2>{progress.plan?.name ?? (progress.source === 'audit' ? 'Your mySAU audit' : 'Degree progress')}</h2><p>Completion counts only passed courses (F and W don’t count). In-progress and planned courses stay estimates until grades are posted. Confirm with your SAU advisor.</p></div><button className="ghost square-button" onClick={() => setAuditOpen(false)}>×</button></div><div className="audit-summary-grid"><span><b>{earned}</b> completed credits</span><span><b>{inProgressCredits}</b> in-progress credits</span><span><b>{plannedCredits}</b> planned credits</span><span><b>{remainingCourses.length}</b> remaining courses</span></div>{progress.requirements.map((group, index) => <div className="audit-dialog-group" key={`${group.name}-${index}`}><strong>{group.name}</strong><span>{STATUS_TEXT[group.status]} · {group.hours_done}{group.hours_required ? ` of ${group.hours_required}` : ''} hours</span></div>)}{progress.open_electives.length > 0 && <div className="audit-dialog-group"><strong>Open electives</strong><span>{progress.open_electives.join(' · ')}</span></div>}</section></div>}
  </>
}

