"""Shared helpers for chrono-palace-memory tools.

Lightweight, stdlib-only frontmatter parsing and memory tree walking.
Frontmatter is a restricted subset of YAML — we don't need a full YAML
parser, and avoiding the PyYAML dependency keeps CI / install zero-config.

Supported frontmatter shapes:
  key: scalar
  key: 0.7
  key: null
  key:                # list follows
    - item
    - item
  key: >              # multi-line folded scalar
    line one
    line two

Anything more exotic should be rejected by validate.py.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Iterator


DEFAULT_ROOT = pathlib.Path(os.path.expanduser("~/.memory"))

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


@dataclass
class MemoryFile:
    path: pathlib.Path
    frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""
    parse_errors: list[str] = field(default_factory=list)

    @property
    def rel_path(self) -> str:
        try:
            return str(self.path.relative_to(DEFAULT_ROOT))
        except ValueError:
            return str(self.path)

    @property
    def name(self) -> str | None:
        v = self.frontmatter.get("name")
        return v if isinstance(v, str) else None

    @property
    def type(self) -> str | None:
        v = self.frontmatter.get("type")
        return v if isinstance(v, str) else None

    @property
    def status(self) -> str:
        v = self.frontmatter.get("status")
        return v if isinstance(v, str) else "active"

    @property
    def evidence(self) -> list[str]:
        v = self.frontmatter.get("evidence")
        if isinstance(v, list):
            return [str(x) for x in v]
        return []

    @property
    def expires_at(self) -> date | None:
        v = self.frontmatter.get("expires_at")
        return _coerce_date(v)

    @property
    def created_at(self) -> date | None:
        return _coerce_date(self.frontmatter.get("created_at"))

    @property
    def confidence(self) -> float | None:
        return _coerce_float(self.frontmatter.get("confidence"))

    @property
    def importance(self) -> float | None:
        return _coerce_float(self.frontmatter.get("importance"))


def load(path: pathlib.Path) -> MemoryFile:
    text = path.read_text(encoding="utf-8")
    mf = MemoryFile(path=path)
    m = FRONTMATTER_RE.match(text)
    if not m:
        mf.parse_errors.append("missing frontmatter (file must start with --- ... ---)")
        mf.body = text
        return mf
    raw, body = m.group(1), m.group(2)
    mf.body = body
    try:
        mf.frontmatter = _parse_frontmatter(raw)
    except ValueError as e:
        mf.parse_errors.append(f"frontmatter parse error: {e}")
    return mf


def walk(root: pathlib.Path = DEFAULT_ROOT) -> Iterator[MemoryFile]:
    """Yield MemoryFile for every .md file under root EXCEPT MEMORY.md / README.md
    at root level and files inside index/."""
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        parts = rel.parts
        if parts[0] in {"MEMORY.md", "README.md"} and len(parts) == 1:
            continue
        if parts[0] == "index":
            continue
        yield load(path)


def walk_indexes(root: pathlib.Path = DEFAULT_ROOT) -> Iterator[pathlib.Path]:
    """Yield index files."""
    idx_dir = root / "index"
    if not idx_dir.exists():
        return
    for p in sorted(idx_dir.glob("*.md")):
        yield p


# ---------- internal helpers ----------

def _parse_frontmatter(raw: str) -> dict[str, Any]:
    """Tiny YAML-subset parser tailored to memory frontmatter."""
    out: dict[str, Any] = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if not line[:1].isalpha() and line[:1] != "_":
            raise ValueError(f"unexpected line at {i}: {line!r}")
        if ":" not in line:
            raise ValueError(f"missing ':' at line {i}: {line!r}")
        key, sep, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            # block: list or nested? we only handle list-of-scalars.
            items, consumed = _collect_list(lines, i + 1)
            out[key] = items
            i += 1 + consumed
            continue
        if rest == ">" or rest == "|":
            # folded / literal scalar across following indented lines
            text, consumed = _collect_block_scalar(lines, i + 1, folded=(rest == ">"))
            out[key] = text
            i += 1 + consumed
            continue
        out[key] = _coerce_scalar(rest)
        i += 1
    return out


def _collect_list(lines: list[str], start: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    j = start
    while j < len(lines):
        line = lines[j]
        if not line.strip():
            j += 1
            continue
        stripped = line.lstrip()
        if not stripped.startswith("-"):
            break
        # Indented "- item" continues the list
        item = stripped[1:].strip()
        items.append(_coerce_scalar(item))
        j += 1
    return items, j - start


def _collect_block_scalar(lines: list[str], start: int, folded: bool) -> tuple[str, int]:
    collected: list[str] = []
    j = start
    while j < len(lines):
        line = lines[j]
        if line and not line.startswith((" ", "\t")):
            break
        collected.append(line.strip())
        j += 1
    text = (" " if folded else "\n").join(c for c in collected if c)
    return text, j - start


def _coerce_scalar(text: str) -> Any:
    if text == "" or text.lower() == "null" or text == "~":
        return None
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    # quoted string
    if (len(text) >= 2) and ((text[0] == text[-1] == '"') or (text[0] == text[-1] == "'")):
        return text[1:-1]
    # number
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        pass
    return text


def _coerce_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _coerce_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                continue
    return None


def today() -> date:
    return date.today()


def days_ago(d: date, n: int) -> date:
    return d - timedelta(days=n)


# ---------- tokenization & TF-IDF (stdlib only) ----------

import math
from collections import Counter

# Latin word-like tokens (≥2 chars, letters/digits/dash/underscore)
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]+")
# CJK ranges: keep single CJK characters as standalone tokens
_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


def tokenize(text: str) -> list[str]:
    """Mixed-language tokenizer.

    - Latin: lowercase word boundaries (≥2 chars to drop noise)
    - CJK: each character is its own token (cheap unigram model;
      adequate for keyword recall without external dependencies)
    """
    if not text:
        return []
    out: list[str] = []
    for m in _LATIN_TOKEN_RE.finditer(text):
        out.append(m.group(0).lower())
    for m in _CJK_RE.finditer(text):
        out.append(m.group(0))
    return out


def build_idf(docs: list[list[str]]) -> dict[str, float]:
    """Standard IDF: log((N + 1) / (1 + df)) + 1 (smoothed, never 0)."""
    n = len(docs)
    df: Counter[str] = Counter()
    for tokens in docs:
        for t in set(tokens):
            df[t] += 1
    return {t: math.log((n + 1) / (1 + dft)) + 1.0 for t, dft in df.items()}


def tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Term-frequency-IDF as a sparse dict.

    Unknown tokens (not in idf) get a default weight of 1.0 — so the
    formula degrades gracefully when scoring a query containing brand-new
    terms.
    """
    if not tokens:
        return {}
    tf = Counter(tokens)
    total = sum(tf.values())
    return {t: (c / total) * idf.get(t, 1.0) for t, c in tf.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    num = sum(a[k] * b[k] for k in keys)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


# ---------- Concurrency: global lock + atomic write ----------

import contextlib
import errno
import os
import tempfile
import time

DEFAULT_LOCK_TIMEOUT_SEC = 5.0


class LockTimeout(RuntimeError):
    """Raised when a memory-store lock could not be acquired in time."""


@contextlib.contextmanager
def file_lock(root: pathlib.Path = DEFAULT_ROOT, timeout: float = DEFAULT_LOCK_TIMEOUT_SEC):
    """Process-safe advisory lock on the memory store.

    Uses fcntl.flock on POSIX, msvcrt.locking on Windows. The lock file
    `<root>/.lock` is created if needed. Multiple readers don't strictly
    need this lock — but every WRITER must take it for the duration of
    its read-modify-write so concurrent agents don't clobber each other.

    Usage:
        with file_lock(root):
            ... read file, transform, atomic_write ...

    Raises LockTimeout if the lock can't be acquired within `timeout`.
    """
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".lock"
    # Open in append mode so we don't truncate, and ensure it exists.
    fp = lock_path.open("a+")
    try:
        deadline = time.monotonic() + timeout
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise LockTimeout(f"could not lock {lock_path} within {timeout}s")
                    time.sleep(0.1)
            try:
                yield
            finally:
                try:
                    msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as e:
                    if e.errno not in (errno.EAGAIN, errno.EACCES):
                        raise
                    if time.monotonic() >= deadline:
                        raise LockTimeout(f"could not lock {lock_path} within {timeout}s")
                    time.sleep(0.1)
            try:
                yield
            finally:
                try:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
    finally:
        fp.close()


def atomic_write(path: pathlib.Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to path atomically: write to .tmp, fsync, rename.

    Guarantees that readers never see a half-written file. Combine with
    file_lock() for multi-process safety; atomic_write alone protects
    against crashes mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use a tempfile in the same directory so rename is atomic across same FS
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fp:
            fp.write(content)
            fp.flush()
            try:
                os.fsync(fp.fileno())
            except OSError:
                pass  # fsync not supported on some filesystems; rename still safe
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
