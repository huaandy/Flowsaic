// Backend error codes -> what the toast says. Unknown codes get a general message.
import { ApiError } from './client'

const MESSAGES: Record<string, string> = {
  network_error: 'Can’t reach Flowsaic. Make sure the start.cmd window is still open (double-click start.cmd if not), wait 10 seconds and refresh.',
  server_error: 'Something went wrong on the server. Try again; if it keeps happening, close the start.cmd window and double-click start.cmd.',
  not_authenticated: 'Your session ended. Please sign in again.',
  invalid_credentials: 'That username or email isn’t a Flowsaic account. Try 1–5.',
  invalid_request: 'Some of that information isn’t valid. Check it and try again.',
  schedule_has_conflicts: 'This schedule has conflicts. Fix them before saving.',
  schedule_not_found: 'That saved schedule no longer exists.',
  section_not_found: 'One of those sections isn’t offered anymore.',
  section_not_in_term: 'Those sections belong to another term.',
  term_not_found: 'That term isn’t available.',
  term_not_supported: 'Flow can only plan the current registration term.',
  course_not_found: 'That course isn’t in the catalog.',
  event_not_found: 'That event no longer exists.',
  too_many_events: 'Your calendar is full (60 events). Remove one first.',
  invalid_credit_range: 'Minimum credits can’t be more than maximum credits.',
  gemini_model_not_set: 'Flow isn’t set up on this laptop yet. Double-click setup.cmd (it adds the missing setting), then restart start.cmd.',
  ai_unavailable: 'Flow can’t be reached right now. Check your internet connection and send it again.',
  connect_already_running: 'A mySAU connect is already running. Finish signing in there.',
  student_not_found: 'Your account wasn’t found. Please sign in again.',
  pdf_unavailable: 'The schedule PDF can’t be made on this laptop yet. Double-click setup.cmd (it installs the browser Flowsaic uses), then restart start.cmd.',
}

export function friendlyError(error: unknown, fallback = 'Something went wrong. Try again.') {
  if (error instanceof ApiError) return MESSAGES[error.code] ?? fallback
  return fallback
}
