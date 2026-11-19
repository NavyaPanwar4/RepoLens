from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException, Query, Request, Header
from fastapi.responses import PlainTextResponse
from fastapi.responses import Response
from pydantic import BaseModel
import os
import shutil
import tempfile
import json
from uuid import uuid4

from app.services.ingestion import ingest_from_url, ingest_from_zip, walk_repo, cleanup
from app.services.parser import parse_all
from app.services.graph import build_graph, graph_summary, graph_to_json
from app.services.chunker import chunk_all
from app.services.vector_store import store_chunks
from app.services.bug_detector import detect_bugs, findings_summary
from app.services.repository_store import (
    delete_analysis,
    get_analysis,
    get_source,
    list_analyses,
    persist_analysis,
    persist_sources,
    count_analyses,
    create_share,
    revoke_share,
    get_shared_analysis,
)
from app.services.overview import build_overview
from app.services.llm import summarise_repository
from app.core.config import get_settings
from app.services.jobs import create_job, get_job, update_job
from app.services.git_history import get_history
from app.services.vector_store import delete_collection
from app.services.github_integration import (
    get_pull_request_diff,
    list_pull_requests,
    post_pull_request_review,
    verify_webhook_signature,
)
from app.services.scanner import run_real_scanners
from app.services.queue import enqueue
from app.services.comparison import build_comparison
from app.services.coverage import analyze_tests

router = APIRouter()

class RepoURL(BaseModel):
    url: str


class PullRequestReviewPayload(BaseModel):
    owner: str
    repository: str
    pull_number: int
    body: str
    event: str = "COMMENT"
    installation_id: str | None = None


class ComparisonPayload(BaseModel):
    repo_ids: list[str]


async def _save_upload(file: UploadFile) -> str:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload a .zip file.")
    settings = get_settings()
    settings = get_settings()
    upload_dir = settings.data_dir / "uploads" / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = str(upload_dir / "upload.zip")
    written = 0
    try:
        with open(target, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="ZIP is larger than the upload limit.")
                output.write(chunk)
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise
    return target


def _analyse_repo(
    repo_path: str,
    job_id: str | None = None,
    source_url: str | None = None,
) -> dict:
    if job_id:
        update_job(job_id, status="running", phase="Discovering supported files")
    files = walk_repo(repo_path)
    if job_id:
        update_job(job_id, status="running", phase=f"Parsing {len(files)} source files")
    parsed = parse_all(files)
    repo_id = uuid4().hex
    if job_id:
        update_job(job_id, status="running", phase="Saving source snapshot")
    persist_sources(repo_id, parsed, repo_path)
    if job_id:
        update_job(job_id, status="running", phase="Mapping dependencies")
    graph = build_graph(parsed)
    chunks = chunk_all(parsed)
    if job_id:
        update_job(job_id, status="running", phase=f"Indexing {len(chunks)} code chunks")
    chunks_stored = store_chunks(repo_id, chunks)
    if job_id:
        update_job(job_id, status="running", phase="Running code-quality checks")
    bugs = detect_bugs(parsed)
    if job_id:
        update_job(job_id, status="running", phase="Running security and dependency scanners")
    scanner_result = run_real_scanners(repo_path)
    scanner_findings = scanner_result.get("findings", [])
    if scanner_findings:
        seen = {
            (
                finding.get("file"),
                finding.get("line"),
                finding.get("rule"),
            )
            for finding in bugs
        }
        for finding in scanner_findings:
            key = (finding.get("file"), finding.get("line"), finding.get("rule"))
            if key not in seen:
                bugs.append(finding)
                seen.add(key)
    history = get_history(repo_path)
    testing = analyze_tests(repo_path, parsed)
    base_analysis = {
        "repo_id": repo_id,
        "source_url": source_url,
        "summary": graph_summary(graph),
        "graph": graph_to_json(graph),
        "chunks_stored": chunks_stored,
        "bugs": findings_summary(bugs),
        "git": history,
        "testing": testing,
    }
    overview = build_overview(repo_id, base_analysis, parsed, bugs, testing)
    overview["testing"] = testing
    overview["scanners"] = scanner_result
    try:
        overview["architecture_summary"] = summarise_repository(overview)
    except Exception as exc:
        overview["architecture_summary"] = f"AI architecture summary unavailable: {exc}"
    result = {
        "repo_id": repo_id,
        "source_url": source_url,
        "summary": graph_summary(graph),
        "graph": graph_to_json(graph),
        "chunks_stored": chunks_stored,
        "bugs": findings_summary(bugs),
        "git": history,
        "scanners": scanner_result,
        "testing": testing,
        "overview": overview,
    }
    persist_analysis(repo_id, result)
    return result


