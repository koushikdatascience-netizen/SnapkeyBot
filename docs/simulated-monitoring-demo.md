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

## Add Real Demo Videos

Upload short, muted-safe MP4/WebM files to a public HTTPS object store such as Cloudflare R2, AWS S3, Supabase
Storage, or Vercel Blob. The URL must return the video file directly and permit browser playback. Google Drive share
pages and YouTube watch URLs will not work as `<video>` sources.

Set Railway variables:

```env
MONITORING_CAMERA_URLS=https://cdn.example.com/cam1.mp4,https://cdn.example.com/cam2.mp4,https://cdn.example.com/cam3.mp4
MONITORING_SCREEN_URL=https://cdn.example.com/pos-screen.mp4
```

Redeploy Railway. Snapkey loops the videos muted and places the simulated detection overlays above them. When a URL
is missing or fails, the animated fallback remains visible instead of a blank screen.

For a future real deployment, camera access, employee monitoring, identity matching, retention, and alerts require
customer authorization, employee notice/consent, role-based access, audit logs, and applicable privacy-law review.
