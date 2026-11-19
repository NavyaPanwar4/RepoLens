"""Test discovery and coverage report parsing."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path


SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".rs", ".go",
    ".rb", ".php", ".swift", ".kt", ".c", ".cc", ".cpp", ".cxx",
}

TEST_PATTERNS = (
    "_test.", ".test.", ".spec.", "/tests/", "/test/",
)

TEST_FILENAMES = {
    "jest.config.js", "jest.config.ts", "vitest.config.js",
    "vitest.config.ts", "pytest.ini", "tox.ini", "phpunit.xml",
}


def _normal_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    marker = "/sources/"
    if marker in normalized:
        normalized = normalized.split(marker, 1)[1]
    return normalized.lstrip("./")


def _is_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    if name.startswith("test_") or name.endswith(("_test.py", ".test.js", ".test.jsx",
                                               ".test.ts", ".test.tsx", ".spec.js",
                                               ".spec.jsx", ".spec.ts", ".spec.tsx")):
        return True
    return any(pattern in normalized for pattern in TEST_PATTERNS)


def detect_test_setup(parsed_files: list[dict]) -> dict:
    test_files = []
    frameworks = set()
    manifests = {}

    for parsed in parsed_files:
        path = _normal_path(parsed["file"])
        name = path.rsplit("/", 1)[-1].lower()
        raw = parsed.get("raw", "").lower()
        if _is_test_file(path):
            test_files.append(path)
        if name in TEST_FILENAMES:
            if "pytest" in name or name in {"pytest.ini", "tox.ini"}:
                frameworks.add("pytest")
            if "jest" in name:
                frameworks.add("Jest")
            if "vitest" in name:
                frameworks.add("Vitest")
            if "phpunit" in name:
                frameworks.add("PHPUnit")
        if name in {"package.json", "requirements.txt", "pyproject.toml"}:
            manifests[path] = raw

    combined_manifests = "\n".join(manifests.values())
    if "pytest" in combined_manifests:
        frameworks.add("pytest")
    if "jest" in combined_manifests:
        frameworks.add("Jest")
    if "vitest" in combined_manifests:
        frameworks.add("Vitest")
    if "unittest" in combined_manifests:
        frameworks.add("unittest")
    if "mocha" in combined_manifests:
        frameworks.add("Mocha")
    if "cypress" in combined_manifests:
        frameworks.add("Cypress")
    if "playwright" in combined_manifests:
        frameworks.add("Playwright")

    return {
        "frameworks": sorted(frameworks),
        "test_files": sorted(set(test_files)),
        "test_file_count": len(set(test_files)),
    }


def _parse_cobertura(path: Path) -> list[dict]:
    root = ET.parse(path).getroot()
    records = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "class":
            continue
        filename = node.attrib.get("filename")
        if not filename:
            continue
        lines = node.findall(".//{*}line")
        if not lines:
            lines = node.findall(".//line")
        covered = sum(
            1
            for line in lines
            if int(line.attrib.get("hits", "0")) > 0
        )
        records.append({
            "file": _normal_path(filename),
            "covered_lines": covered,
            "total_lines": len(lines),
        })
    return records


def _parse_lcov(path: Path) -> list[dict]:
    records = []
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("SF:"):
            if current:
                records.append(current)
            current = {
                "file": _normal_path(line[3:].strip()),
                "covered_lines": 0,
                "total_lines": 0,
            }
        elif current and line.startswith("DA:"):
            current["total_lines"] += 1
            try:
                hits = int(line.split(":", 1)[1].split(",", 1)[1])
            except (IndexError, ValueError):
                hits = 0
            if hits > 0:
                current["covered_lines"] += 1
        elif line == "end_of_record":
            if current:
                records.append(current)
                current = None
    return records


def _parse_istanbul(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = []
    for filename, data in payload.items():
        statement_map = data.get("statementMap", {})
        statement_counts = data.get("s", {})
        covered = sum(1 for count in statement_counts.values() if count > 0)
        records.append({
            "file": _normal_path(filename),
            "covered_lines": covered,
            "total_lines": len(statement_map),
        })
    return records


def parse_coverage_report(repo_path: str) -> dict:
    root = Path(repo_path)
    report_files = []
    coverage_records = []
    report_format = None

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        try:
            if name in {"coverage.xml", "cobertura.xml"} or name.endswith("cobertura.xml"):
                coverage_records.extend(_parse_cobertura(path))
                report_format = "Cobertura XML"
                report_files.append(path.name)
            elif name in {"lcov.info", "lcov-report.info"} or name.endswith(".lcov"):
                coverage_records.extend(_parse_lcov(path))
                report_format = "LCOV"
                report_files.append(path.name)
            elif name in {"coverage-final.json", "istanbul-coverage.json"}:
                coverage_records.extend(_parse_istanbul(path))
                report_format = "Istanbul JSON"
                report_files.append(path.name)
        except (ET.ParseError, json.JSONDecodeError, OSError, ValueError):
            continue

    merged = {}
    for record in coverage_records:
        file_key = record["file"].lower().lstrip("./")
        if file_key not in merged:
            merged[file_key] = {"covered_lines": 0, "total_lines": 0}
        merged[file_key]["covered_lines"] = max(
            merged[file_key]["covered_lines"],
            record["covered_lines"],
        )
        merged[file_key]["total_lines"] = max(
            merged[file_key]["total_lines"],
            record["total_lines"],
        )

    covered_lines = sum(item["covered_lines"] for item in merged.values())
    total_lines = sum(item["total_lines"] for item in merged.values())
    line_percent = round((covered_lines / total_lines * 100), 1) if total_lines else None

    return {
        "available": bool(merged),
        "format": report_format,
        "report_files": sorted(set(report_files)),
        "line_percent": line_percent,
        "covered_lines": covered_lines,
        "total_lines": total_lines,
        "covered_files": sum(
            1 for item in merged.values()
            if item["total_lines"] > 0 and item["covered_lines"] == item["total_lines"]
        ),
        "file_records": [
            {"file": filename, **item}
            for filename, item in sorted(merged.items())
        ],
    }


def analyze_tests(repo_path: str, parsed_files: list[dict]) -> dict:
    test_setup = detect_test_setup(parsed_files)
    coverage = parse_coverage_report(repo_path)

    source_files = []
    for parsed in parsed_files:
        path = _normal_path(parsed["file"])
        suffix = Path(path).suffix.lower()
        if suffix in SOURCE_SUFFIXES and not _is_test_file(path):
            source_files.append(path)

    covered_paths = {
        record["file"].lower().lstrip("./").rsplit("/", 1)[-1]
        for record in coverage.get("file_records", [])
    }
    untested = [
        path
        for path in source_files
        if Path(path).name.lower() not in covered_paths
    ]

    test_ratio = (
        round(test_setup["test_file_count"] / max(len(source_files), 1), 2)
        if source_files
        else 0
    )
    return {
        **test_setup,
        "source_file_count": len(source_files),
        "test_source_ratio": test_ratio,
        "untested_files": sorted(untested)[:100],
        "untested_file_count": len(untested),
        "coverage": coverage,
    }
