#!/usr/bin/env python3
"""Redact memories on user request — soft-delete with audit trail.

Per references/lifecycle.md, "forget" must never `rm` the file. Instead:
1. set frontmatter `status: redacted`
2. blank the body (keep frontmatter for audit)
3. add `redacted_at:` and `redacted_reason:` fields
4. log the action to `~/.memory/.audit-redactions.log`

Search excludes redacted memories by default (only `--include-superseded`
in search.py widens, which is for superseded — redacted is stricter).

Selection (one required):
  --name <slug>      # the frontmatter `name:`
  --path <relpath>   # path under <root>
  --topic <term>    # all files whose topic / description / name contains this

Safety:
  Default is DRY-RUN. Pass --apply to actually redact.
  Pass --reason "<text>" to record why (required for --apply).

Exit codes:
  0  — succeeded (or dry-run completed)
  1  — nothing matched
  2  — invocation / safety error
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys

import _lib as lib


FRONTMATTER_RE = re.compile(r"\A(---\s*\n.*?\n---\s*\n)(.*)\Z", re.DOTALL)


def _match_files(root: pathlib.Path, name: str | None, path: str | None, topic: str | None) -> list[lib.MemoryFile]:
    hits: list[lib.MemoryFile] = []
    for mf in lib.walk(root):
        if mf.status == "redacted":
            continue
        if name and mf.name == name:
            hits.append(mf)
            continue
        if path:
            if mf.rel_path == path or str(mf.path).endswith(path):
                hits.append(mf)
                continue
        if topic:
            topic_lc = topic.lower()
            pool = " ".join([
                (mf.name or ""),
                (mf.frontmatter.get("description") or ""),
                " ".join(mf.frontmatter.get("topics") or [] if isinstance(mf.frontmatter.get("topics"), list) else []),
            ]).lower()
            if topic_lc in pool:
                hits.append(mf)
    return hits


def _redact_file(mf: lib.MemoryFile, reason: str) -> str:
    """Return the new content for the file with body blanked and status flipped."""
    today = dt.date.today().isoformat()
    text = mf.path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise RuntimeError(f"{mf.rel_path}: missing frontmatter, cannot safely redact")
    fm_block = m.group(1)

    # Update or insert frontmatter fields. Conservative line-based edit.
    new_lines: list[str] = []
    saw_status = False
    saw_redacted_at = False
    saw_redacted_reason = False
    for line in fm_block.splitlines():
        if line.startswith("status:"):
            new_lines.append("status: redacted")
            saw_status = True
            continue
        if line.startswith("redacted_at:"):
            new_lines.append(f"redacted_at: {today}")
            saw_redacted_at = True
            continue
        if line.startswith("redacted_reason:"):
            new_lines.append(f"redacted_reason: {reason!r}")
            saw_redacted_reason = True
            continue
        new_lines.append(line)
    # Insert before closing '---'
    if not (saw_status and saw_redacted_at and saw_redacted_reason):
        if new_lines and new_lines[-1].strip() == "---":
            tail = new_lines.pop()
            if not saw_status:
                new_lines.append("status: redacted")
            if not saw_redacted_at:
                new_lines.append(f"redacted_at: {today}")
            if not saw_redacted_reason:
                new_lines.append(f"redacted_reason: {reason!r}")
            new_lines.append(tail)

    new_body = (
        "\n# [REDACTED]\n\n"
        f"Content removed on {today}. Reason: {reason}\n"
    )
    return "\n".join(new_lines) + "\n" + new_body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=pathlib.Path, default=lib.DEFAULT_ROOT)
    sel = ap.add_mutually_exclusive_group(required=True)
    sel.add_argument("--name", help="match frontmatter `name:` exactly")
    sel.add_argument("--path", help="match file path (relative to --root)")
    sel.add_argument("--topic", help="match topics / description / name substring")
    ap.add_argument("--apply", action="store_true",
                    help="actually redact; otherwise dry-run only")
    ap.add_argument("--reason", default="",
                    help="reason for redaction (required for --apply)")
    args = ap.parse_args()

    if args.apply and not args.reason.strip():
        print("error: --apply requires --reason '<why>' (audit trail)", file=sys.stderr)
        return 2

    matches = _match_files(args.root, args.name, args.path, args.topic)
    if not matches:
        print("No matching memory files (or all matches already redacted).")
        return 1

    print(f"{'WILL REDACT' if args.apply else 'DRY RUN — would redact'} {len(matches)} file(s):")
    for mf in matches:
        print(f"  - {mf.rel_path}")
        print(f"      name:        {mf.name}")
        print(f"      description: {mf.frontmatter.get('description')}")

    if not args.apply:
        print("\nPass --apply --reason '<why>' to perform the redaction.")
        return 0

    audit_log = args.root / ".audit-redactions.log"
    audit_lines: list[str] = []
    timestamp = dt.datetime.now().isoformat(timespec="seconds")

    try:
        with lib.file_lock(args.root):
            for mf in matches:
                try:
                    new_text = _redact_file(mf, args.reason)
                except RuntimeError as e:
                    print(f"  skip: {e}", file=sys.stderr)
                    continue
                lib.atomic_write(mf.path, new_text)
                audit_lines.append(
                    f"{timestamp}\tredacted\t{mf.rel_path}\treason={args.reason!r}"
                )
                print(f"  redacted: {mf.rel_path}")

            if audit_lines:
                # Append to audit log (not atomic_write because we append)
                with audit_log.open("a", encoding="utf-8") as fp:
                    fp.write("\n".join(audit_lines) + "\n")
                print(f"\nAudit log: {audit_log}")
    except lib.LockTimeout as e:
        print(f"error: {e}", file=sys.stderr)
        print("another tool may be writing to ~/.memory; try again in a moment.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
