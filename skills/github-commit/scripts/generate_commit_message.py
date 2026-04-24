#!/usr/bin/env python3
"""Generate a Conventional Commits draft from staged git changes."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import Counter


DOC_EXTENSIONS = {
    ".md",
    ".mdx",
    ".rst",
    ".txt",
    ".adoc",
}

TEST_SUFFIXES = (
    "_test.go",
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
    "_spec.rb",
)

BUILD_FILES = {
    "go.mod",
    "go.sum",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Cargo.toml",
    "Cargo.lock",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "Dockerfile",
    "Makefile",
}


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "git command failed"
        raise RuntimeError(stderr)
    return result.stdout


def get_name_status() -> list[tuple[str, str]]:
    output = run_git(["diff", "--cached", "--name-status", "--find-renames"])
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        entries.append((status, path))
    return entries


def get_numstat() -> dict[str, tuple[int, int]]:
    output = run_git(["diff", "--cached", "--numstat", "--find-renames"])
    stats: dict[str, tuple[int, int]] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        added_raw, deleted_raw, path = line.split("\t", 2)
        added = 0 if added_raw == "-" else int(added_raw)
        deleted = 0 if deleted_raw == "-" else int(deleted_raw)
        stats[path] = (added, deleted)
    return stats


def is_doc_file(path: str) -> bool:
    base = os.path.basename(path).lower()
    if base.startswith("readme"):
        return True
    return os.path.splitext(path)[1].lower() in DOC_EXTENSIONS or path.startswith("docs/")


def is_test_file(path: str) -> bool:
    base = os.path.basename(path)
    lower = path.lower()
    return (
        lower.startswith("test/")
        or lower.startswith("tests/")
        or "/test/" in lower
        or "/tests/" in lower
        or base.endswith(TEST_SUFFIXES)
    )


def is_ci_file(path: str) -> bool:
    lower = path.lower()
    return (
        lower.startswith(".github/workflows/")
        or lower.startswith(".circleci/")
        or "gitlab-ci" in lower
        or "jenkins" in lower
    )


def is_build_file(path: str) -> bool:
    base = os.path.basename(path)
    lower = path.lower()
    return (
        base in BUILD_FILES
        or lower.endswith(".dockerfile")
        or lower.startswith("docker/")
        or lower.startswith("build/")
        or lower.startswith("scripts/")
    )


def sanitize_scope(value: str) -> str:
    scope = value.strip().lower()
    scope = re.sub(r"[^a-z0-9._/-]+", "-", scope)
    scope = scope.replace("/", "-").strip("-")
    return scope


def infer_scope(paths: list[str]) -> str | None:
    if not paths:
        return None

    ignore = {"src", "pkg", "internal", "cmd", "app", "lib", "docs", "test", "tests", ".github"}
    candidates: list[str] = []
    for path in paths:
        parts = [part for part in path.split("/") if part and part not in ignore]
        if len(parts) >= 2:
            candidates.append(parts[0])
        elif len(parts) == 1 and "." not in parts[0]:
            candidates.append(parts[0])

    if candidates:
        top = Counter(candidates).most_common(1)[0][0]
        scope = sanitize_scope(top)
        if scope:
            return scope

    if len(paths) == 1:
        stem = os.path.splitext(os.path.basename(paths[0]))[0]
        scope = sanitize_scope(stem)
        return scope or None

    return None


def human_target(paths: list[str], stats: dict[str, tuple[int, int]]) -> str:
    if not paths:
        return "staged files"

    ranked = sorted(
        paths,
        key=lambda path: (
            -(stats.get(path, (0, 0))[0] + stats.get(path, (0, 0))[1]),
            path.count("/"),
            path,
        ),
    )
    candidate = ranked[0]
    base = os.path.basename(candidate)
    stem, _ = os.path.splitext(base)

    if stem.lower() in {"index", "main", "__init__", "mod"} and "/" in candidate:
        stem = os.path.basename(os.path.dirname(candidate))
    if base.lower().startswith("readme"):
        return "README"

    target = stem.replace("_", " ").replace("-", " ").strip()
    return target or "staged files"


def infer_type(paths: list[str], stats: dict[str, tuple[int, int]], statuses: list[str], default_type: str) -> str:
    if paths and all(is_doc_file(path) for path in paths):
        return "docs"
    if paths and all(is_test_file(path) for path in paths):
        return "test"
    if paths and all(is_ci_file(path) for path in paths):
        return "ci"
    if paths and all(is_build_file(path) for path in paths):
        return "build"

    total_added = sum(added for added, _ in stats.values())
    total_deleted = sum(deleted for _, deleted in stats.values())
    has_new_file = any(status == "A" for status in statuses)
    has_rename = any(status.startswith("R") for status in statuses)

    if has_rename and total_added == 0 and total_deleted == 0:
        return "refactor"
    if has_new_file and default_type == "chore":
        return "feat"
    if total_deleted > total_added * 2 and default_type == "chore":
        return "fix"
    return default_type


def infer_subject(commit_type: str, target: str, has_new_file: bool) -> str:
    target = target.strip() or "staged files"
    target_lower = target.lower()

    if commit_type == "docs":
        return "update README" if target == "README" else f"update {target_lower} documentation"
    if commit_type == "test":
        if has_new_file:
            return f"add coverage for {target_lower}"
        return f"update tests for {target_lower}"
    if commit_type == "ci":
        return f"update {target_lower} workflow"
    if commit_type == "build":
        if "lock" in target_lower or "mod" in target_lower or "package" in target_lower:
            return "update dependencies"
        return f"update {target_lower} build settings"
    if commit_type == "feat":
        verb = "add" if has_new_file else "implement"
        return f"{verb} {target_lower}"
    if commit_type == "fix":
        return f"fix {target_lower}"
    if commit_type == "refactor":
        return f"refactor {target_lower}"
    return f"update {target_lower}"


def build_body(paths: list[str], stats: dict[str, tuple[int, int]]) -> str:
    total_added = sum(added for added, _ in stats.values())
    total_deleted = sum(deleted for _, deleted in stats.values())
    preview = ", ".join(paths[:3])
    if len(paths) > 3:
        preview = f"{preview}, ..."
    lines = [
        f"- touch {len(paths)} staged file(s)",
        f"- diff stats: +{total_added}/-{total_deleted}",
    ]
    if preview:
        lines.append(f"- files: {preview}")
    return "\n".join(lines)


def build_commit_message(
    *,
    type_override: str | None = None,
    scope_override: str | None = None,
    summary_override: str | None = None,
    default_type: str = "chore",
    with_body: bool = False,
) -> str:
    entries = get_name_status()
    stats = get_numstat()
    if not entries:
        raise RuntimeError("no staged changes found")

    statuses = [status for status, _ in entries]
    paths = [path for _, path in entries]
    commit_type = type_override or infer_type(paths, stats, statuses, default_type)
    scope = sanitize_scope(scope_override) if scope_override else infer_scope(paths)
    target = human_target(paths, stats)
    has_new_file = any(status == "A" for status in statuses)
    subject_text = summary_override.strip() if summary_override else infer_subject(commit_type, target, has_new_file)
    header = f"{commit_type}({scope}): {subject_text}" if scope else f"{commit_type}: {subject_text}"

    if not with_body:
        return header
    return f"{header}\n\n{build_body(paths, stats)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Conventional Commits draft from staged git changes."
    )
    parser.add_argument(
        "--type",
        choices=["feat", "fix", "docs", "test", "refactor", "build", "ci", "chore"],
        help="Override the inferred commit type.",
    )
    parser.add_argument(
        "--scope",
        help="Override the inferred scope.",
    )
    parser.add_argument(
        "--summary",
        help="Override the inferred subject text. Do not include 'type(scope):'.",
    )
    parser.add_argument(
        "--default-type",
        choices=["feat", "fix", "chore"],
        default="chore",
        help="Fallback type when inference is inconclusive.",
    )
    parser.add_argument(
        "--with-body",
        action="store_true",
        help="Append a short body draft after the subject line.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        print(
            build_commit_message(
                type_override=args.type,
                scope_override=args.scope,
                summary_override=args.summary,
                default_type=args.default_type,
                with_body=args.with_body,
            )
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
