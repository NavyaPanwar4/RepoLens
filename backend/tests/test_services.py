import app.services.vector_store as vector_store
from app.services.github_integration import verify_webhook_signature
from app.services.graph import build_graph, graph_to_json
from app.services.scanner import run_real_scanners
from app.services.comparison import build_comparison
from app.services.coverage import analyze_tests, parse_coverage_report
from app.services.queue import enqueue


def test_store_chunks_splits_large_batches(monkeypatch):
    writes = []

    class Collection:
        def upsert(self, **kwargs):
            writes.append(len(kwargs["ids"]))

    monkeypatch.setattr(vector_store, "get_or_create_collection", lambda _repo_id: Collection())
    monkeypatch.setattr(
        vector_store,
        "embed_texts",
        lambda batch: [[1.0] for _ in batch],
    )
    chunks = [
        {"id": str(index), "text": "text", "metadata": {"file": "a.py"}}
        for index in range(17471)
    ]

    assert vector_store.store_chunks("test", chunks) == 17471
    assert writes[-1] == 471
    assert max(writes) == 1000


def test_webhook_signature_requires_configured_secret(monkeypatch):
    class Settings:
        github_webhook_secret = ""
    monkeypatch.setattr(
        "app.services.github_integration.get_settings",
        lambda: Settings(),
    )
    assert verify_webhook_signature(b'{"zen":"test"}', "sha256=abc") is False


def test_graph_adds_symbol_call_edges():
    parsed = [
        {
            "file": "src/main.py",
            "language": "py",
            "functions": [{"name": "main"}],
            "classes": [],
            "imports": [],
            "calls": [{"name": "build_report()", "simple_name": "build_report", "start_line": 12}],
        },
        {
            "file": "src/report.py",
            "language": "py",
            "functions": [{"name": "build_report"}],
            "classes": [],
            "imports": [],
            "calls": [],
        },
    ]

    graph = build_graph(parsed)
    data = graph_to_json(graph)
    call_edges = [edge for edge in data["edges"] if edge["kind"] == "call"]

    assert len(call_edges) == 1
    assert call_edges[0]["source"] == "src/main.py"
    assert call_edges[0]["target"] == "src/report.py"
    assert call_edges[0]["confidence"] == "inferred"


def test_real_scanners_disabled_by_default(monkeypatch, tmp_path):
    class Settings:
        enable_real_scanners = False

    monkeypatch.setattr(
        "app.services.scanner.get_settings",
        lambda: Settings(),
    )
    result = run_real_scanners(str(tmp_path))

    assert result["enabled"] is False
    assert result["findings"] == []


def test_queue_falls_back_without_redis(monkeypatch):
    class Settings:
        redis_url = ""
    monkeypatch.setattr(
        "app.services.queue.get_settings",
        lambda: Settings(),
    )
    assert enqueue("job-1", "url", {"url": "https://github.com/example/repo"}) is False


def test_comparison_calculates_health_and_findings():
    analyses = [
        {
            "summary": {"total_files": 100, "total_edges": 20},
            "bugs": {
                "errors": 1,
                "warnings": 2,
                "info": 3,
                "findings": [
                    {"rule": "unsafe-eval", "file": "main.py", "line": 10, "message": "Unsafe"},
                ],
            },
            "overview": {
                "dependency_edges": 20,
                "call_edges": 5,
                "health_score": 75,
                "health": {"health_score": 75, "standalone_files": 10},
            },
        },
        {
            "summary": {"total_files": 80, "total_edges": 10},
            "bugs": {
                "errors": 2,
                "warnings": 1,
                "info": 1,
                "findings": [
                    {"rule": "unsafe-eval", "file": "main.py", "line": 10, "message": "Unsafe"},
                ],
            },
            "overview": {
                "dependency_edges": 10,
                "call_edges": 2,
                "health_score": 65,
                "health": {"health_score": 65, "standalone_files": 12},
            },
        },
    ]
    comparison = build_comparison(["repo-a", "repo-b"], analyses)

    assert comparison["summary"]["repository_count"] == 2
    assert comparison["summary"]["largest_repository"] == "repo-a"
    assert comparison["summary"]["strongest_health"] == "repo-a"
    assert comparison["summary"]["common_finding_count"] == 1


def test_lcov_coverage_and_test_discovery(tmp_path):
    (tmp_path / "lcov.info").write_text(
        "SF:src/main.py\n"
        "DA:10,1\n"
        "DA:11,0\n"
        "end_of_record\n",
        encoding="utf-8",
    )
    parsed = [
        {
            "file": str(tmp_path / "src" / "main.py"),
            "raw": "def main():\n    pass\n",
        },
        {
            "file": str(tmp_path / "tests" / "test_main.py"),
            "raw": "def test_main():\n    assert True\n",
        },
    ]

    result = analyze_tests(str(tmp_path), parsed)

    assert result["test_file_count"] == 1
    assert result["coverage"]["available"] is True
    assert result["coverage"]["line_percent"] == 50.0
    assert result["coverage"]["format"] == "LCOV"
