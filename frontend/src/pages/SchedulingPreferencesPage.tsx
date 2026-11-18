import { useEffect, useState } from 'react'
import { MOCK_PREFERENCE_DEFAULTS, preferencesToUi } from '../api/adapters'
import { Icon } from '../components/Icon'
import type { SchedulingPreferences } from '../types'

/** The backend's defaults (GET /me/preferences for a student who never saved). */
export const DEFAULT_PREFERENCES:SchedulingPreferences=preferencesToUi({preferred_time:'none',preferred_days:'',min_credits:12,max_credits:18,delivery:['in_person','online'],flexibility:'balanced',updated_at:null},MOCK_PREFERENCE_DEFAULTS)


// Saved with PUT /me/preferences. Travel distance and minimum rating are mock fields: they stay
// on this device only (the backend doesn't store them).
export function SchedulingPreferencesPage({preferences,onSave}:{preferences:SchedulingPreferences;onSave:(preferences:SchedulingPreferences)=>Promise<boolean>}) {
  const defaults:SchedulingPreferences=DEFAULT_PREFERENCES
  const [draft,setDraft]=useState(preferences)
  const [saving,setSaving]=useState(false)
  useEffect(()=>setDraft(preferences),[preferences])
  const toggle=(key:'days'|'delivery',value:string)=>setDraft(current=>({...current,[key]:current[key].includes(value)?current[key].filter(item=>item!==value):[...current[key],value]}))
  const save=async()=>{setSaving(true);await onSave(draft);setSaving(false)}
  return <div className="account-page preferences-page">
    <article className="card preferences-intro"><span className="feature-icon purple"><Icon name="sliders"/></span><div><h2>Build schedules around your priorities</h2><p>Create Schedule and Flow use these preferences when comparing sections. Required courses and fixed commitments still take priority.</p></div><span className="pill">{draft.flexibility} flexibility</span></article>
    <div className="preference-grid">
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon teal"><Icon name="calendar"/></span><div><h2>Time and days</h2><p>When you prefer to attend class.</p></div></div><label>Preferred class time<select value={draft.time} onChange={event=>setDraft({...draft,time:event.target.value})}><option>Morning</option><option>Midday</option><option>Afternoon</option><option>Evening</option><option>No preference</option></select></label><span className="field-label">Preferred days</span><div className="choice-pills">{['Mon','Tue','Wed','Thu','Fri'].map(day=><button className={draft.days.includes(day)?'active':''} key={day} onClick={()=>toggle('days',day)}>{day}</button>)}</div></article>
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon blue"><Icon name="book"/></span><div><h2>Course load</h2><p>Set a comfortable semester range.</p></div></div><div className="range-fields"><label>Minimum credits<input type="number" min="1" max={draft.maxCredits} value={draft.minCredits} onChange={event=>setDraft({...draft,minCredits:Number(event.target.value)})}/></label><label>Maximum credits<input type="number" min={draft.minCredits} max="24" value={draft.maxCredits} onChange={event=>setDraft({...draft,maxCredits:Number(event.target.value)})}/></label></div><label>Preference flexibility<select value={draft.flexibility} onChange={event=>setDraft({...draft,flexibility:event.target.value as SchedulingPreferences['flexibility']})}><option>Flexible</option><option>Balanced</option><option>Strict</option></select></label></article>
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon orange"><Icon name="layers"/></span><div><h2>Format and location</h2><p>How and where classes meet.</p></div></div><span className="field-label">Delivery formats</span><div className="choice-pills wide-pills">{['Face-to-face','Online'].map(format=><button className={draft.delivery.includes(format)?'active':''} key={format} onClick={()=>toggle('delivery',format)}>{format}</button>)}</div><label>Maximum travel between classes <small>(this device only)</small><select value={draft.distance} onChange={event=>setDraft({...draft,distance:event.target.value})}><option>Under 10 minutes</option><option>Under 15 minutes</option><option>Under 25 minutes</option><option>No preference</option></select></label></article>
      <article className="card preference-card"><div className="account-section-head"><span className="feature-icon pink"><Icon name="user"/></span><div><h2>Instructor preference</h2><p>Use ratings as a scheduling signal.</p></div></div><span className="field-label">Minimum professor rating <small>(preview, this device only)</small></span><div className="rating-preference">{[1,2,3,4,5].map(value=><button className={draft.minRating>=value?'active':''} key={value} onClick={()=>setDraft({...draft,minRating:value})}>★</button>)}<strong>{draft.minRating}.0+</strong></div><small>Ratings never override prerequisites or required course sequencing.</small></article>
    </div>
    <div className="account-save-bar"><button className="ghost" onClick={()=>setDraft(defaults)}>Reset defaults</button><button className="primary" disabled={saving} onClick={save}>{saving?'Saving…':'Save preferences'}</button></div>
  </div>
}