def _run_url_job(job_id: str, url: str) -> None:
    repo_path = None
    try:
        update_job(job_id, status="running", phase="Cloning repository")
        repo_path = ingest_from_url(url)
        result = _analyse_repo(repo_path, job_id, source_url=url)
        update_job(job_id, status="completed", phase="Analysis complete", result=result)
    except Exception as exc:
        update_job(job_id, status="failed", phase="Analysis failed", error=str(exc))
    finally:
        if repo_path:
            cleanup(repo_path)


def _run_zip_job(job_id: str, zip_path: str, upload_dir: str) -> None:
    repo_path = None
    try:
        update_job(job_id, status="running", phase="Extracting ZIP archive")
        repo_path = ingest_from_zip(zip_path)
        result = _analyse_repo(repo_path, job_id)
        update_job(job_id, status="completed", phase="Analysis complete", result=result)
    except Exception as exc:
        update_job(job_id, status="failed", phase="Analysis failed", error=str(exc))
    finally:
        if repo_path:
            cleanup(repo_path)
        shutil.rmtree(upload_dir, ignore_errors=True)

@router.post("/ingest/url", status_code=202)
async def ingest_url(payload: RepoURL, background_tasks: BackgroundTasks):
    job = create_job()
    if not enqueue(job["job_id"], "url", {"url": payload.url}):
        background_tasks.add_task(_run_url_job, job["job_id"], payload.url)
    return {"job_id": job["job_id"], "status": job["status"], "phase": job["phase"]}

@router.post("/ingest/zip", status_code=202)
async def ingest_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    tmp_zip = await _save_upload(file)
    upload_dir = os.path.dirname(tmp_zip)
    job = create_job()
    if not enqueue(
        job["job_id"],
        "zip",
        {"zip_path": tmp_zip, "upload_dir": upload_dir},
    ):
        background_tasks.add_task(_run_zip_job, job["job_id"], tmp_zip, upload_dir)
    return {"job_id": job["job_id"], "status": job["status"], "phase": job["phase"]}

@router.post("/ingest/debug")
async def ingest_debug(payload: RepoURL):
    repo_path = None
    try:
        repo_path = ingest_from_url(payload.url)
        files = walk_repo(repo_path)
        return {"total_files_found": len(files), "files": [str(f) for f in files]}
    finally:
        if repo_path:
            cleanup(repo_path)


@router.get("/repositories/{repo_id}")
async def repository_details(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    return analysis


@router.get("/ingest/jobs/{job_id}")
async def ingestion_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found or the server restarted.")
    return job


@router.get("/repositories/{repo_id}/source")
async def repository_source(repo_id: str, path: str = Query(min_length=1)):
    content = get_source(repo_id, path)
    if content is None:
        raise HTTPException(status_code=404, detail="Source file not found.")
    return {"path": path, "content": content}


@router.get("/repositories")
async def repository_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    repositories = list_analyses(limit, offset)
    return {
        "repositories": repositories,
        "limit": limit,
        "offset": offset,
        "count": len(repositories),
        "total": count_analyses(),
    }


@router.post("/repositories/compare")
async def compare_repositories(payload: ComparisonPayload):
    repo_ids = list(dict.fromkeys(payload.repo_ids))
    if len(repo_ids) < 2:
        raise HTTPException(status_code=400, detail="Select at least two repositories.")
    if len(repo_ids) > 5:
        raise HTTPException(status_code=400, detail="Compare no more than five repositories.")

    analyses = []
    missing = []
    for repo_id in repo_ids:
        analysis = get_analysis(repo_id)
        if analysis:
            analyses.append(analysis)
        else:
            missing.append(repo_id)
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Repositories not found: {', '.join(missing)}",
        )
    return build_comparison(repo_ids, analyses)


@router.post("/repositories/compare/report")
async def compare_repositories_report(payload: ComparisonPayload):
    repo_ids = list(dict.fromkeys(payload.repo_ids))
    if len(repo_ids) < 2 or len(repo_ids) > 5:
        raise HTTPException(status_code=400, detail="Select between two and five repositories.")

    analyses = []
    for repo_id in repo_ids:
        analysis = get_analysis(repo_id)
        if not analysis:
            raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
        analyses.append(analysis)
    comparison = build_comparison(repo_ids, analyses)

    lines = [
        "# Repository Comparison Report",
        "",
        f"- Repository count: {comparison['summary']['repository_count']}",
        f"- Common findings: {comparison['summary']['common_finding_count']}",
        f"- Unique findings: {comparison['summary']['unique_finding_count']}",
        "",
        "## Repository metrics",
        "",
    ]
    for repository in comparison["repositories"]:
        lines.extend([
            f"### `{repository['repo_id']}`",
            f"- Files: {repository['files']}",
            f"- Relationships: {repository['relationships']}",
            f"- Symbol call edges: {repository['call_edges']}",
            f"- Health score: {repository['health_score']} / 100",
            f"- Findings: {repository['errors']} errors, "
            f"{repository['warnings']} warnings, {repository['info']} info",
            "",
        ])
    lines.extend(["## Common findings", ""])
    if comparison["common_findings"]:
        for finding in comparison["common_findings"]:
            lines.append(
                f"- `{finding['rule']}` — {finding['file']}:{finding['line']}: "
                f"{finding['message']}"
            )
    else:
        lines.append("- No common findings across every repository.")
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": 'attachment; filename="repository-comparison.md"'},
        media_type="text/markdown",
    )


