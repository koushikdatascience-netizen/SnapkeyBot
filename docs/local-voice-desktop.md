# Snapkey Local Voice Desktop

Snapkey can run as a separate Windows desktop assistant beside Madhushala Ultimate. It uses the existing local SQL Server reporting views and does not require ElevenLabs or another paid voice API.

## Runtime

```text
Microphone
-> browser-side voice activity detection
-> local WAV utterance
-> faster-whisper on the shop PC
-> approved Snapkey command router
-> local SQL Server report connector
-> interactive Snapkey workspace
-> Windows SAPI or Piper speech
```

The microphone remains active while Snapkey speaks. When the user starts talking, current audio playback stops immediately and the new utterance is captured. Browser echo cancellation and noise suppression are enabled.

## Install And Run

Use Python 3.12:

```powershell
Set-Location "D:\Snapkey Assistant"
.\scripts\setup_local_voice.ps1
Copy-Item .env.example .env
```

Set these values in `.env`:

```env
LOCAL_VOICE_ENABLED=true
LOCAL_STT_MODEL=small
LOCAL_STT_DEVICE=cpu
LOCAL_STT_COMPUTE_TYPE=int8
LOCAL_STT_LANGUAGE=hi
LOCAL_TTS_PROVIDER=sapi

REPORT_CONNECTOR_URL=http://127.0.0.1:8090
REPORT_CONNECTOR_SECRET=<same-local-secret>
REPORT_TENANT_ID=2

MADHUSHALA_EXE_PATH=C:\Program Files\Madhushala\Madhushala Ultimate.exe
MADHUSHALA_PROCESS_NAME=Madhushala Ultimate
```

Start the SQL Server connector:

```powershell
$env:MSSQL_CONNECTION_STRING="DRIVER={ODBC Driver 18 for SQL Server};SERVER=.\SQLEXPRESS;DATABASE=barmanager;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;"
$env:CONNECTOR_SECRET="<same-local-secret>"
.\scripts\run_sqlserver_connector.ps1
```

Start the desktop assistant:

```powershell
py -3.12 desktop\snapkey_desktop.py
```

The launcher starts FastAPI on `127.0.0.1:8010` and opens an Edge application window. Create or sign into the local Snapkey account, select **Talk live**, and allow microphone access.

## Better Local Voice With Piper

Windows SAPI is available immediately but voice quality depends on installed Windows voices. Piper provides predictable offline speech:

```env
LOCAL_TTS_PROVIDER=piper
LOCAL_TTS_PIPER_EXECUTABLE=C:\SnapkeyVoice\piper\piper.exe
LOCAL_TTS_PIPER_MODEL=C:\SnapkeyVoice\models\your-voice.onnx
```

Use a legally licensed Hindi or Indian-English Piper model. The model and executable remain on the shop computer.

## Performance Profiles

CPU-only retail PC:

```env
LOCAL_STT_MODEL=small
LOCAL_STT_DEVICE=cpu
LOCAL_STT_COMPUTE_TYPE=int8
```

Low-powered PC:

```env
LOCAL_STT_MODEL=base
LOCAL_STT_DEVICE=cpu
LOCAL_STT_COMPUTE_TYPE=int8
```

NVIDIA GPU:

```env
LOCAL_STT_MODEL=medium
LOCAL_STT_DEVICE=cuda
LOCAL_STT_COMPUTE_TYPE=float16
```

The first request is slower because Whisper loads into memory. Keep the desktop assistant running throughout the working day.

## Current Supported Local Commands

- Sales summary.
- Top products.
- Category sales.
- Low stock and inventory.
- Payment mix.
- Hourly sales.
- Average bill.
- Purchase trend.
- Customer visits.
- Stock by category.
- Camera/monitoring workspace.
- Open, focus, minimize, and gracefully close Madhushala.

The router intentionally selects approved reports and never accepts arbitrary SQL.

Closing Madhushala always requires visible confirmation. Snapkey sends a normal
window-close request and never force-kills the ERP process.

## Build The EXE

```powershell
.\scripts\build_desktop_exe.ps1
```

The output is created in `dist\SnapkeyAssistant`. Keep `.env`, the Piper files when used, and the local Whisper model cache available on the client PC.

The first packaged build must be tested on a clean Windows machine before distribution. Code-sign the final installer to avoid Windows reputation warnings.
