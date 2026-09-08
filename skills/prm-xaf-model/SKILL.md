---
name: prm-xaf-model
description: Understand and troubleshoot the XAF Application Model in PRM — member-visibility attributes, enum localization, and DB-backed runtime model diffs that override source .xafml. Use when a BO member won't appear in the Model Editor, enum captions show in the wrong language, or the running UI doesn't match the source model / a column stays hidden despite correct .xafml.
---

# PRM XAF Application Model

Where model settings come from, and why the running UI can differ from source. Line numbers are point-in-time — verify against current source. Run any SQL read-only via the `sql-lookup` skill.

## Model layer order (higher wins)

```
code / attributes  →  .xafml (Model Editor)  →  shared DB diff (UserId empty)  →  per-user DB diff
```

So the source `.xafml` can be correct yet the UI differs because a **DB diff overrides it**. Rule out the DB layer before editing source when "the UI is wrong but the xafml looks right."

## Member visibility attributes

- **`[Browsable(false)]`** removes a member from the Application Model **entirely** → it cannot be added to any view in the Model Editor (absent, not just hidden). Example: `Notice.Todos`/`Claim.Todos` are `[Browsable(false)]`, so a hand-configured tab on them can't be built until the attribute changes.
- To keep a member out of auto-generated layouts **but still placeable** in the ME, use **`[VisibleInDetailView(false)]`** / `[VisibleInListView(false)]` instead.

## Enum German captions

Per-enum-member captions come from a **Localization xafml group**, not attributes:
```xml
<!-- Model.DesignedDiffs.Localization.de.xafml (PRM.Claim), inside the Enums group -->
<LocalizationGroup Name="PRM.Claim.Enums.ClaimAttachmentStateEnum">
  <LocalizationItem Name="Draft" Value="Entwurf" />
</LocalizationGroup>
```
The enum types in this repo are plain (no `[XafDisplayName]`/`[Display]` on members). `[XafDisplayName("…")]` sets the **property** caption (works directly since the app is German); the localization xafml handles the **member** dropdown labels. Localization is scoped per group, so the same member name can carry different values in two groups with no conflict. Hand-editing this localization file is **safe** (stable key-value) — unlike the layout `Model.DesignedDiffs.xafml`, which is Model-Editor-only.

## Runtime model diffs live in the DB

DB tables (in `PRM_Blazor`):
- **`ModelDifference`** (parent: `Oid`, `UserId`, `ContextId`, `Version`, `GCRecord`)
- **`ModelDifferenceAspect`** (child: `Oid`, `Name`, **`Xml`** = the diff fragment, `Owner` FK → parent)

`ContextId` separates apps: **"Blazor"** vs **"Win"** are different stores. `UserId` empty = shared/all-users layer. Registered in `PRM.Blazor.Server/BlazorModule.cs` via `new ModelDifferenceDbStore(app, typeof(ModelDifference), false, "Blazor")`.

**Inspect (read-only):**
```sql
SELECT ... FROM ModelDifferenceAspect WHERE CAST(Xml AS NVARCHAR(MAX)) LIKE '%SomeViewId%'
```
**Edit (scoped):**
```sql
UPDATE ModelDifferenceAspect SET Xml = REPLACE(CAST(Xml AS NVARCHAR(MAX)), '<exact node/>', '') WHERE Oid = '...'
```
**STOP the app first** — the running app re-flushes its in-memory model to the DB on shutdown and clobbers the edit. Then start + verify.

**When the Blazor UI can't fix a hidden column itself:** the grid may be `HideToolbar="True"` (no column chooser); `PRM.Module/Controllers/ResetViewSettingsController.cs` disables the ResetViewSettings action app-wide; and Blazor exposes no `ModelDifference` admin list (only the `.Win` designer does). In that case the DB edit above is the route.
