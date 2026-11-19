"""Dependency graph construction using conservative, path-aware import resolution."""

import re
from pathlib import PurePosixPath

import networkx as nx


SOURCE_EXTENSIONS = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".rs", ".c", ".cc", ".cpp", ".cxx")


def _candidate_paths(base: PurePosixPath) -> list[str]:
    """Return supported file candidates for an extension-less local import."""
    candidates = [base.as_posix()]
    if not base.suffix:
        candidates.extend(base.with_suffix(ext).as_posix() for ext in SOURCE_EXTENSIONS)
        candidates.extend((base / f"index{ext}").as_posix() for ext in (".js", ".jsx", ".ts", ".tsx"))
        candidates.append((base / "__init__.py").as_posix())
    return candidates


def _resolve_relative(source: str, specifier: str, known_paths: set[str]) -> set[str]:
    if not specifier.startswith("."):
        return set()
    target = PurePosixPath(source).parent / specifier
    return {candidate for candidate in _candidate_paths(target) if candidate in known_paths}


def _resolve_python(source: str, statement: str, known_paths: set[str]) -> set[str]:
    match = re.match(r"\s*from\s+([.\w]+)\s+import\s+", statement)
    if not match:
        match = re.match(r"\s*import\s+([\w.]+)", statement)
    if not match:
        return set()

    module = match.group(1)
    source_dir = PurePosixPath(source).parent
    relative_dots = len(module) - len(module.lstrip("."))
    module_name = module.lstrip(".").replace(".", "/")
    base = source_dir if relative_dots else PurePosixPath()
    for _ in range(max(relative_dots - 1, 0)):
        base = base.parent
    return {candidate for candidate in _candidate_paths(base / module_name) if candidate in known_paths}


def _resolve_imports(source: str, statement: str, known_paths: set[str]) -> set[str]:
    """Resolve local imports; external packages deliberately create no edge."""
    resolved = _resolve_python(source, statement, known_paths)
    for specifier in re.findall(r"(?:from\s+|require\()\s*['\"]([^'\"]+)['\"]", statement):
        resolved.update(_resolve_relative(source, specifier, known_paths))
    for specifier in re.findall(r"#include\s*[<\"]([^>\"]+)[>\"]", statement):
        resolved.update(_resolve_relative(source, f"./{specifier}", known_paths))

    java_match = re.match(r"\s*import\s+([\w.]+);", statement)
    if java_match:
        java_path = PurePosixPath(java_match.group(1).replace(".", "/")).with_suffix(".java").as_posix()
        if java_path in known_paths:
            resolved.add(java_path)
    return resolved


def build_graph(parsed_files: list) -> nx.DiGraph:
    """Build import and symbol-call relationships between files."""
    graph = nx.DiGraph()
    known_paths = {parsed["file"] for parsed in parsed_files}
    symbol_index = {}

    for parsed in parsed_files:
        for function in parsed.get("functions", []):
            symbol_index.setdefault(function["name"], []).append(parsed["file"])
        for klass in parsed.get("classes", []):
            symbol_index.setdefault(klass["name"], []).append(parsed["file"])
        graph.add_node(
            parsed["file"],
            language=parsed.get("language", ""),
            functions=[function["name"] for function in parsed.get("functions", [])],
            classes=[klass["name"] for klass in parsed.get("classes", [])],
            num_functions=len(parsed.get("functions", [])),
            num_classes=len(parsed.get("classes", [])),
            calls=[call for call in parsed.get("calls", [])],
        )

    for parsed in parsed_files:
        for statement in parsed.get("imports", []):
            for imported_file in _resolve_imports(parsed["file"], statement, known_paths):
                if graph.has_edge(parsed["file"], imported_file):
                    graph.edges[parsed["file"], imported_file]["label"] += f"; {statement}"
                    graph.edges[parsed["file"], imported_file]["kind"] = "import"
                else:
                    graph.add_edge(
                        parsed["file"],
                        imported_file,
                        label=statement,
                        kind="import",
                        confidence="high",
                    )

        for call in parsed.get("calls", []):
            candidates = symbol_index.get(call["simple_name"], [])
            for imported_file in candidates:
                if imported_file == parsed["file"]:
                    continue
                edge_label = f"calls {call['simple_name']} (line {call['start_line']})"
                if graph.has_edge(parsed["file"], imported_file):
                    existing = graph.edges[parsed["file"], imported_file]
                    existing["label"] = existing["label"] + "; " + edge_label
                    existing["kind"] = "mixed"
                else:
                    graph.add_edge(
                        parsed["file"],
                        imported_file,
                        label=edge_label,
                        kind="call",
                        confidence="inferred",
                    )
    return graph


def graph_summary(graph: nx.DiGraph) -> dict:
    call_edges = sum(
        1
        for _, _, data in graph.edges(data=True)
        if data.get("kind") in {"call", "mixed"}
    )
    import_edges = sum(
        1
        for _, _, data in graph.edges(data=True)
        if data.get("kind") in {"import", "mixed"}
    )
    return {
        "total_files": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "call_edges": call_edges,
        "import_edges": import_edges,
        "hub_files": sorted(graph.nodes, key=lambda node: graph.in_degree(node), reverse=True)[:5],
        "isolated_files": [node for node in graph.nodes if graph.degree(node) == 0],
        "edges": list(graph.edges()),
    }


def graph_to_json(graph: nx.DiGraph) -> dict:
    return {
        "nodes": [
            {
                "id": node,
                "language": graph.nodes[node].get("language"),
                "functions": graph.nodes[node].get("functions", []),
                "classes": graph.nodes[node].get("classes", []),
                "num_functions": graph.nodes[node].get("num_functions", 0),
                "num_classes": graph.nodes[node].get("num_classes", 0),
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
            }
            for node in graph.nodes
        ],
        "edges": [
            {
                "source": source,
                "target": target,
                "label": graph.edges[source, target].get("label", ""),
                "kind": graph.edges[source, target].get("kind", "dependency"),
                "confidence": graph.edges[source, target].get("confidence", "high"),
            }
            for source, target in graph.edges
        ],
    }
