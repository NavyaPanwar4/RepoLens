"""Cross-repository comparison calculations."""


def _finding_key(finding: dict) -> tuple:
    return (
        finding.get("rule", ""),
        finding.get("file", ""),
        finding.get("line", 0),
        finding.get("message", ""),
    )


def build_comparison(repo_ids: list[str], analyses: list[dict]) -> dict:
    repositories = []
    for repo_id, analysis in zip(repo_ids, analyses):
        summary = analysis.get("summary", {})
        bugs = analysis.get("bugs", {})
        overview = analysis.get("overview", {})
        health = overview.get("health", {})
        graph = analysis.get("graph", {})
        findings = bugs.get("findings", overview.get("prioritized_findings", []))
        repositories.append({
            "repo_id": repo_id,
            "source_url": analysis.get("source_url"),
            "files": summary.get("total_files", len(graph.get("nodes", []))),
            "relationships": summary.get("total_edges", overview.get("dependency_edges", 0)),
            "call_edges": overview.get("call_edges", 0),
            "health_score": health.get("health_score", 0),
            "errors": bugs.get("errors", health.get("errors", 0)),
            "warnings": bugs.get("warnings", health.get("warnings", 0)),
            "info": bugs.get("info", health.get("info", 0)),
            "long_functions": health.get("long_functions", 0),
            "standalone_files": health.get("standalone_files", 0),
            "languages": overview.get("languages", {}),
            "frameworks": overview.get("frameworks", []),
            "entry_points": overview.get("entry_points", []),
            "central_files": overview.get("central_files", []),
            "findings": findings,
        })

    all_finding_keys = set()
    per_repository = {}
    for repository in repositories:
        keys = {_finding_key(finding) for finding in repository["findings"]}
        per_repository[repository["repo_id"]] = keys
        all_finding_keys.update(keys)

    finding_frequency = {}
    for finding_key in all_finding_keys:
        present_in = [
            repository["repo_id"]
            for repository in repositories
            if finding_key in per_repository[repository["repo_id"]]
        ]
        finding_frequency[finding_key] = present_in

    common = [
        finding_key
        for finding_key, present_in in finding_frequency.items()
        if len(present_in) == len(repositories)
    ]
    unique = [
        finding_key
        for finding_key, present_in in finding_frequency.items()
        if len(present_in) == 1
    ]

    if repositories:
        strongest = max(repositories, key=lambda item: item["health_score"])
        weakest = min(repositories, key=lambda item: item["health_score"])
        largest = max(repositories, key=lambda item: item["files"])
        most_connected = max(repositories, key=lambda item: item["relationships"])
    else:
        strongest = weakest = largest = most_connected = None

    return {
        "repositories": repositories,
        "summary": {
            "repository_count": len(repositories),
            "common_finding_count": len(common),
            "unique_finding_count": len(unique),
            "strongest_health": strongest["repo_id"] if strongest else None,
            "weakest_health": weakest["repo_id"] if weakest else None,
            "largest_repository": largest["repo_id"] if largest else None,
            "most_connected_repository": most_connected["repo_id"] if most_connected else None,
        },
        "common_findings": [
            {
                "rule": key[0],
                "file": key[1],
                "line": key[2],
                "message": key[3],
                "repositories": finding_frequency[key],
            }
            for key in sorted(common)
        ],
        "unique_findings": [
            {
                "rule": key[0],
                "file": key[1],
                "line": key[2],
                "message": key[3],
                "repositories": finding_frequency[key],
            }
            for key in sorted(unique)
        ],
    }
