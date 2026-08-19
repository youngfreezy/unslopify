"""Cross-document phrase bank.

A writer (or an agent writing on their behalf) develops stock phrases:
the same 8-word run showing up in every document. The bank remembers
n-grams from committed documents and the audit flags overlap, so each new
piece has to say things in its own words.

Storage: JSONL at $UNSLOPIFY_HOME/phrase_bank.jsonl (default ~/.unslopify).
One row per committed document id; re-committing an id replaces its row.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CROSS_NGRAM_N = 8
CROSS_HIT_MIN = 1  # any 8-word overlap with another document fails

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_QUOTED_RE = re.compile(r'"[^"\n]*"')


def bank_dir() -> Path:
    root = os.environ.get("UNSLOPIFY_HOME")
    return Path(root) if root else Path.home() / ".unslopify"


def bank_path() -> Path:
    return bank_dir() / "phrase_bank.jsonl"


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall(text.lower()))


def ngrams(text: str, n: int = CROSS_NGRAM_N) -> set[str]:
    """Commentary n-grams. Quoted spans are masked first: two documents
    that faithfully preserve the same quotation are not copying each
    other, and the skill requires quotes to be preserved exactly."""
    words = _normalize(_QUOTED_RE.sub(" ", text)).split()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def load_bank() -> list[dict]:
    path = bank_path()
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def cross_check(text: str, doc_id: str | None = None) -> list[str]:
    """Return one failure message per banked doc this text overlaps."""
    mine = ngrams(text)
    if not mine:
        return []
    fails: list[str] = []
    for row in load_bank():
        other = str(row.get("doc_id") or "")
        if doc_id and other == doc_id:
            continue
        hits = sorted(mine & set(row.get("ngrams") or []))
        if len(hits) >= CROSS_HIT_MIN:
            fails.append(
                f"{len(hits)} {CROSS_NGRAM_N}-word phrase(s) overlap banked doc "
                f"{other!r}; e.g. {hits[:3]!r}"
            )
    return fails


def commit(text: str, doc_id: str) -> Path:
    """Bank a document's n-grams under doc_id, replacing any prior row."""
    row = {
        "doc_id": doc_id,
        "committed_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "ngrams": sorted(ngrams(text)),
    }
    existing = [r for r in load_bank() if str(r.get("doc_id") or "") != doc_id]
    path = bank_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # atomic replace: a crash mid-write must not eat the bank
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".bank-", suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for r in existing:
                fh.write(json.dumps(r, ensure_ascii=True) + "\n")
            fh.write(json.dumps(row, ensure_ascii=True) + "\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
