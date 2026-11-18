import { useState } from 'react'
import { ApiError } from '../api/client'

// Prototype sign-in (POST /auth/login): usernames 1–5 or a demo email, and the password isn't
// checked. Real accounts and passwords are semester 2.
export function SignIn({ onSignIn, signedOutNote }: { onSignIn: (username: string, password: string) => Promise<void>; signedOutNote: boolean }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async () => {
    if (!username.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      await onSignIn(username.trim(), password)
    } catch (caught) {
      setError(caught instanceof ApiError && caught.code === 'invalid_credentials'
        ? 'That isn’t a Flowsaic account. Use 1–5 or a demo email.'
        : caught instanceof ApiError && caught.code === 'network_error' ? 'Can’t reach Flowsaic. Is the backend running?' : 'Sign-in failed. Try again.')
    } finally {
      setBusy(false)
    }
  }
  return <main className="signed-out-screen"><section className="card login-card"><span className="top-brand-symbol"><img src="/assets/flow-koi.png" alt="Flowsaic koi" /></span><span className="eyebrow">FLOWSAIC</span><h1>{signedOutNote ? 'Welcome back' : 'Sign in'}</h1><p>{signedOutNote ? 'You have been signed out. Sign in again to pick up where you left off.' : 'Plan your degree, build your schedule, and ask Flow for advice.'}</p>
    <form className="login-form" onSubmit={event => { event.preventDefault(); submit() }}>
      <label>Username or email<input autoFocus autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} placeholder="1–5, or name@demo.flowsaic.test" /></label>
      <label>Password<input type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Any password (prototype)" /></label>
      {error && <p className="login-error" role="alert">{error}</p>}
      <button className="primary" type="submit" disabled={busy || !username.trim()}>{busy ? 'Signing in…' : 'Sign in'}</button>
    </form>
    <small>Prototype accounts: 1 Alex · 2 Jordan · 3 Sam · 4 Returning student · 5 New student. Any password works.</small></section></main>
}
