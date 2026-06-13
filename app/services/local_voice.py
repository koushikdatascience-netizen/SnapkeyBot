import asyncio
import base64
import csv
import io
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.retail_reports import report_tenant_for, run_retail_report

_whisper_model: Any = None
_whisper_lock = asyncio.Lock()


def _faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def _tts_provider_ready() -> bool:
    settings = get_settings()
    if settings.local_tts_provider == "piper":
        executable = settings.local_tts_piper_executable or shutil.which("piper")
        return bool(executable and settings.local_tts_piper_model)
    if settings.local_tts_provider == "sapi":
        return platform.system() == "Windows" and bool(shutil.which("powershell"))
    return False


def local_voice_ready() -> bool:
    settings = get_settings()
    return bool(settings.local_voice_enabled and _faster_whisper_available() and _tts_provider_ready())


def local_voice_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "enabled": settings.local_voice_enabled,
        "ready": local_voice_ready(),
        "stt": {
            "ready": _faster_whisper_available(),
            "model": settings.local_stt_model,
            "device": settings.local_stt_device,
            "compute_type": settings.local_stt_compute_type,
            "language": settings.local_stt_language,
        },
        "tts": {
            "ready": _tts_provider_ready(),
            "provider": settings.local_tts_provider,
            "voice": settings.local_tts_sapi_voice,
        },
        "features": [
            "local_audio",
            "barge_in",
            "approved_retail_reports",
            "monitoring_workspace",
            "madhushala_desktop_control",
        ],
        "madhushala_control": bool(settings.madhushala_exe_path or settings.madhushala_process_name),
    }


async def _model() -> Any:
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    async with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel

            settings = get_settings()
            _whisper_model = await asyncio.to_thread(
                WhisperModel,
                settings.local_stt_model,
                device=settings.local_stt_device,
                compute_type=settings.local_stt_compute_type,
            )
    return _whisper_model


