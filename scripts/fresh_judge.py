#!/usr/bin/env python3
"""Harness-neutral fresh judge for the unslopify pipeline (step 5).

Runs the judge as a separate headless agent-CLI process that receives ONLY
the rewritten text, never the working notes, so it works the same from any
harness (Claude Code, Codex, Cursor, plain shell).

Usage:
    fresh_judge.py DRAFT.md [--judge-cmd "CMD {prompt}"] [--timeout SECS]

Judge selection, first hit wins:
    1. --judge-cmd argument, or UNSLOPIFY_JUDGE_CMD env var. The string is a
       shell command template; "{prompt}" is replaced with the judge prompt
       (shell-quoted). If no "{prompt}" placeholder, the prompt is piped to
       the command's stdin.
    2. claude        -> claude -p --model claude-opus-5-5 <prompt>
    3. codex         -> codex exec -m gpt-6.1-sol <prompt>
    4. cursor-agent  -> cursor-agent -p --output-format text --mode ask
                        --trust <prompt>  (ask mode is read-only; --trust
                        only clears the headless workspace-trust gate)

Output: a JudgeVerdict JSON object on stdout:
    {"approved": bool, "reasons": [...], "quoted_spans": [...]}

Exit codes:
    0  approved
    1  not approved (spans quoted; loop back to the rewrite step)
    2  no judge CLI available (declare step 5 skipped, do not fake a verdict)
    3  judge ran but returned unusable output
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

JUDGE_INSTRUCTION = """\
You are a fresh-context reviewer. You have no other information about this \
text, its author, or how it was produced. Read the text between the markers \
and quote every span that reads as AI-generated, stock, or evasive, and say \
why. Approve only if nothing needs quoting.

Reply with ONLY a JSON object, no markdown fence, no other prose:
{"approved": true or false,
 "reasons": ["one short reason per problem, or empty if approved"],
 "quoted_spans": ["each offending span quoted exactly, or empty if approved"]}

---BEGIN TEXT---
%s
---END TEXT---
"""


def build_command(template, prompt):
    if "{prompt}" in template:
        return template.replace("{prompt}", shlex.quote(prompt)), None
    return template, prompt


def detect_judge():
    env_cmd = os.environ.get("UNSLOPIFY_JUDGE_CMD")
    if env_cmd:
        return env_cmd, "custom"
    if shutil.which("claude"):
        return "claude -p --model claude-opus-5-5 {prompt}", "claude"
    if shutil.which("codex"):
        return "codex exec -m gpt-6.1-sol {prompt}", "codex"
    if shutil.which("cursor-agent"):
        return ("cursor-agent -p --output-format text --mode ask --trust "
                "{prompt}", "cursor-agent")
    return None, None


def extract_json(text):
    # The CLIs sometimes wrap output in fences or prose; take the first
    # balanced object that parses and has an "approved" key.
    for match in re.finditer(r"\{", text):
        depth = 0
        for i in range(match.start(), len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[match.start(): i + 1]
                    try:
                        obj = json.loads(candidate)
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict) and "approved" in obj:
                        return obj
                    break
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("draft", help="file holding the rewritten text")
    ap.add_argument("--judge-cmd", default=None,
                    help="shell command template; {prompt} is replaced with "
                         "the quoted judge prompt (else prompt goes to stdin)")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()

    try:
        with open(args.draft, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"cannot read draft: {e}", file=sys.stderr)
        return 3
    if not text.strip():
        print("draft is empty", file=sys.stderr)
        return 3

    template, name = (args.judge_cmd, "custom") if args.judge_cmd \
        else detect_judge()
    if not template:
        print("no judge CLI found (tried UNSLOPIFY_JUDGE_CMD, claude, codex, "
              "cursor-agent); declare step 5 skipped", file=sys.stderr)
        return 2

    prompt = JUDGE_INSTRUCTION % text
    cmd, stdin_data = build_command(template, prompt)
    print(f"judge: {name}", file=sys.stderr)
    try:
        proc = subprocess.run(cmd, shell=True, input=stdin_data,
                              capture_output=True, text=True,
                              timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print(f"judge timed out after {args.timeout}s", file=sys.stderr)
        return 3

    verdict = extract_json(proc.stdout)
    if verdict is None:
        print("judge output had no parseable verdict:", file=sys.stderr)
        print(proc.stdout[-2000:] or proc.stderr[-2000:], file=sys.stderr)
        return 3

    verdict.setdefault("reasons", [])
    verdict.setdefault("quoted_spans", [])
    print(json.dumps(verdict, indent=2))
    return 0 if verdict["approved"] else 1


if __name__ == "__main__":
    sys.exit(main())