@router.get("/repositories/{repo_id}/overview")
async def repository_overview(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    overview = analysis.get("overview")
    if not overview:
        raise HTTPException(status_code=404, detail="Repository overview is not available.")
    return overview


@router.get("/repositories/{repo_id}/coverage")
async def repository_coverage(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    testing = analysis.get("testing")
    if testing is None:
        testing = analysis.get("overview", {}).get("testing", {})
    return testing


@router.get("/repositories/{repo_id}/git")
async def repository_git(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    return analysis.get("git", {
        "branch": None,
        "branches": [],
        "commits": [],
        "commit_count": 0,
    })


@router.get("/repositories/{repo_id}/pulls")
async def repository_pull_requests(
    repo_id: str,
    state: str = Query(default="open", pattern="^(open|closed|all)$"),
):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    source_url = analysis.get("source_url")
    if not source_url:
        raise HTTPException(status_code=400, detail="Pull requests require a GitHub source repository.")
    try:
        return {"pull_requests": list_pull_requests(source_url, state)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/repositories/{repo_id}/pulls/{pull_number}")
async def repository_pull_request_diff(
    repo_id: str,
    pull_number: int,
    installation_id: str | None = None,
):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    source_url = analysis.get("source_url")
    if not source_url:
        raise HTTPException(status_code=400, detail="Pull-request diff requires a GitHub source repository.")
    from app.services.github_integration import parse_github_repository
    parsed = parse_github_repository(source_url)
    if not parsed:
        raise HTTPException(status_code=400, detail="The source is not a GitHub repository.")
    owner, repository = parsed
    try:
        return get_pull_request_diff(owner, repository, pull_number, installation_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/repositories/{repo_id}/scan")
async def rescan_repository(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    source_root = get_settings().data_dir / "workspaces" / repo_id / "sources"
    scanner_result = run_real_scanners(str(source_root))
    return scanner_result


@router.post("/github/pull-requests/review")
async def create_pull_request_review(payload: PullRequestReviewPayload):
    try:
        result = post_pull_request_review(
            payload.owner,
            payload.repository,
            payload.pull_number,
            payload.body,
            payload.event,
            payload.installation_id,
        )
        return {"review": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/github/webhooks/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-Github-Event"),
):
    payload_bytes = await request.body()
    if not verify_webhook_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature.")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.") from exc

    event_path = get_settings().data_dir / "github_events.json"
    events = []
    if event_path.is_file():
        try:
            events = json.loads(event_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            events = []
    events.append({
        "event": x_github_event,
        "action": payload.get("action"),
        "delivery": request.headers.get("X-GitHub-Delivery"),
        "repository": payload.get("repository", {}).get("full_name"),
        "pull_request": (
            payload.get("pull_request", {}).get("number")
            if payload.get("pull_request")
            else None
        ),
    })
    event_path.write_text(json.dumps(events[-500:], indent=2), encoding="utf-8")
    return {"accepted": True, "event": x_github_event}


@router.delete("/repositories/{repo_id}")
async def remove_repository(repo_id: str):
    if not delete_analysis(repo_id):
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    delete_collection(repo_id)
    return {"deleted": True, "repo_id": repo_id}


@router.get("/repositories/{repo_id}/report")
async def repository_report(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")

    overview = analysis.get("overview", {})
    health = overview.get("health", {})
    lines = [
        "# Repository Analysis Report",
        "",
        f"- Repository ID: `{repo_id}`",
        f"- Source files: {analysis.get('summary', {}).get('total_files', 0)}",
        f"- Dependency relationships: {overview.get('dependency_edges', 0)}",
        f"- Health score: {health.get('health_score', 0)} / 100",
        "",
        "## AI architecture summary",
        "",
        overview.get("architecture_summary", "No AI summary was generated."),
        "",
        "## Technology stack",
        "",
    ]
    lines.extend(
        f"- {language}: {count} file(s)"
        for language, count in overview.get("languages", {}).items()
    )
    testing = analysis.get("testing", overview.get("testing", {}))
    coverage = testing.get("coverage", {})
    lines.extend([
        "",
        "## Tests and coverage",
        f"- Test frameworks: {', '.join(testing.get('frameworks', [])) or 'Not detected'}",
        f"- Test files: {testing.get('test_file_count', 0)}",
        f"- Likely untested source files: {testing.get('untested_file_count', 0)}",
        f"- Coverage: {coverage.get('line_percent') if coverage.get('available') else 'No report detected'}",
        "",
    ])
    lines.extend(["", "## Prioritized findings", ""])
    findings = overview.get("prioritized_findings", [])
    if findings:
        for finding in findings:
            lines.append(
                f"- **{finding.get('severity', 'info').upper()}** "
                f"`{finding.get('file', '?')}:{finding.get('line', '?')}` "
                f"{finding.get('rule', 'finding')}: {finding.get('message', '')}"
            )
    else:
        lines.append("- No findings detected.")
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Disposition": f'attachment; filename="{repo_id}-report.md"'},
        media_type="text/markdown",
    )


@router.get("/repositories/{repo_id}/report.pdf")
async def repository_pdf_report(repo_id: str):
    analysis = get_analysis(repo_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")

    try:
        from io import BytesIO
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="PDF export dependency is not installed.") from exc

    overview = analysis.get("overview", {})
    health = overview.get("health", {})
    findings = overview.get("prioritized_findings", [])
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=48,
        leftMargin=48,
        topMargin=48,
        bottomMargin=48,
        title=f"Repository report - {repo_id}",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Repository Analysis Report", styles["Title"]),
        Spacer(1, 0.15 * inch),
        Paragraph(f"<b>Repository ID:</b> {repo_id}", styles["Normal"]),
        Paragraph(
            f"<b>Files:</b> {analysis.get('summary', {}).get('total_files', 0)} "
            f"&nbsp;&nbsp; <b>Relationships:</b> {overview.get('dependency_edges', 0)} "
            f"&nbsp;&nbsp; <b>Health:</b> {health.get('health_score', 0)} / 100",
            styles["Normal"],
        ),
        Spacer(1, 0.25 * inch),
        Paragraph("Architecture Summary", styles["Heading2"]),
        Paragraph(
            str(overview.get("architecture_summary", "No AI summary was generated.")).replace("\n", "<br/>"),
            styles["BodyText"],
        ),
        Spacer(1, 0.18 * inch),
        Paragraph("Technology Stack", styles["Heading2"]),
    ]

    language_rows = [["Language", "Files"]] + [
        [str(language), str(count)]
        for language, count in overview.get("languages", {}).items()
    ]
    if len(language_rows) > 1:
        table = Table(language_rows, colWidths=[2.2 * inch, 1 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#293966")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#a8b3c7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)

    testing = analysis.get("testing", overview.get("testing", {}))
    coverage = testing.get("coverage", {})
    story.extend([
        Spacer(1, 0.18 * inch),
        Paragraph("Tests and Coverage", styles["Heading2"]),
        Paragraph(
            f"<b>Frameworks:</b> {', '.join(testing.get('frameworks', [])) or 'Not detected'}"
            f"<br/><b>Test files:</b> {testing.get('test_file_count', 0)}"
            f"<br/><b>Likely untested source files:</b> {testing.get('untested_file_count', 0)}"
            f"<br/><b>Line coverage:</b> "
            f"{coverage.get('line_percent') if coverage.get('available') else 'No report detected'}",
            styles["BodyText"],
        ),
    ])

    story.extend([
        Spacer(1, 0.18 * inch),
        Paragraph("Prioritized Findings", styles["Heading2"]),
    ])
    if findings:
        for finding in findings[:50]:
            severity = str(finding.get("severity", "info")).upper()
            location = f"{finding.get('file', '?')}:{finding.get('line', '?')}"
            story.append(Paragraph(
                f"<b>[{severity}] {finding.get('rule', 'finding')}</b><br/>"
                f"{location}<br/>{finding.get('message', '')}",
                styles["BodyText"],
            ))
            story.append(Spacer(1, 0.08 * inch))
    else:
        story.append(Paragraph("No findings detected.", styles["BodyText"]))

    document.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{repo_id}-report.pdf"'},
    )


@router.post("/repositories/{repo_id}/share")
async def share_repository(repo_id: str):
    token = create_share(repo_id)
    if not token:
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    return {"token": token, "enabled": True}


@router.delete("/repositories/{repo_id}/share")
async def revoke_repository_share(repo_id: str):
    if not revoke_share(repo_id):
        raise HTTPException(status_code=404, detail="Analysis workspace not found.")
    return {"enabled": False}


@router.get("/shared/{token}")
async def get_shared_repository(token: str):
    analysis = get_shared_analysis(token)
    if not analysis:
        raise HTTPException(status_code=404, detail="Shared workspace not found or sharing was revoked.")
    analysis.pop("share", None)
    return analysis
