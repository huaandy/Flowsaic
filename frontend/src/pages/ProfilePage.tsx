import type { ApiProgress, ApiStudent } from '../api/types'
import { Icon } from '../components/Icon'
import type { Page, StudentProfile } from '../types'

export type ConnectState = { status: 'idle' | 'running' | 'done' | 'failed'; message: string }
const PHOTO_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp']
const MAX_PHOTO_BYTES = 1_000_000

// Identity comes from GET /me; the photo is saved with PUT /me/settings. Students without a demo
// plan (users 4 and 5) get Connect mySAU: POST /me/connect-mysau, then GET /data/refresh/{id}.
export function ProfilePage({ me, profile, progress, onPhotoSave, onPhotoError, go, connect, onConnect }: { me: ApiStudent; profile: StudentProfile; progress: ApiProgress | null; onPhotoSave: (photo: string | null) => void; onPhotoError: (message: string) => void; go: (page: Page) => void; connect: ConnectState; onConnect: () => void }) {
  const uploadPhoto = (file?: File) => {
    if (!file) return
    if (!PHOTO_TYPES.includes(file.type)) return onPhotoError('Choose a PNG, JPEG, GIF or WebP image.')
    if (file.size > MAX_PHOTO_BYTES) return onPhotoError('That photo is over 1 MB. Choose a smaller one.')
    const reader = new FileReader()
    reader.onload = () => onPhotoSave(String(reader.result))
    reader.readAsDataURL(file)
  }
  const earned = progress?.hours.earned ?? me.total_hours_earned ?? 0
  const required = progress?.hours.required ?? me.total_hours_needed
  const percent = required ? Math.min(100, Math.round(earned / required * 100)) : null
  const canConnect = me.degree_plan === null
  return <div className="account-page profile-page">
    <article className="card profile-hero-card"><div className="profile-photo">{profile.photo ? <img src={profile.photo} alt={profile.name} /> : profile.name.split(' ').map(part => part[0]).join('').slice(0, 2)}</div><div><span className="eyebrow">STUDENT PROFILE</span><h2>{profile.name}</h2><p>{profile.degree}{profile.major !== profile.degree ? ` · ${profile.major}` : ''}</p><span className="profile-standing"><Icon name="check" size={14} />{profile.standing}</span></div><div className="profile-hero-actions"><label className="ghost photo-upload">Update photo<input type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={event => { uploadPhoto(event.target.files?.[0]); event.target.value = '' }} /></label>{profile.photo && <button className="ghost" onClick={() => onPhotoSave(null)}>Remove photo</button>}</div></article>
    <div className="official-info-note"><Icon name="settings" size={16} /><span>Academic and identity information is managed by Southern Arkansas University. Contact your university to request corrections.</span></div>
    <div className="account-grid">
      <article className="card account-section"><div className="account-section-head"><span className="feature-icon blue"><Icon name="user" /></span><div><h2>University-managed information</h2><p>Read-only information from the student information system.</p></div></div><div className="profile-fields"><label>Official name<strong>{profile.name}</strong><small>University-managed identity</small></label><label>Student email<strong>{profile.email}</strong><small>University-issued account</small></label><label>University<strong>{profile.university}</strong><small>Official institution record</small></label><label>Major<strong>{profile.major}</strong><small>{me.connected_mysau ? 'From your mySAU degree audit' : 'Official academic record'}</small></label><label>Degree program<strong>{profile.degree}</strong><small>{me.catalog_year ? `${me.catalog_year} catalog` : 'Official academic record'}</small></label><label>Expected graduation<strong>{profile.graduation}</strong><small>Estimate at 15 credits a term</small></label></div></article>
      <article className="card academic-summary-card"><div className="account-section-head"><span className="feature-icon green"><Icon name="chart" /></span><div><h2>Academic summary</h2><p>Your current official standing.</p></div></div><div className="profile-stat-row"><span><b>{earned}</b> of {required ?? '—'} credits</span><span><b>{percent === null ? '—' : `${percent}%`}</b> complete</span></div><div className="profile-academic-detail"><span>Classification<strong>{profile.standing}</strong></span><span>Expected graduation<strong>{profile.graduation}</strong></span></div><button className="text-btn" onClick={() => go('Degree Progress')}>View degree progress <Icon name="arrow" size={14} /></button><button className="text-btn" onClick={() => go('Semester Planner')}>Open semester roadmap <Icon name="arrow" size={14} /></button></article>
      {canConnect && <article className="card account-section"><div className="account-section-head"><span className="feature-icon purple"><Icon name="layers" /></span><div><h2>{me.connected_mysau ? 'mySAU' : 'Get started'}</h2><p>{me.connected_mysau ? `Last connected ${me.audit_refreshed_at ? new Date(me.audit_refreshed_at).toLocaleString() : ''}` : 'Load your degree audit and this term’s course schedule from mySAU.'}</p></div></div><p className="settings-copy">A browser window opens on this laptop. Sign in to mySAU yourself (Microsoft and Duo); Flowsaic never sees or stores your password. Your name, ID number, address and GPA are not kept.</p><button className="primary" disabled={connect.status === 'running'} onClick={onConnect}>{connect.status === 'running' ? 'Waiting for mySAU…' : me.connected_mysau ? 'Refresh from mySAU' : 'Connect mySAU'}</button>{connect.message && <p className="settings-copy">{connect.message}</p>}</article>}
    </div>
  </div>
}
