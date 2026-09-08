---
name: prm-stateworkflow
description: Work with PRM's custom StateWorkFlow state-machine engine — controller/BO registration gotchas, catalogue-BO state modeling, gate vs validation criteria placement, unseeded transitions on clean deploys, and live-testing pitfalls. Use when adding a controller or business object to the StateWorkFlow module, wiring transitions or gates, debugging why a state-change button is greyed or missing, or driving/testing state transitions in the running Blazor app.
---

# PRM StateWorkFlow engine

The custom `StateWorkFlow` module (`Source/Prod/StateWorkFlow`) drives Claim/Notice/Checklist/Todo state via `XpoStateMachine` + `XpoTransition` rows. Line numbers are point-in-time — verify against current source. Run any SQL via the `sql-lookup` skill.

## Registration is hardcoded — check this FIRST

`StateWorkFlowModule.GetDeclaredControllerTypes()` overrides the base with an **explicit hardcoded array** and does NOT call `base`, so XAF does not auto-scan the assembly. A new `ViewController` anywhere in StateWorkFlow silently never instantiates, never activates, produces zero logs — even though the module is registered. **Add `typeof(YourController)` to that array.** If a controller "doesn't fire / no logs," check this before chasing XAF lifecycle/popup theories.

Same for BOs: `GetDeclaredExportedTypes()` is also overridden without `base` (returns hardcoded `{XpoStateMachine}`). New BOs must be added via `AdditionalExportedTypes.Add(...)` there. (Contrast: `ClaimModule` does NOT override this → own-assembly BOs auto-collect; its `AdditionalExportedTypes` block is redundant.)

## States are catalogue BOs

States are catalogue BOs, not enums (`ClaimState`, `TodoState`, …). The engine writes the state via `StateMachineLogic.ProcessTransition → stateMemberInfo.SetValue(...)`; the tell that a property is engine-controlled is **`[ModelDefault(AllowEdit, False)]`**. A machine's `XpoStateMachine`/transition definition may live **only in the DB** (admin-created via Model Editor), not in source — absence of a `Source/Workflows/*.xml` export does NOT mean "no state machine." Only Claim & Notice are exported. See `prm-business-objects` for the BO side.

## Gate vs validation criteria

A transition's **`TargetObjectCriteria`** (the gate that enables/greys the button) is evaluated via `ObjectSpace.IsObjectFitForCriteria(...)`; a **null** result greys the button. `IsObjectFitForCriteria` reliably evaluates simple navigation/property criteria but returns **null** for a compound that mixes persistent navigation (`…SystemUser.Oid = CurrentUserId()`) with a collection-backed/`[NonPersistent]`/aggregate member — so an `AND` of the two greys the button even when each clause alone works.

**Rule of thumb:**
- Put the **role/identity gate** (simple nav) in `TargetObjectCriteria`.
- Put **preconditions** (aggregate/NonPersistent, e.g. "all required docs present") in **`ValidationCriteria`** — enforced on execute via a `RuleCriteria` that raises a proper error instead of silently greying. Back a precondition with a `[NonPersistent]` computed bool getter and test `= True`, rather than a nested-aggregate criteria.
- Caveat: `Transition.ValidationCriteria` is `[Browsable(false)]` → absent from the model/editor. Set it via SQL on the `XpoTransition` row or in code; the engine enforces it regardless.

## Transitions are seeded NOWHERE

`Create*StateMachine()` in `PRM.Claim/DatabaseUpdate/Updater.Logic.cs` seeds the machine, its state nodes, and StartState — but **not transitions** (the code says the admin wires them in the UI). The only `XpoTransition` creation in the solution is runtime BO logic + tests. So on a **clean prod deploy**, catalogue + machine + rule seed fine, but the workflow is **non-functional** (zero transitions → no state-change buttons; only programmatic auto-moves work). Transitions are wiped by a DB reset and aren't documented in `resources/`. Robust fix = add a `Create*Transitions()` seeder in code; needs ground-truth topology first (a pre-reset dev backup, or re-wire in UI then read back).

## Live-testing gotchas (running Blazor app)

1. **Transitions on a DetailView do NOT auto-commit.** `StateMachineController.ExecuteTransition` sets the state marker + runs TransitionToDos **in memory**, then `View.Refresh()`. It commits only if the transition has `SaveAndCloseView` or the view is a ListView with AutoCommit. On a DetailView you must click **Speichern** after each transition or nothing persists — a DB read before Save shows the OLD state (looks like a rollback; it's pending).
2. **A direct SQL reset is ignored while the running app holds the object in-memory.** A later Save flushes the STALE cached copy, overwriting the SQL reset (and can re-apply side-effects from an earlier walk). To reset reliably: restart the app, or navigate fully away + back to force a DB reload, THEN SQL-reset.
