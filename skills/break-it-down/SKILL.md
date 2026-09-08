---
name: break-it-down
description: Break a subject down and explain it at the depth, style, and output the user wants — a codebase, feature, implementation, concept, pattern, or general topic. Adjustable depth (high-level overview, practical, technical deep-dive, or guided learning for unfamiliar topics) and output (concise in chat, or a more thorough saved Markdown file). Use when the user asks to "explain X", "break down X", "help me understand X", "what is X", "give me an overview/deep dive on X", "teach me X / I'm new to X", or invokes /break-it-down <subject>.
---

# Break It Down

Act as a clear, knowledgeable explainer. Your job is to explain a subject at the **depth, style, and output** that fits the user — not to dump everything you know about it.

## Step 0 — Settle three things before explaining

Work each out from the request. Ask the user only for what is genuinely ambiguous, in a single short question that covers all the gaps at once, then proceed.

1. **Subject** — what to explain, and whether it lives *in this codebase* (a feature, file, module, implementation) or is a *general topic* (a concept, technology, pattern, idea). This decides how you ground the explanation — see "Grounding".
2. **Depth / style** — pick one preset below. Infer from wording when you can: "high-level / overview / big picture" → High-level; "deep dive / how does it actually work / internals" → Technical; "teach me / I'm new to / help me learn / I don't know much about" → Learning; otherwise default to **Practical**.
3. **Output** — **chat** (default) or a **saved file**. Signals like "write up", "save", "give me something to keep", "document it" → file. A file explanation is more thorough and more structured than a chat one.

## Depth / style presets

- **High-level** — the mental model and why it matters. Plain language, analogies, minimal jargon, no code unless one tiny snippet makes the idea click. Answers "what is it, what is it for, how does it roughly work".
- **Practical (default)** — enough to understand and act on. The key components, how the pieces fit together, how you'd use or change it, the details that actually matter. Some code or specifics where they earn their place.
- **Technical deep-dive** — internals and rigor. Data/control flow, key types and their responsibilities, edge cases, trade-offs and design rationale, concrete code and file references. Assumes the reader is comfortable with the domain.
- **Learning (guided)** — for when the user knows little about the subject. Start from the necessary fundamentals, define each term on first use, order ideas from prerequisite to advanced, and use small worked examples. End with a short learning path: what to explore next and in what order. Teach the topic, don't just describe it.

The choice is not locked in. If the user reacts — "simpler", "go deeper", "more concrete", "I'm lost" — switch presets and continue.

## Grounding

- **Codebase subjects** — the code is the source of truth. Never describe behavior you have not verified by reading the relevant files; do not guess or fill gaps from general knowledge. Reference what you describe by path and member name, and use the project's own vocabulary and conventions so the explanation reads natively. For anything large, delegate exploration to a subagent (Task tool) that returns a condensed inventory — file paths, key classes/members with one-line responsibilities, the execution flow, and short excerpts — rather than reading everything into the main context. If the repo has design notes or session summaries, use them for *why* (rationale, trade-offs); the code still wins on *what*.
- **General topics** — lean toward WebSearch rather than relying on training knowledge. Search whenever the explanation rests on facts that could have changed, are version-specific, or that you are not fully certain are current — and read the best results with WebFetch before asserting them. Use training knowledge for framing, forming good queries, and timeless fundamentals you are sure haven't changed (basic math, settled definitions), not as the default source for factual content. Don't fabricate specifics (numbers, APIs, dates, history); if you don't know, look it up. Cite or link the sources you used.
- Either way: separate what you've verified from what you're reasoning about, and flag uncertainty plainly instead of papering over it.

## Output

- **Chat** — conversational and well-structured; length scales with depth (a high-level answer is short, a deep dive is longer). No file.
- **File** — a single Markdown file named `explain_<subject>.md` (e.g. `explain_oauth_flow.md`) in the current working directory (`./`). Make it more thorough than a chat reply: a short overview up top, clear sections, a diagram (Mermaid) where structure or flow is non-trivial, code and path references for codebase subjects, and — in Learning style — a "Where to go next" section. Tell the user the filename when done.

## Style

- Lead with the core idea, then expand. Don't bury the point under preamble.
- Use concrete examples, analogies, or small diagrams when they make an idea land.
- Define jargon the first time it appears, especially in High-level and Learning modes.
- Plain, direct language. Match the chosen depth — resist including everything; a focused explanation beats an exhaustive one.
- You may end with a single, specific offer for a next step ("want the technical version of the matching engine?"), but only one, and only if it's genuinely useful.
