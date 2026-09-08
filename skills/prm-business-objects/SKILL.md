---
name: prm-business-objects
description: Conventions and patterns for authoring PRM XPO business objects and associations — single-file layout (no partials), cross-module associations, [Aggregated] disambiguation, AssemblyVersion migration bumps, catalogue-BO state modeling, and net8 test-project setup. Use when creating or modifying a PRM business object, adding an association (especially across the PRM.Claim ↔ PRM.Module assembly boundary), or writing unit tests for net8 PRM.Claim/module code.
---

# PRM business object & association authoring

XPO business objects (`BasePersistentObject` → `DevExpress.Persistent.BaseImpl.BaseObject`). Line numbers are point-in-time — verify against current source.

## No partial files (overrides CLAUDE.md)

Put **all** BO code — properties, associations, `AfterConstruction`, `OnChanged`, audit/change-history members — in the single main `.cs` file. Do **not** create `.Logic.cs` **or** `.ITrailAudit.cs` partials. Existing `.ITrailAudit.cs` files in the repo are legacy, not a pattern to copy. (Project CLAUDE.md still documents the `.ITrailAudit.cs` convention — this rule supersedes it for new code.)

## Cross-assembly associations

C# `partial class` is compile-time and single-assembly. You **cannot** extend a `PRM.Module` BO (e.g. `ProjectGroup`, `Company`) with a `partial class` declared in `PRM.Claim` — the dependency is one-way (`PRM.Claim → PRM.Module`), and a back-collection typed on the Claim side would create a circular reference. Reject any plan that proposes it.

Valid alternatives:
1. **One-sided XPO association** — declare `[Association]` only on the Claim side; skip the back-collection property on the Module BO.
2. **Two-sided via `ModuleHelper`** (the sanctioned way to get a back-collection on the lower BO) — register both ends at runtime in the higher module's `CustomizeTypesInfoDictionary`:
   ```csharp
   moduleHelper.RegisterAggregatedCollectionMember<ProjectGroup, Checklist>("Checklists", "Checklists", "ProjectGroup_Checklists");
   moduleHelper.RegisterReferenceMember<Checklist, ProjectGroup>("Project", "Project", "ProjectGroup_Checklists");
   ```
   No code member on the lower BO, no partial. Already used for `Claim⇄MailItem`, `Notice⇄MailItem`, `ClaimMasterType⇄ProjectGroup`. Tradeoff: the injected member isn't visible in the lower BO's `.cs` source — it lives in `Module.cs`.
3. Move the BO to `PRM.Module` (only if it architecturally belongs there).

## `[Aggregated]` must be fully-qualified

In BOs importing both `DevExpress.Xpo` and `DevExpress.ExpressApp.DC`, write `[DevExpress.Xpo.Aggregated]` on the `XPCollection` (cascade-delete child collection). Bare `[Aggregated]` is `CS0104` ambiguous. Do **not** "clean up" the fully-qualified form to bare — it's deliberate. Only bare it when `DevExpress.ExpressApp.DC` is not imported in that file.

## Catalogue-BO state pattern

A state-machine **state** in PRM is a **catalogue BO**, not a C# enum: `ClaimState`, `NoticeState`, `InstructionState`, `TodoState`, etc. extend `BasePersistentObject, IActive` with `Code`/`ShortName`/`Localization→Name`/`Active`/`PercentFinished` (+ optional `IsDefault`/behaviour columns). Seeded via `Create*State(...)` helpers in `PRM.Claim/DatabaseUpdate/Updater.Logic.cs`. The tell that a `State` property is engine-controlled is **`[ModelDefault(AllowEdit, False)]`**. See the `prm-stateworkflow` skill for the engine side.

## AssemblyVersion bump triggers migration

When adding/changing a persistent BO member, bump `AssemblyVersion` in the affected module `.csproj` to trigger XPO schema migration. Format `2.<YY>.<MMdd>.<revision>` (e.g. `2.26.0715.0`); increment the last digit for multiple same-day migrations. `PRM.Module.csproj` for `PRM.Module/` changes, `PRM.Claim.csproj` for `PRM.Claim/`. Version-gated updates live in `Updater.cs`.

## net8 test projects

`Source/Test/PRM.Claim.Test` is legacy **non-SDK net472** (referenced only by `PRM.sln`) and **cannot** reference the net8 `PRM.Claim`. For new tests, create a fresh **SDK-style net8** project mirroring `Source/Test/StateWorkFlow.Test/StateWorkFlow.Test.csproj` (MSTest 3.2.0, `Microsoft.NET.Test.Sdk`, DevExpress 25.2.5, `Microsoft.Extensions.Logging.Abstractions` **8.0.3** to avoid the NU1605 Azure.Identity downgrade). Register BOs via `XafTypesInfo.Instance.RegisterEntity` + `new XPObjectSpaceProvider(new MemoryDataStoreProvider())`.
