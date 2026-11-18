import { useEffect, useState } from 'react'
import type { EventDraft } from '../api/adapters'
import { Icon } from '../components/Icon'
import type { CalendarEvent, EventCategory } from '../types'


type ScheduleOption={id:string;name:string}

// My commitments come from /me/events (add, edit, delete). Classes are the sections of the saved
// schedule picked here, read-only. "Proposed" events are the Create Schedule draft, also read-only.
export function CalendarPage({events,classEvents,proposedEvents,schedules,activeScheduleId,onScheduleChange,onAdd,onUpdate,onRemove,askFlow}:{events:CalendarEvent[];classEvents:CalendarEvent[];proposedEvents:CalendarEvent[];schedules:ScheduleOption[];activeScheduleId:string;onScheduleChange:(id:string)=>void;onAdd:(draft:EventDraft)=>Promise<boolean>;onUpdate:(id:string,draft:EventDraft)=>Promise<boolean>;onRemove:(id:string)=>Promise<boolean>;askFlow:()=>void}) {
  const dayKeys: CalendarEvent['day'][]=['Mon','Tue','Wed','Thu','Fri']
  const categories:EventCategory[]=['Academic','Work','Personal / Study','Extracurricular']
  const categoryTone:Record<EventCategory,string>={Academic:'blue',Work:'orange','Personal / Study':'purple',Extracurricular:'mint'}
  const [view,setView]=useState<'day'|'week'|'month'>(()=>{const saved=localStorage.getItem('flowsaic-calendar-view');return saved==='day'||saved==='month'?saved:'week'})
  const [anchor,setAnchor]=useState(()=>{const saved=localStorage.getItem('flowsaic-calendar-date');return saved?new Date(saved):new Date()})
  const [visibleCategories,setVisibleCategories]=useState<EventCategory[]>(categories)
  const [showProposed,setShowProposed]=useState(true)
  const [dialogOpen,setDialogOpen]=useState(false)
  const [editingId,setEditingId]=useState<string|null>(null)
  const [applyScope,setApplyScope]=useState<'occurrence'|'series'>('series')
  const [draft,setDraft]=useState({day:'Mon' as CalendarEvent['day'],title:'',start:'12:00',end:'13:00',meta:'',category:'Personal / Study' as EventCategory,recurrence:'Weekly' as CalendarEvent['recurrence'],priority:'Normal' as CalendarEvent['priority'],fixed:false})
  const toInputTime=(time:string)=>{
    const [clock,period]=time.split(' ')
    const [hourText,minute]=clock.split(':')
    let hour=Number(hourText)
    if(period==='PM'&&hour!==12) hour+=12
    if(period==='AM'&&hour===12) hour=0
    return `${String(hour).padStart(2,'0')}:${minute}`
  }
  const toDisplayTime=(time:string)=>{
    const [hourText,minute]=time.split(':')
    const hour=Number(hourText)
    return `${hour%12||12}:${minute} ${hour>=12?'PM':'AM'}`
  }
  const asHour=(time:string)=>{
    const input=toInputTime(time)
    const [hour,minute]=input.split(':').map(Number)
    return hour+minute/60
  }
  const allEvents=[...classEvents,...events]
  const selectedEvent=[...allEvents,...proposedEvents].find(event=>event.id===editingId)
  const [busy,setBusy]=useState(false)
  const isReadOnly=Boolean(selectedEvent?.readOnly)
  useEffect(()=>{localStorage.setItem('flowsaic-calendar-view',view);localStorage.setItem('flowsaic-calendar-date',anchor.toISOString())},[view,anchor])
  const startOfWeek=(date:Date)=>{
    const start=new Date(date)
    const weekday=start.getDay()
    start.setDate(start.getDate()-(weekday===0?6:weekday-1))
    return start
  }
  const weekStart=startOfWeek(anchor)
  const dayDates=dayKeys.map((key,index)=>{const date=new Date(weekStart);date.setDate(date.getDate()+index);return {key,date}})
  const activeDay=(anchor.getDay()>=1&&anchor.getDay()<=5?dayKeys[anchor.getDay()-1]:'Mon')
  const shownDays=view==='day'?dayDates.filter(day=>day.key===activeDay):dayDates
  const visibleEvents=[...allEvents.filter(event=>visibleCategories.includes(event.category)),...(showProposed?proposedEvents:[])]
  const dateRange=view==='month'
    ? anchor.toLocaleDateString('en-US',{month:'long',year:'numeric'})
    : view==='day'
      ? anchor.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'})
      : `${dayDates[0].date.toLocaleDateString('en-US',{month:'long',day:'numeric'})}–${dayDates[4].date.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}`
  const navigate=(direction:number)=>{
    const next=new Date(anchor)
    if(view==='day'){
      next.setDate(next.getDate()+direction)
      while(next.getDay()===0||next.getDay()===6) next.setDate(next.getDate()+direction)
    }
    else if(view==='week') next.setDate(next.getDate()+direction*7)
    else next.setMonth(next.getMonth()+direction)
    setAnchor(next)
  }
  const openNew=()=>{setEditingId(null);setApplyScope('series');setDraft({day:activeDay,title:'',start:'12:00',end:'13:00',meta:'',category:'Personal / Study',recurrence:'Weekly',priority:'Normal',fixed:false});setDialogOpen(true)}
  const openEvent=(event:CalendarEvent)=>{setEditingId(event.id);setApplyScope('series');setDraft({day:event.day,title:event.title,start:toInputTime(event.time),end:toInputTime(event.endTime),meta:event.meta,category:event.category,recurrence:event.recurrence,priority:event.priority,fixed:event.fixed});setDialogOpen(true)}
  const saveEvent=async()=>{
    if(!draft.title.trim()||draft.end<=draft.start||busy) return
    const next:EventDraft={...draft,category:draft.category==='Academic'?'Personal / Study':draft.category,recurrence:editingId&&selectedEvent?.recurrence==='Weekly'&&applyScope==='occurrence'?'None':draft.recurrence}
    setBusy(true)
    const ok=editingId?await onUpdate(editingId,next):await onAdd(next)
    setBusy(false)
    if(ok) setDialogOpen(false)
  }
  const removeEvent=async(id:string)=>{setBusy(true);const ok=await onRemove(id);setBusy(false);if(ok)setDialogOpen(false)}
  const draftConflict=allEvents.some(event=>event.id!==editingId&&event.day===draft.day&&asHour(event.time)<Number(draft.end.split(':')[0])+Number(draft.end.split(':')[1])/60&&Number(draft.start.split(':')[0])+Number(draft.start.split(':')[1])/60<asHour(event.endTime))
  const monthStart=new Date(anchor.getFullYear(),anchor.getMonth(),1)
  const monthGridStart=startOfWeek(monthStart)
  const monthDates=Array.from({length:42},(_,index)=>{const date=new Date(monthGridStart);date.setDate(date.getDate()+index);return date})
  const eventStyle=(event:CalendarEvent,dayEvents:CalendarEvent[])=>{
    const start=asHour(event.time)
    const end=asHour(event.endTime)
    const overlaps=dayEvents.filter(other=>other.id!==event.id&&start<asHour(other.endTime)&&asHour(other.time)<end)
    // Two lanes: events sharing a slot alternate by start time, then id (so equal starts split too).
    const lane=[event,...overlaps].sort((first,second)=>asHour(first.time)-asHour(second.time)||first.id.localeCompare(second.id)).indexOf(event)%2
    return {top:`${(start-8)*76+5}px`,height:`${Math.max((end-start)*76-9,34)}px`,left:overlaps.length?`${lane*50+3}%`:'3%',width:overlaps.length?'47%':'94%'}
  }
  return <div className="calendar-workspace">
    <article className="card calendar-card">
      <div className="calendar-toolbar">
        <div className="calendar-date-nav"><button className="ghost square-button" aria-label="Previous" onClick={()=>navigate(-1)}><span className="previous-arrow"><Icon name="arrow" size={16}/></span></button><button className="ghost" onClick={()=>setAnchor(new Date())}>Today</button><button className="ghost square-button" aria-label="Next" onClick={()=>navigate(1)}><Icon name="arrow" size={16}/></button><div><h2>{dateRange}</h2><p>{visibleEvents.length} visible events · 8:00 AM–8:00 PM</p></div></div>
        <div className="calendar-toolbar-actions">{schedules.length>0&&<label className="calendar-schedule-select"><span>Classes from</span><select value={activeScheduleId} onChange={event=>onScheduleChange(event.target.value)}><option value="">No saved schedule</option>{schedules.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}<div className="view-tabs">{(['day','week','month'] as const).map(option=><button key={option} className={view===option?'active':''} onClick={()=>setView(option)}>{option[0].toUpperCase()+option.slice(1)}</button>)}</div><button className="ghost ask-calendar-button" onClick={askFlow}><Icon name="chat" size={16}/> Ask Flow</button><button className="primary" onClick={openNew}><Icon name="plus"/> Add event</button></div>
      </div>
      <div className="calendar-category-filters">{categories.map(category=><button key={category} className={visibleCategories.includes(category)?'active':''} onClick={()=>setVisibleCategories(current=>current.includes(category)?current.filter(item=>item!==category):[...current,category])}><i className={categoryTone[category]}/>{category}</button>)}{proposedEvents.length>0&&<button className={showProposed?'active proposed-filter':''} onClick={()=>setShowProposed(value=>!value)}><i className="proposed"/>Proposed schedule</button>}</div>
      {view==='month'
        ? <div className="calendar-month"><div className="calendar-month-weekdays">{['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(day=><span key={day}>{day}</span>)}</div><div className="calendar-month-grid">{monthDates.map(date=>{const dayKey=dayKeys[date.getDay()-1];const dateEvents=dayKey?visibleEvents.filter(event=>event.day===dayKey):[];return <button disabled={!dayKey} key={date.toISOString()} className={`${date.getMonth()!==anchor.getMonth()?'outside':''} ${date.toDateString()===anchor.toDateString()?'selected':''}`} onClick={()=>{setAnchor(date);setView('day')}}><strong>{date.getDate()}</strong>{dateEvents.slice(0,3).map(event=><span className={event.tone} key={event.id}>{event.title}</span>)}{dateEvents.length>3&&<small>+{dateEvents.length-3} more</small>}</button>})}</div></div>
        : <div className="calendar-time-shell"><div className="calendar-grid-head"><span/><div className="calendar-day-heads" style={{gridTemplateColumns:`repeat(${shownDays.length},minmax(150px,1fr))`}}>{shownDays.map(day=><div key={day.key}><strong>{day.key}</strong><span>{day.date.getDate()}</span></div>)}</div></div><div className="calendar-grid-body"><div className="calendar-time-rail">{Array.from({length:12},(_,index)=>index+8).map(hour=><span key={hour}>{hour===12?'12 PM':hour<12?`${hour} AM`:`${hour-12} PM`}</span>)}</div><div className="calendar-day-tracks" style={{gridTemplateColumns:`repeat(${shownDays.length},minmax(150px,1fr))`}}>{shownDays.map(day=>{const dayEvents=visibleEvents.filter(event=>event.day===day.key);return <div className="calendar-day-track" key={day.key}>{dayEvents.map(event=><button key={event.id} className={`calendar-grid-event ${event.tone}`} style={eventStyle(event,dayEvents)} onClick={()=>openEvent(event)}><small>{event.tone==='proposed'?'Proposed':event.type==='Class'?'Enrolled':'Personal'} · {event.time}–{event.endTime}</small><strong>{event.title}</strong><span>{event.meta}</span></button>)}</div>})}</div></div></div>}
    </article>
    {dialogOpen&&<div className="modal-backdrop" onMouseDown={()=>setDialogOpen(false)}><form className="event-dialog calendar-event-dialog" onMouseDown={event=>event.stopPropagation()} onSubmit={event=>{event.preventDefault();saveEvent()}}><div className="event-dialog-head"><span className="eyebrow">{editingId?'EVENT DETAILS':'NEW COMMITMENT'}</span><h2>{editingId?isReadOnly?(selectedEvent?.tone==='proposed'?'Proposed section details':'Class details'):'Edit event':'Add to calendar'}</h2><p>{isReadOnly?(selectedEvent?.tone==='proposed'?'This proposed section is in your Create Schedule draft and is edited there.':'Classes come from the saved schedule picked above and are read-only. Change them in Create Schedule.'):'Changes here also inform schedule generation and Flow’s advice.'}</p></div><label>Event name<input autoFocus required disabled={isReadOnly} value={draft.title} onChange={event=>setDraft({...draft,title:event.target.value})}/></label><div className="event-dialog-row"><label>Category<select disabled={isReadOnly} value={draft.category} onChange={event=>setDraft({...draft,category:event.target.value as EventCategory})}>{categories.filter(category=>category!=='Academic').map(category=><option key={category}>{category}</option>)}</select></label><label>Day<select disabled={isReadOnly} value={draft.day} onChange={event=>setDraft({...draft,day:event.target.value as CalendarEvent['day']})}>{dayKeys.map(day=><option key={day}>{day}</option>)}</select></label></div><div className="event-dialog-row"><label>Starts<input disabled={isReadOnly} type="time" min="08:00" max="19:59" required value={draft.start} onChange={event=>setDraft({...draft,start:event.target.value})}/></label><label>Ends<input disabled={isReadOnly} type="time" required value={draft.end} min={draft.start} max="20:00" onChange={event=>setDraft({...draft,end:event.target.value})}/></label></div><label>Location or details<input disabled={isReadOnly} value={draft.meta} onChange={event=>setDraft({...draft,meta:event.target.value})}/></label><div className="event-dialog-row"><label>Repeats<select disabled={isReadOnly} value={draft.recurrence} onChange={event=>setDraft({...draft,recurrence:event.target.value as CalendarEvent['recurrence']})}><option>None</option><option>Weekly</option></select></label><label>Priority<select disabled={isReadOnly} value={draft.priority} onChange={event=>setDraft({...draft,priority:event.target.value as CalendarEvent['priority']})}><option>Low</option><option>Normal</option><option>High</option></select></label></div>{!isReadOnly&&<label className="calendar-checkbox"><input type="checkbox" checked={draft.fixed} onChange={event=>setDraft({...draft,fixed:event.target.checked})}/><span><strong>Fixed commitment</strong><small>Block schedule generation from placing courses here.</small></span></label>}{editingId&&!isReadOnly&&selectedEvent?.recurrence==='Weekly'&&<div className="recurrence-scope"><span>Apply changes to</span><div><button type="button" className={applyScope==='occurrence'?'active':''} onClick={()=>setApplyScope('occurrence')}>This occurrence</button><button type="button" className={applyScope==='series'?'active':''} onClick={()=>setApplyScope('series')}>Entire series</button></div><small>{applyScope==='occurrence'?'Only this visible occurrence will change.':'Updates apply to the recurring weekly commitment.'}</small></div>}{!isReadOnly&&draft.end<=draft.start&&<p className="calendar-form-warning">End time must be after start time.</p>}{!isReadOnly&&draftConflict&&<p className="calendar-form-warning">This overlaps another event. You can save it, but the schedule builder will flag the conflict.</p>}<div className="event-dialog-actions">{editingId&&!isReadOnly&&<button type="button" className="remove-event-button" disabled={busy} onClick={()=>removeEvent(editingId)}>{selectedEvent?.recurrence==='Weekly'?(applyScope==='occurrence'?'Delete occurrence':'Delete series'):'Remove event'}</button>}<button type="button" className="ghost" onClick={()=>setDialogOpen(false)}>{isReadOnly?'Close':'Cancel'}</button>{!isReadOnly&&<button className="primary" type="submit" disabled={busy}>{busy?'Saving…':editingId?'Save changes':'Add event'}</button>}</div></form></div>}
  </div>
}
