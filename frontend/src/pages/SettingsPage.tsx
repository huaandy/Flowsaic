import { useEffect, useState } from 'react'
import { Icon } from '../components/Icon'
import type { AppSettings, StudentProfile } from '../types'


// Saved with PUT /me/settings. Appearance and accessibility apply as soon as they're clicked
// (onPreview); Discard puts the saved settings back.
export function SettingsPage({settings,onSave,onNotify,profile,onPreview}:{settings:AppSettings;onSave:(settings:AppSettings)=>Promise<boolean>;onNotify:(message:string)=>void;profile:StudentProfile;onPreview:(settings:AppSettings)=>void}) {
  const [draft,setDraftState]=useState(settings)
  const [saving,setSaving]=useState(false)
  useEffect(()=>setDraftState(settings),[settings])
  const setDraft=(next:AppSettings)=>{setDraftState(next);onPreview(next)}
  const toggle=(key:keyof AppSettings)=>setDraft({...draft,[key]:!draft[key]})
  const sections=[{title:'Notifications',icon:'bell',tone:'orange',items:[['emailNotifications','Email notifications','Degree and scheduling updates by email'],['pushNotifications','Push notifications','Time-sensitive reminders in Flowsaic'],['advisorUpdates','Advisor updates','Approval status and advisor feedback'],['scheduleAlerts','Schedule alerts','Conflicts, seat changes, and deadlines']]},{title:'Accessibility',icon:'eye',tone:'teal',items:[['highContrast','Higher contrast','Increase borders and text contrast'],['largerText','Larger interface text','Increase core interface sizing'],['reduceMotion','Reduce motion','Minimize transitions and movement']]}] as const
  const save=async()=>{setSaving(true);await onSave(draft);setSaving(false)}
  return <div className="account-page settings-page">
    <div className="settings-grid">
      <article className="card settings-card"><div className="account-section-head"><span className="feature-icon blue"><Icon name="user"/></span><div><h2>Account</h2><p>Official identity and authentication.</p></div></div><div className="readonly-account-fields"><span><small>Official name</small><strong>{profile.name}</strong></span><span><small>Student email</small><strong>{profile.email}</strong></span><span><small>Institution</small><strong>{profile.university}</strong></span></div><p className="university-managed-caption">Identity information is read-only and managed by Southern Arkansas University.</p><label>Profile visibility<select value={draft.profileVisibility} onChange={event=>setDraft({...draft,profileVisibility:event.target.value as AppSettings['profileVisibility']})}><option>Private</option><option>Advisors only</option><option>University community</option></select></label><button className="ghost settings-action" onClick={()=>onNotify('Passwords aren’t used in the prototype (real accounts come in semester 2)')}>Change password</button></article>
      <article className="card settings-card"><div className="account-section-head"><span className="feature-icon purple"><Icon name="settings"/></span><div><h2>Appearance</h2><p>Light is the default. System follows your device.</p></div></div><div className="appearance-options">{(['Light','Dark','System'] as const).map(option=><button className={draft.appearance===option?'active':''} aria-pressed={draft.appearance===option} key={option} onClick={()=>setDraft({...draft,appearance:option})}><span className={`theme-preview ${option.toLowerCase()}`}/><strong>{option}</strong></button>)}</div></article>
      {sections.map(section=><article className="card settings-card settings-list-card" key={section.title}><div className="account-section-head"><span className={`feature-icon ${section.tone}`}><Icon name={section.icon}/></span><div><h2>{section.title}</h2><p>Choose what works best for you.</p></div></div>{section.items.map(([key,label,description])=><button className="setting-row" key={key} onClick={()=>toggle(key)}><span><strong>{label}</strong><small>{description}</small></span><i className={draft[key]?'active':''}/></button>)}</article>)}
      <article className="card settings-card"><div className="account-section-head"><span className="feature-icon green"><Icon name="settings"/></span><div><h2>Privacy</h2><p>How your academic context is used.</p></div></div><p className="settings-copy">Flow uses your degree audit, planned courses, and calendar commitments to provide guidance. Flowsaic does not mark planned courses as completed.</p><button className="ghost settings-action">Review data controls</button></article>
    </div>
    <div className="account-save-bar"><button className="ghost" onClick={()=>setDraft(settings)}>Discard changes</button><button className="primary" disabled={saving} onClick={save}>{saving?'Saving…':'Save settings'}</button></div>
  </div>
}
