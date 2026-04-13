"""Phase 1 demo wrapper around the pipeline — NOT the Phase 2 web app.

A single-page FastAPI app that:
  - GET /              serves the HTML page (inlined, no bundler)
  - POST /generate     accepts a PDF upload, kicks off pipeline in bg
  - GET /jobs/{id}/events   SSE: streams progress lines
  - GET /jobs/{id}/download DOCX when ready
  - GET /memorial/latest    serve outputs/memorial_v1.docx if it exists

Phase 2 will have auth, DB, Supabase, Razorpay, proper React frontend,
etc. This is a demo so Tanish can SEE the pipeline running. Deliberately
scoped small.
"""

from __future__ import annotations

import asyncio
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

from lexai.pipeline.orchestrator import run_pipeline
from lexai.pipeline.validate import HallucinationError

load_dotenv()

ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = ROOT / "outputs"
UPLOADS_DIR = ROOT / "outputs" / "uploads"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="LexAI Phase 1 Demo")


@dataclass
class Job:
    id: str
    pdf_path: Path
    out_path: Path
    title: str
    tribunal: str
    case_number: str
    events: asyncio.Queue = field(default_factory=asyncio.Queue)
    done: bool = False
    failed: bool = False
    error: str | None = None
    memorial_ready: bool = False
    issues_found: int = 0
    citations_used: int = 0
    hallucinations: int = 0


JOBS: dict[str, Job] = {}


async def _run_pipeline_async(job: Job) -> None:
    loop = asyncio.get_running_loop()

    def emit(line: str) -> None:
        # called from worker thread, push into the queue safely
        asyncio.run_coroutine_threadsafe(job.events.put(line), loop)

    def worker() -> None:
        try:
            result = run_pipeline(
                job.pdf_path,
                job.out_path,
                moot_title=job.title,
                tribunal=job.tribunal,
                case_number=job.case_number,
                strict_citations=False,
                progress=emit,
            )
            job.issues_found = len(result.issues)
            job.citations_used = result.total_citations_used
            job.hallucinations = result.total_hallucinations
            job.memorial_ready = True
            emit(
                f"__DONE__ issues={job.issues_found} citations={job.citations_used} "
                f"hallucinations={job.hallucinations}"
            )
        except HallucinationError as e:
            job.error = f"Hallucinated citation: {e}"
            job.failed = True
            emit(f"__ERROR__ {job.error}")
        except Exception as e:  # noqa: BLE001
            job.error = f"{type(e).__name__}: {e}"
            job.failed = True
            emit(f"__ERROR__ {job.error}\n{traceback.format_exc()[-500:]}")
        finally:
            job.done = True
            emit("__END__")

    await loop.run_in_executor(None, worker)


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/health")
async def health() -> dict:
    latest = OUTPUTS_DIR / "memorial_v1.docx"
    return {
        "ok": True,
        "latest_memorial": latest.exists(),
        "latest_size": latest.stat().st_size if latest.exists() else 0,
    }


@app.get("/memorial/latest")
async def latest_memorial() -> FileResponse:
    path = OUTPUTS_DIR / "memorial_v1.docx"
    if not path.exists():
        raise HTTPException(404, "No memorial generated yet")
    return FileResponse(
        path,
        filename="memorial.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    pdf: UploadFile = File(...),
    title: str = "LexAI Generated Memorial",
    tribunal: str = "Competition Appellate Tribunal",
    case_number: str = "Appeal No. __ of ____",
) -> dict:
    if not pdf.filename or not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Expected a .pdf file")

    job_id = uuid.uuid4().hex[:12]
    pdf_path = UPLOADS_DIR / f"{job_id}.pdf"
    out_path = OUTPUTS_DIR / f"memorial_{job_id}.docx"

    content = await pdf.read()
    pdf_path.write_bytes(content)

    job = Job(
        id=job_id,
        pdf_path=pdf_path,
        out_path=out_path,
        title=title,
        tribunal=tribunal,
        case_number=case_number,
    )
    JOBS[job_id] = job
    background_tasks.add_task(_run_pipeline_async, job)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")

    async def stream():
        while True:
            try:
                line = await asyncio.wait_for(job.events.get(), timeout=60)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: waiting\n\n"
                continue
            yield f"data: {line}\n\n"
            if line == "__END__":
                break

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/jobs/{job_id}/download")
async def job_download(job_id: str) -> FileResponse:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")
    if not job.memorial_ready or not job.out_path.exists():
        raise HTTPException(425, "Memorial not ready")
    return FileResponse(
        job.out_path,
        filename=f"memorial_{job_id}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
