---
name: old-new-review
description: "Build a side-by-side old-vs-new review page: one card per difference by severity, marked screenshots, issue, options and approve/needs-work/comment with export. Use whenever reporting differences between an old and new app version, for 'show me the differences', or /old-new-review."
---

# Old vs new review page

The user decides differences by looking at them, not by reading row ids. Every time differences go to the user for a decision, they get this page. Text alone ("type catalogue 135/121") leaves them asking what a row means.

Files: `scripts/build.py` (spec → cropped, marked images → page), the page itself comes from the ui-sweep skill's `scripts/gen-report.py` (labels, image pairs and the hidden coverage sections are its config options) and is served by its `scripts/serve-report.py`, `references/spec.md` (spec format with an example row).

## Steps

1. **Collect the rows.** One row per difference (one root cause), with severity (BLOCKER, MAJOR, MINOR, COSMETIC), the walk item, roles, page, and the proposal (options, which one you recommend, effort).
2. **Pick the shots.** For each row, find the old and new screenshot of the same page, role and data. Read both images yourself. A row with no visible difference (code, log, database) gets no images; say so in the notes.
3. **Choose crops and marks** in full-screenshot pixels: crop to the area that tells the story (a toolbar strip, a grid header, a form), and draw a red box around the difference on the side where it is (the button that exists, the column order, the counter). Add a `pairs` entry with the whole page when the crop loses context. For a missing element, box it on the side where it exists, and leave the other side unboxed.
4. **Write the spec** next to the evidence (`references/spec.md`). Write `issue` for the user: what they see and why it matters, in two to four sentences, no ids and no file paths. Technical detail goes to `detail` and `cause`, which fold away.
5. **Build with contact sheets:** `python ~/.claude/skills/old-new-review/scripts/build.py <spec.json> --contact`. Read every `contact-*.png` and fix any box that misses its target, then rebuild. Delete the contact sheets afterwards.
6. **Hand it over in the browser pane**, not only as a file: the desktop app's file viewer shows the page but does not run its buttons. The page is `<workDir>/report/<id>-review.html`; register it with the review hub, `python ~/.claude/skills/ui-sweep/scripts/review-hub.py register <workDir> --project <repo or project> --session "<this session's title>"` (starts the hub if needed, prints both URLs; rebuilds need no re-register), and open the printed review URL in the browser pane (`preview_start` with `url`); the user sees every pending review at `http://127.0.0.1:42042/`. SendUserFile it as well for reference. Say in one line: use the browser pane, one card per step, Approve = take the recommended option (or pick another option card first), Needs work + comment = something else; every click is saved, nothing to export.
7. **Record the decisions** from `<workDir>/report/review-decisions.json` (build.py keeps it across rebuilds; a pasted export works too): write each into the spec row's `decision` (and `reply` for a comment you answered) and rebuild so the page shows them. A comment with a condition ("fix if X, else accept") is a question to answer from evidence first: check X, then record the decision that follows, and tell the user what you found.

## Rules

- Same role, same page, same data on both sides; if a shot from another role or page is the best evidence, say so in the caption.
- Screenshots of real systems show names and e-mails. Keep the page local (SendUserFile); do not publish it as an Artifact unless the user asks.
- `file://` previews are refused in the browser pane; serve the page through the review hub (or `serve-report.py` for a one-off), never test-click decisions on the user's live page.
- A row's `open: true` marks a question to the user that is still pending; leave it out otherwise, or every card shows as an open question.
- Every row's `options` has the recommended option at `recOption` (1-based); counts, rights and available actions are never "cosmetic".
