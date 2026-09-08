---
name: dx-lookup
description: Query DevExpress/XAF/XPO/Blazor API docs via the devexpress-mcp-proxy agent. Returns concise, actionable findings — properties, events, method signatures, supported options. Use when user asks "does DevExpress support X", "what options does DX component Y have", "is there a DX method for Z", "check DX API", or when reviewing/writing XAF/XPO/Blazor code that touches DevExpress components and API validation is needed. Also use proactively when writing or reviewing code that uses DevExpress APIs to verify method fitness before committing.
---

# DevExpress Lookup

Delegates to `devexpress-mcp-proxy` agent — keeps large MCP responses out of main context.

## When it fires

- "does DevExpress support X"
- "what are the options/properties/events for [DX component]"
- "check DX API" / "is there a DX method for Z"
- Writing or reviewing XAF controller / XPO BO / Blazor component code where API correctness matters
- Any question about DevExpress component configuration or capability

## How to use

Spawn a `devexpress-mcp-proxy` agent with `model: haiku` (cheapest model — doc lookup needs no reasoning). Ask it to:
1. Search docs for the topic
2. Fetch relevant content
3. Return only the actionable summary — method signatures, property names, supported values

**Example agent prompt:**
> "Search DevExpress docs for GridControl row editing options. Return: property names, types, and whether inline vs popup editing is supported. Under 200 words."

## What to pass

- Component/class name (e.g. `DxGrid`, `XPObject`, `ObjectSpace`, `XafApplication`)
- Specific capability, property, or method in question
- XAF version context: **v24.2.7**
- Any constraints (Blazor-only, XPO-only, etc.)

## Output

Relay the agent's summary directly. No need to re-explain — the proxy distills verbose MCP output.
