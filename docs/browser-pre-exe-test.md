# Browser Test Before Building The EXE

This is the recommended validation path before packaging Snapkey as a Windows executable.

## Start Services

Start the local SQL Server reporting connector:

```powershell
$env:MSSQL_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=.\SQLEXPRESS;DATABASE=barmanager;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
$env:CONNECTOR_SECRET="<same-secret-as-env>"
.\scripts\run_sqlserver_connector.ps1
```

Start the Snapkey web application:

```powershell
py -3.12 -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Open:

```text
http://127.0.0.1:8010/live
```

## Available Input Modes

- Type commands into the normal message box.
- Use ElevenLabs **Talk live** when configured.
- Use local voice when `LOCAL_VOICE_ENABLED=true` and local voice dependencies are installed.

All three modes use the same approved reporting and local-command services.

The ElevenLabs browser client also exposes an optional `run_local_command` client
tool with one required string parameter named `prompt`. Automatic transcript
handling works without adding this tool, but adding it lets the ElevenLabs agent
explicitly request purchase-import and allowed desktop-app actions.

## Commands To Test

### Real Database Reporting

```text
Show today's sales report
Show top selling products this month
Show low stock items
Show payment mix as a pie chart
Show purchase trend
Show customer visits
```

### Workspaces

```text
Show today's meetings
Show camera 1
Show all cameras
Open purchase import
Open Google and search for Madhushala software
Play a retail training video on YouTube
```

### Allowed Desktop Applications

```text
Open Madhushala
Bring Madhushala to front
Minimize Madhushala
Open Notepad
Open Calculator
```

Closing an application requires confirmation.

## Purchase Import Preview

Say or type:

```text
Open purchase import
```

Then choose:

- PDF invoice: Snapkey extracts candidate text lines for human review.
- CSV invoice: use columns `item,quantity,rate` for structured totals.

The preview never writes to Madhushala.

## Expected Limitations Before EXE Packaging

- Browserbase is required for the hosted live-browser workspace.
- Google OAuth is required for real Google Calendar; otherwise local configured meetings are displayed.
- PDF extraction is text-based. Scanned image-only PDFs require OCR in a later phase.
- Camera views use configured URLs or the clearly labelled simulated demo.
- Desktop application controls work only on the Windows PC running FastAPI.
