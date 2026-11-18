import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { ApiSearchResult } from '../api/types'
import { Icon } from './Icon'

const MATCH_TEXT = { code: 'Course code', title: 'Title', description: 'Description match' } as const

// GET /search: on Enter, or 400 ms after typing stops, from 2 characters. Code/title matches come
// first, then courses whose description is closest in meaning. Clicking opens the course.
export function HeaderSearch({ onOpen, onError }: { onOpen: (result: ApiSearchResult) => void; onError: (error: unknown) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ApiSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const requestId = useRef(0)
  const box = useRef<HTMLDivElement>(null)

  const run = (text: string) => {
    const value = text.trim()
    if (value.length < 2) { setResults([]); return }
    const id = ++requestId.current
    setLoading(true)
    setOpen(true)
    api.search(value).then(result => { if (id === requestId.current) setResults(result.results) })
      .catch(error => { if (id === requestId.current) onError(error) })
      .finally(() => { if (id === requestId.current) setLoading(false) })
  }
  useEffect(() => {
    const timer = setTimeout(() => run(query), 400)
    return () => clearTimeout(timer)
  }, [query])
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!box.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const choose = (result: ApiSearchResult) => { setOpen(false); setQuery(''); setResults([]); onOpen(result) }

  return <div className="search header-search" ref={box}><Icon name="search" /><input value={query} onChange={event => { setQuery(event.target.value); if (event.target.value.trim().length >= 2) setOpen(true) }} onFocus={() => results.length && setOpen(true)} onKeyDown={event => { if (event.key === 'Enter') run(query); if (event.key === 'Escape') setOpen(false) }} placeholder="Search courses, plans, and schedules" aria-label="Search courses" />
    {open && query.trim().length >= 2 && <div className="header-search-results card" role="listbox">
      {loading && !results.length && <span className="header-search-empty">Searching…</span>}
      {!loading && !results.length && <span className="header-search-empty">No courses match “{query.trim()}”</span>}
      {results.map(result => <button key={result.course_id} role="option" onMouseDown={event => event.preventDefault()} onClick={() => choose(result)}><span><strong>{result.code} · {result.title}</strong>{result.snippet && <small>{result.snippet}</small>}</span><em>{result.offered ? MATCH_TEXT[result.match_type] : 'Not offered this term'}</em></button>)}
    </div>}
  </div>
}
