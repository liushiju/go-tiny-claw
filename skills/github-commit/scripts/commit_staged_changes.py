#!/usr/bin/env python3
"""Create a non-interactive git commit from staged changes."""

from __future__ import annotations

import argparse
import subprocess
import sys

from generate_commit_message import build_commit_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a git commit from staged changes using Conventional Commits."
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
        help="Include an auto-generated body draft in the commit message.",
    )
    parser.add_argument(
        "--body",
        help="Append a manual body instead of the auto-generated body.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the commit message and git command without creating a commit.",
    )
    return parser.parse_args()


def split_message(message: str) -> tuple[str, str | None]:
    if "\n\n" not in message:
        return message.strip(), None
    subject, body = message.split("\n\n", 1)
    subject = subject.strip()
    body = body.strip() or None
    return subject, body


def run_git_commit(subject: str, body: str | None) -> subprocess.CompletedProcess[str]:
    command = ["git", "commit", "-m", subject]
    if body:
        command.extend(["-m", body])
    return subprocess.run(command, check=False, capture_output=True, text=True)


def get_head_short_hash() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to read commit hash")
    return result.stdout.strip()


def main() -> int:
    args = parse_args()
    try:
        auto_message = build_commit_message(
            type_override=args.type,
            scope_override=args.scope,
            summary_override=args.summary,
            default_type=args.default_type,
            with_body=args.with_body and not args.body,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    subject, inferred_body = split_message(auto_message)
    body = args.body.strip() if args.body else inferred_body

    if args.dry_run:
        print("subject:")
        print(subject)
        if body:
            print()
            print("body:")
            print(body)
        print()
        print("command:")
        preview = f'git commit -m "{subject}"'
        if body:
            preview += f' -m "{body}"'
        print(preview)
        return 0

    result = run_git_commit(subject, body)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git commit failed"
        print(f"error: {message}", file=sys.stderr)
        return result.returncode

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)

    try:
        commit_hash = get_head_short_hash()
    except RuntimeError as exc:
        print(f"warning: {exc}", file=sys.stderr)
        return 0

    print(f"created commit: {commit_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
