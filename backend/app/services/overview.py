"""Repository overview and code-health calculations."""

from collections import Counter
from pathlib import Path


LANGUAGE_NAMES = {
    "py": "Python",
    "js": "JavaScript",
    "jsx": "React JSX",
    "ts": "TypeScript",
    "tsx": "React TSX",
    "java": "Java",
    "rs": "Rust",
    "cpp": "C++",
    "cc": "C++",
    "c": "C",
    "go": "Go",
    "rb": "Ruby",
    "php": "PHP",
    "swift": "Swift",
    "kt": "Kotlin",
    "md": "Markdown",
    "json": "JSON",
    "yaml": "YAML",
    "yml": "YAML",
    "html": "HTML",
    "css": "CSS",
    "sh": "Shell",
}


def _folder_for(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else "Root"


def _filename_for(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]


def detect_frameworks(parsed_files: list[dict], analysis: dict) -> list[str]:
    frameworks = set()
    names = {parsed["file"].replace("\\", "/").lower(): parsed for parsed in parsed_files}
    raw_by_name = " ".join(
        parsed.get("raw", "").lower()
        for parsed in parsed_files
        if parsed.get("raw")
    )

    if any(name.endswith("package.json") for name in names):
        package_text = "\n".join(
            parsed.get("raw", "")
            for parsed in parsed_files
            if parsed["file"].replace("\\", "/").lower().endswith("package.json")
        ).lower()
        if "next" in package_text:
            frameworks.add("Next.js")
        if "react" in package_text:
            frameworks.add("React")
        if "vite" in package_text:
            frameworks.add("Vite")
        if "vue" in package_text:
            frameworks.add("Vue")
        if "express" in package_text:
            frameworks.add("Express")

    if "fastapi" in raw_by_name or any(name.endswith(("requirements.txt", "pyproject.toml")) for name in names):
        if "fastapi" in raw_by_name:
            frameworks.add("FastAPI")
    if "django" in raw_by_name:
        frameworks.add("Django")
    if "flask" in raw_by_name:
        frameworks.add("Flask")
    if "spring" in raw_by_name:
        frameworks.add("Spring")
    return sorted(frameworks)


def build_overview(
    repo_id: str,
    analysis: dict,
    parsed_files: list[dict],
    findings: list[dict],
    testing: dict | None = None,
) -> dict:
    graph = analysis.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    languages = Counter()
    folders = Counter()
    for node in nodes:
        language = node.get("language") or "text"
        languages[LANGUAGE_NAMES.get(language, language.upper())] += 1
        folders[_folder_for(node["id"])] += 1

    entry_points = []
    for node in nodes:
        name = _filename_for(node["id"]).lower()
        if (
            name in {"main.py", "app.py", "manage.py", "server.py", "cli.py", "index.js", "index.ts",
                     "index.jsx", "index.tsx", "main.js", "main.ts", "app.jsx", "app.tsx"}
            or name.startswith("main.")
        ):
            entry_points.append(node["id"])

    central_files = sorted(
        nodes,
        key=lambda node: (
            node.get("in_degree", 0)
            + node.get("out_degree", 0)
            + node.get("num_functions", 0)
            + node.get("num_classes", 0)
        ),
        reverse=True,
    )[:8]

    severity_rank = {"error": 0, "warning": 1, "info": 2}
    prioritized = sorted(
        findings,
        key=lambda finding: (
            severity_rank.get(finding.get("severity"), 3),
            finding.get("file", ""),
            finding.get("line", 0),
        ),
    )

    long_functions = sum(
        1
        for parsed in parsed_files
        for function in parsed.get("functions", [])
        if function["end_line"] - function["start_line"] > 60
    )
    todo_count = sum(
        1
        for parsed in parsed_files
        for finding in findings
        if finding.get("rule") in {"todo-comment", "fixme-comment"}
        and finding.get("file") == parsed["file"]
    )
    total_lines = sum(len(parsed.get("raw", "").splitlines()) for parsed in parsed_files)
    connected = sum(
        1
        for node in nodes
        if node.get("in_degree", 0) > 0 or node.get("out_degree", 0) > 0
    )

    health = {
        "total_lines": total_lines,
        "errors": sum(f["severity"] == "error" for f in findings),
        "warnings": sum(f["severity"] == "warning" for f in findings),
        "info": sum(f["severity"] == "info" for f in findings),
        "long_functions": long_functions,
        "todo_count": todo_count,
        "connected_files": connected,
        "standalone_files": max(len(nodes) - connected, 0),
        "testing": testing or {},
        "health_score": max(
            0,
            100 - sum(f["severity"] == "error" for f in findings) * 8
            - sum(f["severity"] == "warning" for f in findings) * 3
            - sum(f["severity"] == "info" for f in findings),
        ),
    }

    return {
        "repo_id": repo_id,
        "languages": dict(languages),
        "frameworks": detect_frameworks(parsed_files, analysis),
        "folders": [{"name": name, "files": count} for name, count in folders.most_common()],
        "entry_points": entry_points,
        "central_files": [
            {
                "path": node["id"],
                "functions": node.get("num_functions", 0),
                "classes": node.get("num_classes", 0),
                "incoming": node.get("in_degree", 0),
                "outgoing": node.get("out_degree", 0),
            }
            for node in central_files
        ],
        "dependency_edges": len(edges),
        "call_edges": sum(
            1 for edge in edges
            if edge.get("kind") in {"call", "mixed"}
        ),
        "import_edges": sum(
            1 for edge in edges
            if edge.get("kind") in {"import", "mixed"}
        ),
        "health": health,
        "prioritized_findings": prioritized[:50],
    }
