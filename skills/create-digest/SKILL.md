---
name: create-digest
description: Upload a finished Markdown research report to the user's Notion "Reading Material" database, so the user can read it on a phone without opening an AI chat. Use when the user says "upload this to notion", "save this to reading material", "put this in my reading list", "read this later", or invokes /create-digest [path].
---

# create-digest

Publish a finished report to Notion. This skill does not research and does not
summarize. It reshapes an existing document and uploads it.

## Target

Notion database **Reading Material** — https://app.notion.com/p/56a902bc74c849808f2da71a83cddd89

Create pages under the **data source**, not the database:

```
data_source_id = 1f72c4ab-f6b1-4ec5-985d-fea7ec3fef8c
```

| Property | Value |
|---|---|
| `Title` | A statement, not a question. Max ~70 characters. |
| `Area` | One of Dev, Finance, Health, Career, Tools, Gaming, Other. |
| `Tags` | Lowercase. Reuse an existing option before you invent one. |
| `Status` | Always `Inbox`. |
| `Depth` | `Brief` under 800 words, `Standard` to 3000, `Deep dive` above. |
| `Read time` | Word count ÷ 200, rounded to 5 minutes. |
| `Source` | `Claude Code`. |

`Added` fills itself. Do not set it.

## Workflow

1. **Get the document.**
   - Path given: read it.
   - No path: use the newest `*.md` this session wrote.
   - Report exists only in the conversation: write it to a `.md` file in the
     working directory first, then continue. The user keeps a local copy.

2. **Read the schema.** Fetch the data source id above. The result lists the
   current `Area` and `Tags` options. Reuse them. Near-duplicate tags make the
   board useless.

3. **Derive the properties.** Do not ask the user. Print one line with your
   choices and continue. The user overrides with flags (`--area Dev
   --tags xaf,blazor --title "..."`) or with one tap in Notion.

4. **Build the body in this order.** Never change the meaning of the source.
   You reorder the frame and add missing sections only.

   1. A callout block: **TL;DR** — 3 to 5 bullets that answer the question.
      Lift it from an existing summary section wherever the source has one,
      even if that section sits at the bottom. Write it yourself if none exists.
   2. `## Why I asked` — one or two sentences of context.
   3. `## Detail` — the source body, structure untouched.
   4. `## Open questions` — what stays unresolved. Omit the heading if nothing does.
   5. `## Sources` — links, last.

   The summary must come first. The user reads on a phone and decides in the
   first screen whether to continue.

5. **Upload.** See below.

6. **Report the page URL.** That is the deliverable.

## Upload mechanics

Before you write any page content, read the Notion Markdown spec:

```
notion-fetch  id: notion://docs/enhanced-markdown-spec
```

Notion-flavored Markdown is not plain Markdown. Tables, callouts and code
blocks have their own syntax. A skipped spec read is the usual cause of a
mangled page. Never put the title in the body — it belongs in `properties`.

Create with `notion-create-pages` (parent: `data_source_id`). Give the page an
emoji `icon` that fits the subject; the list views show it.

**Large reports.** Split any body over roughly 40 000 characters. Create the
page with the TL;DR and `## Why I asked`, then append each following section
with `notion-update-page`, command `insert_content`, position `end`. Set
`allow_async: true` on large calls.

**Re-upload.** Search the data source for the title first. If a page matches,
ask whether to update that page or create a second one. Never create a silent
twin.
