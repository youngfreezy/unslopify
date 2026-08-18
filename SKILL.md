---
name: unslopify
description: >
  Remove AI-writing patterns from text. Two modes. Always-on: apply the
  writing rules to every reply in the conversation. Rewrite: audit a draft
  with the unslopify CLI, rewrite it against the named findings, check
  phrasing uniqueness, then verify with a fresh-context judge and loop
  until the audit passes. Use when the user says unslopify, de-slop,
  humanize, "make this sound less like AI", or asks for always-on natural
  writing.
license: MIT
compatibility: any-agent
---

# unslopify

Text is clean when a careful reader cannot tell a model touched it. That
takes two things: removing the named failure patterns, and not replacing
them with a new house style. The pipeline below does both.

Run `unslopify types` for the rubric: four categories (formula, substance,
wording, structure), each with named types, one-line definitions, and
examples. The CLI is installed with `pip install unslopify` or run from a
checkout with `python -m unslopify.cli`.

## Mode 1: always-on

When the user asks for unslopify on every reply, follow the writing rules
below in everything you produce for the rest of the session: chat replies,
documents, commit messages, comments.

- Start where the answer starts. No scene-setting, no restating the
  question, no announcing what you are about to say.
- Concrete subjects and verbs. Name what changed, why, and the evidence.
  A number, a source, or an observable result beats an adjective.
- Prefer is, are, and has over ornate stand-in verbs (the serves-as and
  stands-as family).
- No manufactured rhythm: no not-just-X-but-Y frames, no slogan
  fragments, no triads for cadence, no colon-and-semicolon drumbeats,
  no em dashes.
- No AI vocabulary when a plain word works. If the word would look odd
  in a text message to a colleague, pick the plain one.
- Vary sentence length. Uniform sentences read as generated even when
  every word is clean.
- End on the last real point. No summary paragraph that re-says the
  piece, no trailing offers.
- Neutral register is correct for code, config, and reference material.
  Do not inject personality there.

These rules are contextual signals, not banned tokens. One isolated
instance is fine; conspicuous, repeated, or unearned patterns are not.

## Mode 2: rewrite a draft

Input: pasted text or a file path. Output: the clean text plus a short
log of what changed. Work in a scratch directory; never edit the user's
file in place unless asked.

### Pipeline

Every gate either passes or sends you back to the rewrite step. Do not
skip a gate because the draft "looks clean".

1. **Audit.** Save the draft as `DRAFT.md` and run:

   ```
   unslopify DRAFT.md --brief
   ```

   The brief names each finding with its line, span, problem, and
   direction. Mechanical problems (dashes, curly quotes, long sentences,
   repeated phrases) are listed with the findings.

2. **Rewrite.** Fix every finding by rewriting, not deleting. The
   rewrite covers everything the original covers: same claims, same
   qualifications, same paragraph count unless structure itself was the
   finding. If the user supplied a writing sample, build a voice profile
   first (`unslopify.voice.profile_from_sample`) and aim the rewrite at
   those numbers.

   Plain-language rules for the rewrite itself:

   - One main point per sentence, with an active subject and verb.
   - Standard capitalization and spelling. Never inject informality,
     slang, or errors to sound human; that is its own tell.
   - Quoted material and citations are evidence. Preserve them exactly.
   - Say the direct thing instead of a template. If you notice the same
     sentence shape appearing across your rewrites, that shape is a
     house formula and it dies here.
   - Name a failure type in your notes only when it clarifies the edit.
     Do not tag types to satisfy a checklist.
   - The rewrite should not be longer than the original. Padding added
     to satisfy a gate is a new finding, not a fix.

   Record every edit you make as a RewriteEvent (line, rule or type id,
   before, after). `mechanical_rewrite` already logs its own events;
   yours join the same list, so the final report shows exactly what
   changed and why.

3. **Judgment pass.** The CLI cannot see everything. Reread the rewrite
   for the judgment-only types: meaning loss (a sentence compressed until
   the point is gone), unexplained jargon the regexes missed, synthetic
   balance, and uniform sentence rhythm. Fix what you find.

4. **Uniqueness.** Check the draft against the user's phrase bank:

   ```
   unslopify DRAFT.md --bank --id <doc-id>
   ```

   Any 8-word run shared with a previously banked document fails, and so
   does any 4-word phrase repeated inside this draft. Rephrase the
   flagged spans in different words, not reshuffled ones.

5. **Fresh judge.** Spawn a subagent with no access to your working
   notes. Give it only the rewritten text and this instruction: "Quote
   every span that reads as AI-generated, stock, or evasive, and say
   why. Approve only if nothing needs quoting." Return its verdict as a
   JudgeVerdict (approved, reasons, quoted_spans). If it quotes anything,
   go back to step 2 with its quotes as new findings.

6. **Final gate.** `unslopify DRAFT.md` must print PASS. Then, if the
   user keeps a phrase bank, commit the finished document so future
   drafts cannot reuse its phrasing:

   ```
   unslopify commit DRAFT.md --id <doc-id>
   ```

7. **Deliver.** Return the clean text, then a log: findings fixed by
   type name, judge verdict, and the final PASS line. Keep the log to a
   few lines; the text is the deliverable.

### What not to do

- Do not delete content to make a finding disappear. A missing claim is
  a worse failure than a flagged one.
- Do not swap one stock phrase for another stock phrase. The uniqueness
  gate exists because rewrites drift toward new stamps.
- Do not normalize the author's voice away. Contractions, first person,
  short fragments, and mild informality are the author's, not yours to
  remove.
- Do not run the judge in your own context. A judge that watched you
  rewrite will approve what you approved.
