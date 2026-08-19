#!/usr/bin/env python3
"""Claude Code Stop hook: one bounded rewrite request per response.

Reads the completed response from the hook payload, audits it with the
unslopify engine, and checks it against the response phrase bank. On a
fail it blocks the stop once with the findings as the rewrite brief;
stop_hook_active guarantees the second pass is accepted, so there is
never a retry loop. Passing responses are banked, which is the memory:
an agent that starts leaning on the same 8-word phrasing across
responses gets called on it, no matter how clean each response is alone.

Requires the unslopify package on the hook's python3
(`pip install unslopify`). Without it the hook does nothing.
"""

from __future__ import annotations

import hashlib
import json
import sys

MIN_CHARS = 300  # do not nag one-line answers
STAMP_MIN_HITS = 2  # distinct 8-gram overlaps before phrasing counts as a stamp
BANK_PREFIX = "agent-response/"
BANK_KEEP = 200  # newest response rows retained


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("stop_hook_active"):
        return 0
    text = payload.get("last_assistant_message") or ""
    if len(text) < MIN_CHARS:
        return 0

    try:
        from unslopify.audit import audit_text
        from unslopify.phrasebank import commit, load_bank, ngrams
    except ImportError:
        return 0

    report = audit_text(text, source="response", ignore_quoted=True)
    reasons: list[str] = []
    for f in report.findings[:5]:
        reasons.append(f"{f.type_id}: {f.span!r} ({f.why})")
    hard_fail = report.verdict == "fail" and bool(report.fail_reasons)

    # Stamp memory: compare against previously banked responses.
    mine = ngrams(text)
    stamps: list[str] = []
    if mine:
        for row in load_bank():
            doc_id = str(row.get("doc_id") or "")
            if not doc_id.startswith(BANK_PREFIX):
                continue
            hits = sorted(mine & set(row.get("ngrams") or []))
            if len(hits) >= STAMP_MIN_HITS:
                stamps = hits[:2]
                break

    if hard_fail or stamps:
        lines = ["unslopify: rewrite this response in plain language, keeping every fact."]
        if reasons:
            lines.append("Findings:")
            lines.extend(f"- {r}" for r in reasons)
        if stamps:
            lines.append(
                "You are reusing phrasing from earlier responses (stamps): "
                + "; ".join(repr(s) for s in stamps)
                + ". Say it differently, not reshuffled."
            )
        print(json.dumps({"decision": "block", "reason": "\n".join(lines)}))
        return 0

    # Passed: remember its phrasing so future responses cannot lean on it.
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    session = str(payload.get("session_id") or "s")[:8]
    try:
        commit(text, f"{BANK_PREFIX}{session}/{digest}")
        _prune()
    except OSError:
        pass
    return 0


def _prune() -> None:
    """Keep only the newest BANK_KEEP agent-response rows."""
    import os
    import tempfile

    from unslopify.phrasebank import bank_path, load_bank

    rows = load_bank()
    agent = [r for r in rows if str(r.get("doc_id", "")).startswith(BANK_PREFIX)]
    if len(agent) <= BANK_KEEP:
        return
    agent.sort(key=lambda r: str(r.get("committed_at", "")))
    drop = {id(r) for r in agent[: len(agent) - BANK_KEEP]}
    keep = [r for r in rows if id(r) not in drop]
    path = bank_path()
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".bank-", suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        for r in keep:
            fh.write(json.dumps(r, ensure_ascii=True) + "\n")
    os.replace(tmp, path)


if __name__ == "__main__":
    sys.exit(main())
