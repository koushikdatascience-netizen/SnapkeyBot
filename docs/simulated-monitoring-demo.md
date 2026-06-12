# Simulated Monitoring Demo

The monitoring workspace is a frontend-only demonstration for client presentations. It is always labeled
`SIMULATED DEMO` and does not connect to real cameras, employee screens, face recognition, or activity detection.

Supported voice requests include:

- `Show all cameras`
- `Open camera 1`
- `Show the stock room camera`
- `Show all workers`
- `Who is idle?`
- `Open the employee screen share`

The demo displays:

- Three selectable animated camera tiles
- OpenCV-style detection boxes and confidence labels
- Simulated worker names, activities, and timings
- A simulated POS screen-share preview
- Responsive desktop and mobile layouts

For a future real deployment, camera access, employee monitoring, identity matching, retention, and alerts require
customer authorization, employee notice/consent, role-based access, audit logs, and applicable privacy-law review.
