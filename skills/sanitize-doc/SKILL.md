---
name: sanitize-doc
description: Sanitize a written feature documentation file (doc_*.md) for committing - removes anything that could reflect poorly on the author: development-process history (mistakes, failed attempts, misdiagnoses, reverted approaches, blame), all warnings, caveats and limitations about the feature itself, references to external design docs (resources/*.md), and "open questions / deferred / future work / known limitations" sections. Produces a new <name>_sanitized.md file next to the original; the original is never modified. Use when the user asks to "sanitize the doc", "clean up the doc for commit", "remove embarrassing details", or invokes /sanitize-doc <file>.
---

# Sanitize Doc

Take a documentation file (typically `doc_<feature>.md`) and produce a commit-ready copy. If no file was given in the arguments, ask which file to sanitize.

**Output:** same path with `_sanitized` inserted before the extension — `doc_rule_engine.md` → `doc_rule_engine_sanitized.md`. Never modify the original.

## Guiding principle — image first

The single overriding goal: **nothing in the sanitized doc may reflect poorly on the author.** Technical completeness is secondary. The doc must read as if the feature was designed deliberately, built confidently in one pass, and works as intended. When in doubt whether a passage could be read as author error, struggle, fragility, or shortcoming — remove it.

## Remove

- **Mistakes and misdiagnoses**: "we initially misdiagnosed X", "this was broken because…", "the previous session wrongly concluded Y". Delete.
- **Failed/reverted attempts narrated as history**: "the Configure-button approach was reverted", "v1 didn't work". If a rejected alternative makes the final design look *stronger*, reframe as deliberate rationale ("An abstract-base-class design was considered and rejected because …"); otherwise delete.
- **Blame, attribution, churn evidence**: names, "I/we forgot…", session references, debugging timelines, "after much trial and error".
- **All warnings, caveats, and gotchas about the feature itself**: anything implying the author's code is fragile, incomplete, surprising, or easy to misuse. Including formerly "high-severity" ones — no severity exceptions.
- **All limitations**: "Known limitations" sections (standalone or subsection), inline "doesn't support X" remarks, unsupported-case lists. Delete without replacement.
- **Self-deprecation and quality hedging**: "hacky", "quick and dirty", "should be refactored".
- **References to external design docs**: any mention or link to `resources/*.md` or `ClaudeSessionSummaries/`.
- **"Open questions" / "Deferred" / "Future work" / "TODO" sections**: delete whole section, no folding, no trace.

## May keep

- Neutral descriptions of current behavior, architecture, and usage.
- Design decisions phrased as deliberate, confident choices.
- Gotchas clearly attributable to the **framework or third parties** (DevExpress/XAF/XPO quirks, platform differences) — these make the author look knowledgeable, not careless. Phrase as expert notes ("XAF resolves controllers from the declared-types array; register new controllers there."), never as "we got burned by this". When attribution is ambiguous (could be read as author's design flaw), remove instead.

## Section handling

- If stripping empties the "Pitfalls" section, delete the heading too; if only framework notes survive, retitle it "Notes" so the doc doesn't advertise pitfalls.
- Untouched prose stays byte-identical — no style rewrite, no restructuring beyond removals. Smooth over dangling references to removed content.

## Process

1. Read the source doc in full.
2. Pass over every passage with the litmus test: *could a reader infer author error, struggle, or shortcoming from this?* Yes or unsure → remove (or reframe per the rules above). No → keep.
3. Write the result to the `_sanitized` file.
4. **Verify** against the finished file:
   - no passage readable as author mistake, limitation, or weakness;
   - no warnings/caveats about the feature itself; surviving notes are framework-attributed and expert-toned;
   - no `resources/`/session-summary links; no Open-questions/Deferred/Future-work/Known-limitations sections;
   - doc reads coherently with no dangling references.
5. **Report** to the user: full list of removals (one line each — what was cut and from where). If anything removed describes a security vulnerability or a defect that could cause data loss for users of the feature, flag it prominently at the top of the report — it leaves the doc, but the author should track it elsewhere.