async def transcribe_wav(audio: bytes) -> str:
    if not _faster_whisper_available():
        raise RuntimeError("Install the local-voice dependencies to enable transcription")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
        file.write(audio)
        path = file.name
    try:
        model = await _model()
        settings = get_settings()

        def run() -> str:
            segments, _ = model.transcribe(
                path,
                language=settings.local_stt_language or None,
                vad_filter=True,
                beam_size=1,
                best_of=1,
                condition_on_previous_text=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()

        return await asyncio.to_thread(run)
    finally:
        Path(path).unlink(missing_ok=True)


def _report_intent(text: str) -> dict[str, Any] | None:
    value = text.lower()
    report_words = (
        "report", "sales", "sale", "stock", "inventory", "product", "item",
        "payment", "cash", "card", "upi", "purchase", "customer", "bill",
        "बिक्री", "स्टॉक", "रिपोर्ट", "खरीद", "पेमेंट",
    )
    if not any(word in value for word in report_words):
        return None
    report_name = "sales_summary"
    if any(word in value for word in ("low stock", "reorder", "कम स्टॉक", "inventory")):
        report_name = "low_stock"
    elif any(word in value for word in ("top product", "top item", "best selling", "सबसे ज्यादा")):
        report_name = "top_products"
    elif any(word in value for word in ("payment", "cash", "card", "upi", "पेमेंट")):
        report_name = "payment_mix"
    elif any(word in value for word in ("hourly", "peak hour", "busy hour")):
        report_name = "hourly_sales"
    elif any(word in value for word in ("average bill", "avg bill")):
        report_name = "average_bill"
    elif any(word in value for word in ("purchase", "खरीद")):
        report_name = "purchase_trend"
    elif any(word in value for word in ("customer", "visits")):
        report_name = "customer_visits"
    elif "category" in value and "stock" in value:
        report_name = "stock_by_category"
    elif "category" in value:
        report_name = "category_sales"
    days = 1 if any(word in value for word in ("today", "आज")) else 7
    if any(word in value for word in ("month", "महीना")):
        days = 30
    elif any(word in value for word in ("yesterday", "कल")):
        days = 2
    chart = "donut" if any(word in value for word in ("pie", "donut")) else ""
    return {"report_name": report_name, "days": days, "limit": 20, "chart": chart}


def _monitoring_workspace(text: str) -> dict[str, Any] | None:
    value = text.lower()
    if not any(word in value for word in ("camera", "cam ", "cctv", "monitoring", "कैमरा")):
        return None
    camera = 0
    if any(word in value for word in ("camera 1", "cam 1", "कैमरा एक")):
        camera = 1
    elif any(word in value for word in ("camera 2", "cam 2", "कैमरा दो")):
        camera = 2
    return {
        "type": "monitoring",
        "title": f"Camera {camera} live view" if camera else "Operations monitoring",
        "summary": "The configured local monitoring workspace is open.",
        "selected_camera": camera,
    }


def _summary_for_report(result: dict[str, Any]) -> str:
    if result.get("voice_summary"):
        return f"{result['title']} is ready. {result['voice_summary']}"
    title = result["title"]
    rows = result.get("rows", [])
    if not rows:
        return f"{title} is open, but no matching data was found."
    first = rows[0]
    return f"{title} is ready. The leading result is {first.get('label')} at {first.get('value')}."


def _desktop_apps() -> dict[str, dict[str, str]]:
    settings = get_settings()
    apps = {
        "madhushala": {
            "exe": settings.madhushala_exe_path,
            "process": settings.madhushala_process_name,
        },
        "notepad": {"exe": r"C:\Windows\System32\notepad.exe", "process": "notepad"},
        "calculator": {"exe": "calc.exe", "process": "CalculatorApp"},
    }
    if settings.desktop_apps_json:
        try:
            configured = json.loads(settings.desktop_apps_json)
            if isinstance(configured, dict):
                apps.update(configured)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DESKTOP_APPS_JSON is invalid") from exc
    return apps


def _desktop_action(text: str) -> tuple[str, str]:
    value = text.lower()
    aliases = {"madhusala": "madhushala", "erp": "madhushala", "pos": "madhushala"}
    app_name = next((name for name in _desktop_apps() if name in value), "")
    if not app_name:
        app_name = next((target for alias, target in aliases.items() if alias in value), "")
    if not app_name:
        return "", ""
    if any(word in value for word in ("close", "exit")):
        return app_name, "close"
    if any(word in value for word in ("minimize", "hide")):
        return app_name, "minimize"
    if any(word in value for word in ("focus", "bring", "show", "restore")):
        return app_name, "focus"
    if any(word in value for word in ("open", "start", "launch")):
        return app_name, "open"
    return "", ""


def _validated_process_name(name: str) -> str:
    name = name.strip()
    if not name or not re.fullmatch(r"[\w .-]{1,100}", name):
        raise RuntimeError("MADHUSHALA_PROCESS_NAME is invalid")
    return name.removesuffix(".exe")


async def control_desktop_app(app_name: str, action: str, *, confirmed: bool = False) -> dict[str, Any]:
    if platform.system() != "Windows":
        raise RuntimeError("Desktop application control is available only on Windows")
    app = _desktop_apps().get(app_name)
    if not app:
        raise RuntimeError(f"{app_name} is not in the desktop application allowlist")
    if action == "close" and not confirmed:
        return {"status": "confirmation_required", "action": action}
    if action == "open":
        executable = str(app.get("exe", "")).strip()
        path = Path(executable).expanduser()
        if path.is_file() and path.suffix.lower() == ".exe":
            await asyncio.to_thread(os.startfile, str(path))
        elif executable and re.fullmatch(r"[\w.-]{1,100}\.exe", executable):
            await asyncio.create_subprocess_exec(executable)
        else:
            raise RuntimeError(f"Set a valid executable path for {app_name}")
        return {"status": "opened", "action": action, "app": app_name}

    process_name = _validated_process_name(str(app.get("process", "")))
    scripts = {
        "focus": (
            "$p=Get-Process -Name $env:SNAPKEY_TARGET_PROCESS -ErrorAction Stop | Select-Object -First 1; "
            "$w=New-Object -ComObject WScript.Shell; $null=$w.AppActivate($p.Id)"
        ),
        "minimize": (
            "Add-Type -Name Win -Namespace Native -MemberDefinition "
            "'[DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd,int nCmdShow);'; "
            "$p=Get-Process -Name $env:SNAPKEY_TARGET_PROCESS -ErrorAction Stop | Select-Object -First 1; "
            "[Native.Win]::ShowWindow($p.MainWindowHandle,6) | Out-Null"
        ),
        "close": (
            "$p=Get-Process -Name $env:SNAPKEY_TARGET_PROCESS -ErrorAction Stop | Select-Object -First 1; "
            "if(-not $p.CloseMainWindow()){throw 'Madhushala did not accept a graceful close request'}"
        ),
    }
    if action not in scripts:
        raise ValueError("Unsupported Madhushala action")
    environment = os.environ.copy()
    environment["SNAPKEY_TARGET_PROCESS"] = process_name
    completed = await asyncio.to_thread(
        subprocess.run,
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", scripts[action]],
        capture_output=True,
        env=environment,
        timeout=15,
        check=False,
    )
    if completed.returncode:
        detail = completed.stderr.decode(errors="ignore").strip()
        raise RuntimeError(detail[:300] or f"{app_name} is not currently running")
    return {"status": f"{action}ed", "action": action, "app": app_name}


async def control_madhushala(action: str, *, confirmed: bool = False) -> dict[str, Any]:
    return await control_desktop_app("madhushala", action, confirmed=confirmed)


def _meetings_workspace() -> dict[str, Any]:
    meetings = ["10:30 AM - Supplier review", "6:30 PM - Meeting at Prayag"]
    if get_settings().local_demo_meetings_json:
        try:
            rows = json.loads(get_settings().local_demo_meetings_json)
            meetings = [f"{row.get('time', '')} - {row.get('title', 'Meeting')}" for row in rows][:10]
        except (json.JSONDecodeError, AttributeError) as exc:
            raise RuntimeError("LOCAL_DEMO_MEETINGS_JSON is invalid") from exc
    return {
        "type": "calendar",
        "title": "Today's meetings",
        "summary": f"{len(meetings)} meetings scheduled today.",
        "today_events": meetings,
        "events": meetings,
    }


def preview_purchase_csv(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("The purchase CSV has no rows")
    normalized = []
    total = 0.0
    for row in rows[:100]:
        name = row.get("item") or row.get("item_name") or row.get("product") or "Unmatched item"
        quantity = float(row.get("quantity") or row.get("qty") or 0)
        rate = float(row.get("rate") or row.get("price") or row.get("purchase_rate") or 0)
        amount = round(quantity * rate, 2)
        total += amount
        normalized.append({"label": name, "value": amount, "quantity": quantity, "rate": rate})
    return {
        "reply": f"Purchase preview is ready with {len(normalized)} lines and a total of {round(total, 2)}.",
        "workspace": {
            "type": "report",
            "title": "Purchase import preview",
            "summary": "Preview only. Nothing has been written to Madhushala.",
            "chart": "table",
            "rows": normalized,
            "total": round(total, 2),
        },
    }


def preview_purchase_pdf(payload: bytes) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Install pypdf to enable PDF purchase previews") from exc
    reader = PdfReader(io.BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError("No readable text was found in the PDF invoice")
    candidates = []
    for line in text.splitlines():
        cleaned = " ".join(line.split())
        if len(cleaned) < 4 or not re.search(r"\d", cleaned):
            continue
        numbers = re.findall(r"\d+(?:\.\d+)?", cleaned)
        amount = float(numbers[-1]) if numbers else 0
        candidates.append({"label": cleaned[:120], "value": amount})
        if len(candidates) >= 40:
            break
    if not candidates:
        candidates = [{"label": text[:120], "value": 0}]
    return {
        "reply": (
            f"PDF invoice preview is ready with {len(candidates)} candidate lines. "
            "Please verify item matches, quantities, rates, and tax before entry."
        ),
        "workspace": {
            "type": "report",
            "title": "PDF purchase invoice preview",
            "summary": "AI-assisted extraction preview only. Nothing has been written to Madhushala.",
            "chart": "table",
            "rows": candidates,
            "total": round(sum(float(row["value"]) for row in candidates), 2),
        },
    }


def preview_purchase_document(filename: str, payload: bytes) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return preview_purchase_csv(payload)
    if suffix == ".pdf":
        return preview_purchase_pdf(payload)
    raise ValueError("Use a PDF or CSV purchase invoice")


async def handle_local_command(text: str, email: str) -> dict[str, Any]:
    value = text.lower()
    if any(word in value for word in ("meeting", "calendar", "schedule", "appointment")):
        workspace = _meetings_workspace()
        return {"reply": workspace["summary"], "workspace": workspace}
    if any(word in value for word in ("purchase import", "import invoice", "upload invoice")):
        return {
            "reply": "Purchase import preview is ready. Upload a CSV invoice to validate it before ERP entry.",
            "workspace": {
                "type": "progress",
                "title": "Purchase import",
                "summary": "Preview and validation only. No ERP data will be changed.",
                "steps": ["Upload invoice CSV", "Validate items and totals", "Review before entry"],
            },
        }

    app_name, desktop_action = _desktop_action(text)
    if desktop_action:
        if desktop_action == "close":
            return {
                "reply": f"{app_name.title()} can be closed, but I need your confirmation first.",
                "workspace": {
                    "type": "brief",
                    "title": f"Confirm closing {app_name.title()}",
                    "summary": "Save any active work before closing.",
                },
                "desktop_action": {"app": app_name, "action": "close", "requires_confirmation": True},
            }
        result = await control_desktop_app(app_name, desktop_action)
        return {
            "reply": f"{app_name.title()} has been {result['status']}.",
            "workspace": None,
            "desktop_action": {"app": app_name, "action": desktop_action, "completed": True},
        }

    monitoring = _monitoring_workspace(text)
    if monitoring:
        return {"reply": "Sure. I have opened the monitoring workspace.", "workspace": monitoring}

    intent = _report_intent(text)
    if intent:
        result = await run_retail_report(
            intent["report_name"],
            tenant_id=report_tenant_for(email),
            days=int(intent["days"]),
            limit=int(intent["limit"]),
            chart=str(intent["chart"]),
        )
        workspace = {
            "type": "report",
            "title": result["title"],
            "summary": (
                f"{result['period']['start']} to {result['period']['end']}. "
                f"Showing up to {result['limits']['points']} points."
            ),
            "chart": result["chart"],
            "rows": result["rows"],
            "total": result["total"],
            "insights": result.get("insights", []),
            "source": result.get("source", ""),
        }
        return {"reply": _summary_for_report(result), "workspace": workspace}

    if any(word in text.lower() for word in ("hello", "hi", "hey", "नमस्ते")):
        return {
            "reply": "Hello. I am Snapkey, your local business assistant. How may I help you?",
            "workspace": None,
        }
    return {
        "reply": (
            "I can open sales, stock, purchase, payment, customer, and camera workspaces locally. "
            "Please tell me which one you need."
        ),
        "workspace": {"type": "brief", "title": "Local assistant ready", "summary": text},
    }


async def synthesize_wav(text: str) -> bytes:
    settings = get_settings()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
        output_path = file.name
    Path(output_path).unlink(missing_ok=True)
    try:
        if settings.local_tts_provider == "piper":
            executable = settings.local_tts_piper_executable or shutil.which("piper")
            if not executable or not settings.local_tts_piper_model:
                raise RuntimeError("Piper executable and model are required")
            process = await asyncio.create_subprocess_exec(
                executable,
                "--model",
                settings.local_tts_piper_model,
                "--output_file",
                output_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate(text.encode("utf-8"))
            if process.returncode:
                raise RuntimeError(stderr.decode("utf-8", errors="ignore")[:300] or "Piper failed")
        elif settings.local_tts_provider == "sapi" and platform.system() == "Windows":
            script = (
                "Add-Type -AssemblyName System.Speech; "
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "if($env:SNAPKEY_SAPI_VOICE){$s.SelectVoice($env:SNAPKEY_SAPI_VOICE)}; "
                "$s.SetOutputToWaveFile($env:SNAPKEY_TTS_OUTPUT); "
                "$s.Speak($env:SNAPKEY_TTS_TEXT); $s.Dispose()"
            )
            environment = os.environ.copy()
            environment["SNAPKEY_TTS_TEXT"] = text
            environment["SNAPKEY_TTS_OUTPUT"] = output_path
            environment["SNAPKEY_SAPI_VOICE"] = settings.local_tts_sapi_voice
            completed = await asyncio.to_thread(
                subprocess.run,
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                env=environment,
                timeout=30,
                check=False,
            )
            if completed.returncode:
                raise RuntimeError(completed.stderr.decode(errors="ignore")[:300] or "Windows speech failed")
        else:
            raise RuntimeError("No local TTS provider is configured")
        return Path(output_path).read_bytes()
    finally:
        Path(output_path).unlink(missing_ok=True)


async def local_turn(audio: bytes, email: str) -> dict[str, Any]:
    transcript = await transcribe_wav(audio)
    if not transcript:
        return {"transcript": "", "reply": "", "workspace": None, "audio_base64": ""}
    result = await handle_local_command(transcript, email)
    audio_output = await synthesize_wav(result["reply"])
    return {
        "transcript": transcript,
        **result,
        "audio_base64": base64.b64encode(audio_output).decode("ascii"),
        "audio_content_type": "audio/wav",
    }
