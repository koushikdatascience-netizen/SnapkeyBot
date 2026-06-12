# Production Live Agent

The primary customer entry point is:

`https://YOUR-DOMAIN/live`

The customer signs in once, starts the interruptible ElevenLabs conversation, and then uses voice or the
mobile quick actions. Workspaces open beside the live voice on desktop and as a full-screen switchable view
on mobile.

## Supported Live Capabilities

- Retail reports: sales, hourly sales, top products, category sales, low stock, stock by category, payment
  mix, average bill, purchase trend, and customer visits.
- Report controls: bounded date ranges and result limits, plus bar, line, donut, and table views.
- Google Calendar: read upcoming events and create events after confirmation.
- Gmail: search, read, draft, and send after confirmation.
- Cameras: configured HTTPS camera/video feeds and monitoring workspace.
- YouTube: search, embedded playback, play, pause, stop, next, previous, mute, and unmute.
- Browserbase: visible hosted browser with confirmed interactive actions.

## ElevenLabs Client Tools

Keep the existing `run_integration`, `show_workspace`, `request_confirmation`, `start_browser`, and
`control_browser` client tools. Add these client tools:

### `control_media`

Parameters:

- `action` string, required, enum: `play`, `pause`, `stop`, `next`, `previous`, `mute`, `unmute`

Use it whenever the user asks to control the visible YouTube player.

### `control_report`

Parameters:

- `chart` string, required, enum: `bar`, `line`, `donut`, `table`

Use it when the user asks to change the visible report visualization without rerunning the query.

## Reporting Safety

The agent cannot submit arbitrary SQL. It selects an approved report, date window, point limit, and chart
style. The backend enforces tenant assignment, query timeout, maximum days, and maximum chart points.
