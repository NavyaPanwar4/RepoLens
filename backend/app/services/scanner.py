"""Optional Semgrep, Gitleaks, and dependency vulnerability integration."""

import json
import shutil
import subprocess
import tempfile
from uuid import uuid4
from pathlib import Path

from app.core.config import get_settings


SEVERITY_MAP = {
    "critical": "error",
    "error": "error",
    "high": "error",
    "medium": "warning",
    "moderate": "warning",
    "warning": "warning",
    "low": "info",
    "info": "info",
}


def _run(command: list[str], cwd: str, timeout: int = 300) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 124, "", str(exc)


def _severity(value: str | None) -> str:
    if not value:
        return "warning"
    return SEVERITY_MAP.get(str(value).lower(), "warning")


def run_semgrep(repo_path: str) -> tuple[list[dict], str]:
    executable = shutil.which("semgrep")
    if not executable:
        return [], "Semgrep is not installed."
    report = Path(tempfile.gettempdir()) / f"repolens-semgrep-{uuid4().hex}.json"
    code, stdout, stderr = _run(
        [executable, "scan", "--config", "auto", "--json", "--output", str(report)],
        repo_path,
    )
    if code not in {0, 1}:
        return [], f"Semgrep failed: {stderr or stdout}".strip()
    if not report.is_file():
        return [], "Semgrep completed without a report."
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [], f"Semgrep report could not be read: {exc}"

    findings = []
    for item in payload.get("results", []):
        path = item.get("path", "")
        start = item.get("start", {})
        extra = item.get("extra", {})
        findings.append({
            "file": path,
            "line": start.get("line", 1),
            "severity": _severity(extra.get("severity")),
            "rule": item.get("check_id", "semgrep"),
            "message": extra.get("message") or item.get("check_id", "Semgrep finding"),
            "snippet": extra.get("lines", ""),
            "source": "semgrep",
        })
    return findings, f"Semgrep scanned the repository and returned {len(findings)} findings."


def run_gitleaks(repo_path: str) -> tuple[list[dict], str]:
    executable = shutil.which("gitleaks")
    if not executable:
        return [], "Gitleaks is not installed."
    report = Path(tempfile.gettempdir()) / f"repolens-gitleaks-{uuid4().hex}.json"
    code, stdout, stderr = _run(
        [
            executable,
            "detect",
            "--source",
            repo_path,
            "--report-format",
            "json",
            "--report-path",
            str(report),
            "--no-banner",
        ],
        repo_path,
    )
    if code not in {0, 1}:
        return [], f"Gitleaks failed: {stderr or stdout}".strip()
    if not report.is_file():
        return [], "Gitleaks completed without findings."
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [], f"Gitleaks report could not be read: {exc}"

    findings = []
    for item in payload:
        findings.append({
            "file": item.get("File", ""),
            "line": item.get("StartLine", 1),
            "severity": "error",
            "rule": f"secret-{item.get('RuleID', 'detected')}",
            "message": f"Potential secret detected: {item.get('Description', 'secret')}",
            "snippet": "[secret redacted]",
            "source": "gitleaks",
        })
    return findings, f"Gitleaks scanned the repository and returned {len(findings)} findings."


def run_python_dependencies(repo_path: str) -> tuple[list[dict], str]:
    executable = shutil.which("pip-audit")
    manifest = Path(repo_path) / "requirements.txt"
    if not executable:
        return [], "pip-audit is not installed."
    if not manifest.is_file():
        return [], "No root requirements.txt was found."
    code, stdout, stderr = _run(
        [executable, "-r", str(manifest), "--format", "json", "--progress-spinner", "off"],
        repo_path,
    )
    if code not in {0, 1}:
        return [], f"pip-audit failed: {stderr or stdout}".strip()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return [], "pip-audit returned an unreadable report."

    findings = []
    for vulnerability in payload:
        package = vulnerability.get("name", "unknown")
        version = vulnerability.get("version", "")
        for item in vulnerability.get("vulns", []):
            findings.append({
                "file": "requirements.txt",
                "line": 1,
                "severity": "error" if item.get("fix_versions") else "warning",
                "rule": f"dependency-{item.get('id', 'vulnerability')}",
                "message": (
                    f"{package} {version} is vulnerable: "
                    f"{item.get('description', item.get('id', 'dependency vulnerability'))}"
                ),
                "snippet": f"{package}=={version}",
                "source": "pip-audit",
            })
    return findings, f"pip-audit checked dependencies and returned {len(findings)} findings."


def run_real_scanners(repo_path: str) -> dict:
    settings = get_settings()
    if not settings.enable_real_scanners:
        return {
            "enabled": False,
            "tools": [],
            "findings": [],
            "messages": ["Real scanners are disabled. Set ENABLE_REAL_SCANNERS=true to enable them."],
        }

    findings = []
    tools = []
    messages = []
    for name, runner in (
        ("semgrep", run_semgrep),
        ("gitleaks", run_gitleaks),
        ("pip-audit", run_python_dependencies),
    ):
        tool_findings, message = runner(repo_path)
        findings.extend(tool_findings)
        tools.append({
            "name": name,
            "status": "available" if (
                "scanned" in message.lower()
                or "checked dependencies" in message.lower()
            ) else "unavailable",
        })
        messages.append(message)

    return {
        "enabled": True,
        "tools": tools,
        "findings": findings,
        "messages": messages,
    }
