# Document structure

The document has exactly these four top-level sections, in this order.

## 1. Overview

- What the feature does, in 2–4 paragraphs, and the problem it solves.
- How it works at a high level (the conceptual model a developer needs before touching code).
- Where it lives in the repo (key projects/folders).

## 2. Architecture and implementation

- The main components and how they interact. Include a simple diagram (Mermaid) if the flow is non-trivial.
- Key classes, interfaces, attributes, and extension points, each with file path and a one-line responsibility.
- Execution flow: what happens from trigger to result, step by step.
- Design decisions and their rationale (from the session summaries): why this approach, what was considered and rejected, known trade-offs.

## 3. Usage

- Minimal working example: the smallest complete setup needed to use the feature, with real code from or consistent with the codebase.
- Requirements and conventions that are easy to miss. Be exhaustive here — e.g. "to use the Rule Engine with a Business Object, the BO must expose a callable method decorated with the `[...]` attribute/tag." List every such requirement: required attributes, naming conventions, registration steps, configuration entries, base classes or interfaces.
- Common scenarios as short how-to recipes.

## 4. Pitfalls and things to look out for

- Gotchas when *using* the feature (wrong/missing attribute, lifecycle issues, ordering requirements, silent failures and what they look like).
- Gotchas when *modifying or extending* the feature (fragile areas, hidden coupling, things the implementers warned about in the session summaries).
- Known limitations and unsupported cases.
- Troubleshooting: the most likely failure symptoms and their causes.

# DevExpress / XAF specifics

This codebase uses DevExpress (XAF/XPO). Keep this in mind:

- Use correct DevExpress terminology (Business Object, Object Space, Controller, Action, Application Model / Model.xafml, criteria language, List/Detail View) so the documentation reads naturally to XAF developers.
- Explicitly call out any **non-trivial DevExpress mechanisms** the feature relies on, since these are common sources of confusion. Examples: custom Controllers or Actions, Application Model extensions (`IModelExtender`), non-persistent objects, custom ViewItems/PropertyEditors/ListEditors, ObjectSpace events and object lifecycle (`OnSaving`, `IObjectSpace.Commit`), criteria/expression evaluation, the Security System, domain components, or platform-specific (Win/Blazor) behavior differences.
- For each such mechanism, briefly explain how it is used *in this feature* and link to the relevant file — assume the reader knows XAF basics but not the advanced corner being used.
- Note anything that behaves differently between platforms (WinForms vs. Blazor), if applicable.
