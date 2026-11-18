"""mySAU (my.saumag.edu) connect: the student signs in themselves, then a script exports the
course schedule and reads the degree audit.

Privacy rules (prompt 2, non-negotiable):
- Never store, log or print a password, cookie, token or Playwright storage_state.
  A fresh browser context every run, closed at the end. No persistent profile.
- Tracing, video and screenshots stay off for mySAU pages.
- Never log page HTML or audit text.
- The audit PDF is read in memory only and never written to disk.
- From the audit keep only: major, catalog year, classification, course lines,
  requirement statuses and total hours. Holds become a yes/no only.
"""
