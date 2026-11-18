import { useEffect, useRef, useState } from 'react'
import { daysLabel, hhmmToDisplay } from '../api/adapters'
import type { ApiProposal } from '../api/types'
import { Icon } from '../components/Icon'

/** One chat turn. Flow's turns keep `memory` (what goes back in history: the text plus the schedules shown). */
export type AdvisorMessage = { role: 'user' | 'ai'; text: string; memory?: string; proposals?: ApiProposal[]; suggestions?: string[]; error?: boolean }

const STARTERS = {
  degree: 'Review my degree progress. What do I still need?',
  semester: 'What courses should I take next semester?',
  schedule: 'Build me a balanced schedule for next term around my commitments.',
  courses: 'Help me explore electives that fit my interests.',
}

const meetsText = (section: ApiProposal['sections'][number]) =>
  section.days && section.start_time ? `${daysLabel(section.days)} · ${hhmmToDisplay(section.start_time)}` : 'Online / TBA'

// Flow is POST /ai/advisor: a real conversation (10–30 s a reply). The chat lives in memory only.
// Every schedule card has been through the checker; Save calls POST /schedules with source "ai".
export function AIAdvisor({ messages, loading, studentName, onSend, onNew, onSaveProposal, onOpenProposal }: { messages: AdvisorMessage[]; loading: boolean; studentName: string; onSend: (text: string) => void; onNew: () => void; onSaveProposal: (proposal: ApiProposal) => Promise<string | null>; onOpenProposal: (proposal: ApiProposal) => void }) {
  const welcome = `Hi${studentName ? ` ${studentName.split(' ')[0]}` : ' there'}! I'm Flow. I can help you explore courses, review your degree progress, and build a schedule around your commitments. What would you like to work on today?`
  const [text, setText] = useState('')
  const [saved, setSaved] = useState<Record<string, string>>({})
  const [savingKey, setSavingKey] = useState('')
  const messagesRef = useRef<HTMLDivElement>(null)
  const started = messages.length > 0 || loading
  const send = (value = text) => {
    if (!value.trim() || loading) return
    onSend(value.trim())
    setText('')
  }
  const save = async (key: string, proposal: ApiProposal) => {
    setSavingKey(key)
    const name = await onSaveProposal(proposal)
    setSavingKey('')
    if (name) setSaved(current => ({ ...current, [key]: name }))
  }
  const newConversation = () => { onNew(); setText(''); setSaved({}) }
  useEffect(() => {
    if (!started || !messagesRef.current) return
    const frame = requestAnimationFrame(() => messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: 'smooth' }))
    return () => cancelAnimationFrame(frame)
  }, [messages, loading, started])
  const last = messages[messages.length - 1]
  // Flow's own quick replies (answers to its question, likely changes); generic ones if it gave none.
  const fallbackFollowUps = last?.proposals?.length ? ['Keep Fridays free', 'Make it a lighter load', last.proposals.some(p => p.warnings.length || p.conflicts.length) ? 'Explain the warnings' : 'Add an elective I’d enjoy'] : ['Build my schedule', 'What should I take next?', 'Review my degree progress']
  const followUps = last?.role === 'ai' && !last.error ? (last.suggestions?.length ? last.suggestions : fallbackFollowUps) : []
  // The newest schedule card in the whole conversation, pinned above the message box so its
  // buttons stay one click away however long the chat gets.
  const latest = (() => {
    for (let index = messages.length - 1; index >= 0; index--) {
      const proposals = messages[index].proposals
      if (proposals?.length) return { proposal: proposals[proposals.length - 1], key: `${index}-${proposals.length - 1}` }
    }
    return null
  })()

  return <section className={`advisor-chat flow-chat ${started ? 'conversation-active' : ''}`}><div className="chat-title"><img className="flow-avatar" src="/assets/flow-koi.png" alt="Flow koi icon" /><div><h2>Flow</h2><p>Your AI Academic Advisor</p>{!started && <small className="flow-data-note"><i /> Uses your degree audit, course catalog, and calendar</small>}</div>{started && <button className="new-conversation-button" disabled={loading} onClick={newConversation}><Icon name="plus" size={15} /> New Conversation</button>}</div>
    <div className="messages" ref={messagesRef}>{!started
      ? <div className="flow-welcome-screen"><div className="message ai flow-welcome">{welcome}</div><div className="flow-suggestions"><button onClick={() => send(STARTERS.degree)}><span className="soft-icon blue"><Icon name="chart" /></span><strong>Review My Degree</strong><small style={{ fontSize: 15 }}>Check progress and requirements</small></button><button onClick={() => send(STARTERS.semester)}><span className="soft-icon purple"><Icon name="layers" /></span><strong>Plan Next Semester</strong><small style={{ fontSize: 15 }}>Choose courses that move you forward</small></button><button onClick={() => send(STARTERS.schedule)}><span className="soft-icon orange"><Icon name="calendar" /></span><strong>Build My Schedule</strong><small style={{ fontSize: 15 }}>Fit classes around commitments</small></button><button onClick={() => send(STARTERS.courses)}><span className="soft-icon mint"><Icon name="book" /></span><strong>Explore Courses</strong><small style={{ fontSize: 15 }}>Compare options and sections</small></button></div></div>
      : <>{messages.map((message, index) => <div className={`flow-message-row ${message.role}`} key={index}><div className={`message ${message.role}`}>{message.text}
        {message.proposals?.map((proposal, proposalIndex) => {
          const key = `${index}-${proposalIndex}`
          const clean = !proposal.conflicts.length
          return <div className="flow-schedule-preview" key={key}><div className="flow-preview-head"><div><span className="eyebrow">SCHEDULE OPTION · {proposal.credits} CREDITS</span><strong>{proposal.name}</strong></div><span className={clean ? 'pill success' : 'pill orange'}>{clean ? <><Icon name="check" size={13} /> Checked</> : `${proposal.conflicts.length} ${proposal.conflicts.length === 1 ? 'conflict' : 'conflicts'}`}</span></div>
            <div className="flow-preview-courses">{proposal.sections.map(section => <span key={section.id}><b>{section.code}-{section.section_number}</b> {meetsText(section)}</span>)}</div>
            {proposal.explanation && <p>{proposal.explanation}</p>}
            {proposal.conflicts.map((item, i) => <p key={`c${i}`}><Icon name="calendar" size={14} /> {item.message}</p>)}
            {proposal.warnings.map((item, i) => <p key={`w${i}`}><Icon name="book" size={14} /> {item.message}</p>)}
            {clean && !proposal.warnings.length && <p><Icon name="check" size={14} /> No conflicts or warnings from the schedule checker</p>}
            <div className="flow-preview-actions"><button disabled={!clean || Boolean(saved[key]) || savingKey === key} title={clean ? '' : 'A schedule with conflicts can’t be saved'} onClick={() => save(key, proposal)}>{saved[key] ? 'Saved' : savingKey === key ? 'Saving…' : 'Save'}</button><button onClick={() => setText('Can you change this schedule to ')}>Modify</button><button className="primary" onClick={() => onOpenProposal(proposal)}>Open in Create Schedule</button></div></div>
        })}
        {message.role === 'ai' && index === messages.length - 1 && !loading && followUps.length > 0 && <div className="flow-follow-ups">{followUps.map(label => <button key={label} onClick={() => send(label)}>{label}</button>)}</div>}
      </div></div>)}
        {loading && <div className="flow-message-row ai"><div className="message ai">Flow is thinking… (this can take up to 30 seconds)</div></div>}</>}
    </div>
    <div className="flow-chat-footer">{latest && <div className="flow-latest-schedule" aria-label="Latest schedule"><div><span className="eyebrow">LATEST SCHEDULE · {latest.proposal.credits} CREDITS</span><strong>{latest.proposal.name}</strong><small>{latest.proposal.conflicts.length ? `${latest.proposal.conflicts.length} ${latest.proposal.conflicts.length === 1 ? 'conflict' : 'conflicts'} to fix` : latest.proposal.warnings.length ? `${latest.proposal.warnings.length} ${latest.proposal.warnings.length === 1 ? 'warning' : 'warnings'}` : 'Checked · no conflicts'}</small></div><div className="flow-latest-actions"><button className="ghost" disabled={Boolean(latest.proposal.conflicts.length) || Boolean(saved[latest.key]) || savingKey === latest.key} title={latest.proposal.conflicts.length ? 'A schedule with conflicts can’t be saved' : ''} onClick={() => save(latest.key, latest.proposal)}>{saved[latest.key] ? 'Saved' : savingKey === latest.key ? 'Saving…' : 'Save'}</button><button className="primary" onClick={() => onOpenProposal(latest.proposal)}><Icon name="spark" size={15} /> Open in Create Schedule</button></div></div>}<div className="composer"><input value={text} disabled={loading} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} placeholder="Ask Flow about your academic plan..." /><button disabled={loading} onClick={() => send()}>Send</button></div><p className="flow-disclaimer">Flow is an AI assistant. Confirm important academic decisions and graduation requirements with your Southern Arkansas University advisor.</p></div></section>
}
