#!/usr/bin/env python3
"""Heuristic quality scanner for the quant repository."""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
SKIP_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__", "logs"}
TEXT_SUFFIXES = {".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
DEFAULT_PATHS = ["src", "tests", "docs", "AGENTS.md", "CONTEXT.md"]
LEGACY_PATTERNS = {
    "PLAN/": re.compile(r"PLAN/"),
    "PLAN_LEGACY": re.compile(r"PLAN_LEGACY"),
    "ghost": re.compile(r"\bghost\b", re.IGNORECASE),
    "scripts.ghost_": re.compile(r"scripts\.ghost_"),
    "data/ghost": re.compile(r"data/ghost"),
}
NETWORK_PATTERNS = re.compile(
    r"api\.bybit\.com|fetch_live_klines|ccxt\.(bybit|binance|okx)\(|"
    r"requests\.(get|post|put|delete)\(|httpx\.(get|post|put|delete)\(|"
    r"aiohttp\.ClientSession\("
)
EXCHANGE_MUTATION_PATTERNS = re.compile(r"\b(create_order|cancel_order|set_leverage|market_order)\b")
POSITION_LIFECYCLE_PATTERNS = re.compile(r"\b(close_position)\b")
CONFIG_GET_PATTERN = re.compile(r"\.get\(\s*['\"][A-Za-z0-9_.-]+['\"]\s*,")
YAML_LOAD_PATTERN = re.compile(r"\byaml\.(safe_load|load)\(")
SEVERITY_ORDER = {"Blocker": 0, "High": 1, "Medium": 2, "Low": 3}
@dataclass(order=True)
class Finding:
    severity: str
    category: str
    path: str
    line: int
    detail: str
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", default=DEFAULT_PATHS)
    parser.add_argument("--max-file-lines", type=int, default=200)
    parser.add_argument("--max-function-lines", type=int, default=60)
    parser.add_argument("--max-class-lines", type=int, default=120)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    return parser.parse_args()
def iter_files(paths: Iterable[str]) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix in TEXT_SUFFIXES:
                yield path
            continue
        for child in path.rglob("*"):
            if child.is_file() and child.suffix in TEXT_SUFFIXES:
                if not any(part in SKIP_DIRS for part in child.parts):
                    yield child
def record(
    findings: list[Finding],
    severity: str,
    category: str,
    path: Path,
    line: int,
    detail: str,
) -> None:
    findings.append(Finding(severity, category, str(path), line, detail))
def add_file_length_finding(
    findings: list[Finding], path: Path, text: str, max_lines: int
) -> None:
    line_count = len(text.splitlines())
    if line_count > max_lines:
        detail = f"{line_count} lines exceeds {max_lines}; inspect cohesion before refactoring."
        record(findings, "Medium", "oversized-surface", path, 1, detail)
def add_python_ast_findings(
    findings: list[Finding],
    path: Path,
    text: str,
    max_function_lines: int,
    max_class_lines: int,
) -> None:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        record(findings, "High", "parse-error", path, exc.lineno or 1, str(exc))
        return

    for node in ast.walk(tree):
        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            continue
        span = int(node.end_lineno) - int(node.lineno) + 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and span > max_function_lines:
            detail = f"{node.name} is {span} lines; inspect branching and side effects."
            record(findings, "Medium", "oversized-function", path, int(node.lineno), detail)
        elif isinstance(node, ast.ClassDef) and span > max_class_lines:
            detail = f"{node.name} is {span} lines; inspect responsibility boundaries."
            record(findings, "Medium", "oversized-class", path, int(node.lineno), detail)
def add_legacy_findings(findings: list[Finding], path: Path, line_no: int, line: str) -> None:
    for label, pattern in LEGACY_PATTERNS.items():
        if pattern.search(line):
            record(findings, "Medium", "legacy-reference", path, line_no, f"Contains {label}.")
def add_config_findings(
    findings: list[Finding], path: Path, line_no: int, line: str, is_test: bool
) -> None:
    is_config_boundary = "src/core/config.py" in str(path) or "/config/" in str(path)
    if CONFIG_GET_PATTERN.search(line):
        record(
            findings,
            "Medium",
            "config-boundary-check",
            path,
            line_no,
            "Uses .get(..., default); verify this is not config-origin data.",
        )
    if YAML_LOAD_PATTERN.search(line) and not is_config_boundary and not is_test:
        record(findings, "High", "config-boundary-leak", path, line_no, "Loads YAML outside the config boundary.")
def add_test_network_finding(
    findings: list[Finding], path: Path, text: str, line_no: int, line: str
) -> None:
    if not NETWORK_PATTERNS.search(line) or "patch(" in line or "mock" in line.lower():
        return
    live_marked = "@pytest.mark.live" in text
    severity = "Low" if live_marked else "High"
    detail = "Network-like call in live-marked test." if live_marked else "Possible network call in offline test."
    record(findings, severity, "test-integrity", path, line_no, detail)
def add_live_safety_findings(findings: list[Finding], path: Path, line_no: int, line: str) -> None:
    path_text = str(path)
    if EXCHANGE_MUTATION_PATTERNS.search(line):
        allowed = "src/engine/trader/execution" in path_text
        severity = "Low" if allowed else "Blocker"
        detail = "Live mutation term in execution module." if allowed else "Live mutation term outside explicit execution module."
        record(findings, severity, "live-safety", path, line_no, detail)
    if POSITION_LIFECYCLE_PATTERNS.search(line):
        allowed = "src/engine/trader/state" in path_text
        severity = "Low" if allowed else "Medium"
        detail = "Position lifecycle term in state module." if allowed else "Position close term; inspect that it is not hidden exchange mutation."
        record(findings, severity, "live-safety", path, line_no, detail)
def add_pattern_findings(findings: list[Finding], path: Path, text: str) -> None:
    is_py = path.suffix == ".py"
    is_test = bool(path.parts and path.parts[0] == "tests")
    for line_no, line in enumerate(text.splitlines(), start=1):
        add_legacy_findings(findings, path, line_no, line)
        if is_py:
            add_config_findings(findings, path, line_no, line, is_test)
            if is_test:
                add_test_network_finding(findings, path, text, line_no, line)
            else:
                add_live_safety_findings(findings, path, line_no, line)
def collect_findings(args: argparse.Namespace) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(set(iter_files(args.paths))):
        text = path.read_text(encoding="utf-8", errors="ignore")
        add_file_length_finding(findings, path, text, args.max_file_lines)
        add_pattern_findings(findings, path, text)
        if path.suffix == ".py":
            add_python_ast_findings(findings, path, text, args.max_function_lines, args.max_class_lines)
    return sorted(findings, key=lambda item: (SEVERITY_ORDER[item.severity], item.path, item.line))
def print_markdown(findings: list[Finding]) -> None:
    print(f"# Quant Code Quality Audit\n\nFindings: {len(findings)}\n")
    if not findings:
        print("No scanner signals found.")
        return
    print("| Severity | Category | Location | Detail |")
    print("| --- | --- | --- | --- |")
    for finding in findings:
        detail = finding.detail.replace("|", "\\|")
        print(f"| {finding.severity} | {finding.category} | `{finding.path}:{finding.line}` | {detail} |")
def main() -> int:
    args = parse_args()
    findings = collect_findings(args)
    if args.format == "json":
        print(json.dumps([asdict(item) for item in findings], indent=2))
    else:
        print_markdown(findings)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
