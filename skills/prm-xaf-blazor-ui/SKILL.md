---
name: prm-xaf-blazor-ui
description: Customize XAF Blazor grids, ListView/DetailView actions, and row rendering in the PRM codebase — where each setting must live and which APIs silently no-op. Use when adding per-row or header actions, enabling inline/batch grid edit, hiding grid chrome (search/export/pager/selection), making a grid row expandable or a drop target, wiring the SimpleListEditor add/delete buttons, or when a grid/action customization compiles but does nothing at runtime.
---

# PRM XAF Blazor UI customization

Hard-won levers for the PRM Blazor host (`Source/Prod/PRM.Blazor.Server`, DevExpress XAF 25.2, `DxGridListEditor`). Line numbers are point-in-time — verify against current source. Delegate DevExpress API checks to the `dx-lookup` skill.

## Where a setting must live (model layering)

- **Platform-specific model props** (`InlineEditMode="Batch"/"Inline"`, `ShowAllRows`) only take effect in the **Blazor app model** `Source/Prod/PRM.Blazor.Server/Model.xafml`. Setting them in an agnostic module model (`PRM.Claim`/`PRM.Module/Model.DesignedDiffs.xafml`) is **silently ignored** — the view just opens its DetailView.
- **Target the node you actually click.** For a nested collection (Checklist → Positionen) that's `<Owner>_<Collection>_ListView` (e.g. `Checklist_Positions_ListView`), NOT the standalone `<Type>_ListView`. Set `AllowEdit="True"` too. `DataAccessMode=Server` blocks batch; nested collection views default to Client (OK).

## Actions: placement by category

Blazor host template `Templates/CustomMainFormTemplate.cs` decides where each `PredefinedCategory` renders:
- **`RecordEdit`** → toolbar **+** row command column **+** context menu.
- **`ListView`** → row command column **only**.
- **`QuickAccess`** → header, beside the account/settings cluster (use a `SimpleAction` in a `WindowController` with `TargetWindowType = WindowType.Main`; no template edit, no Notifications module). Precedent: `PersonalTodoHeaderController`.
- `HiddenActions` on a view node removes an action from **both** toolbar and row — it cannot do toolbar-only. Switch the category instead.

## ListView command-column action capture (the big trap)

The command column snapshots its action **set once at control-build time** (`Frame_TemplateChanged → CollectActions → SetActions`). Consequences:
- Actions must **exist in the controller constructor**. An action created later (e.g. on `Activated`/after a cache load) never reaches the column.
- `TargetObjectsCriteria` only **disables per-row** (greyed button on every row) — it does **not** hide. To remove a captured action entirely: `action.Active.SetItemValue("key", false)`.
- Changing `TargetObjectsCriteria` or `Active` **after** build DOES propagate; adding new action *objects* after build does NOT.
- Pattern for data-driven row actions whose config loads late: pre-create a fixed **pool** of N `SimpleAction` slots in the ctor (all `Active=true`, criteria `"1=0"`), then configure the matching slots and deactivate leftovers once config loads. See `StateMachineController`.

## CustomizeElement is a no-op — use cell template + `tr:has()`

Assigning `DxGrid.CustomizeElement` imperatively via `GetGridAdapter().ComponentCaptured` **does not take effect** — XAF owns the render tree and resets the `[Parameter]`. Only **RenderFragment template** props survive that channel.
- Cell template DOES work: `adapter.GridDataColumnModels.First(c => c.FieldName==…).CellDisplayTemplate = RenderFragment<GridDataColumnCellDisplayTemplateContext>` inside `grid.BeginUpdate()/EndUpdate()`.
- To target a whole `<tr>` (e.g. drop zone), render a unique marker inside the cell template (`<span class="cl-row-marker-{oid:N}">`) and resolve with `tr:has(.cl-row-marker-{oid})`. `:has()` works in the app's Chromium. `DxFileInput.ExternalDropZoneCssSelector` accepts it.

## Expandable detail rows

XAF doesn't expose `DxGrid.DetailRowTemplate`; set it via reflection on `DxGridListEditor.ComponentModel` in `OnViewControlsCreated` (prop `"ComponentModel"` then `"DetailRowTemplate"` = `RenderFragment<GridDetailRowTemplateContext>`). Setting it auto-adds the expand chevron.
- Context exposes `DataItem`, `Grid`, **`MasterRowVisibleIndex`** — there is **no `VisibleIndex`**. Detail methods take that master index: `ExpandDetailRow(int)`, `CollapseDetailRow(int)`, `IsDetailRowExpanded(int)`.
- `ExternalDropZoneCssSelector` binds a **single** element (first match). To make an expanded detail row a drop target too, give it its own drop zone with a **distinct** marker key.
- `View.Refresh()` does **not** re-invoke `DetailRowTemplate` for an already-expanded row → collapse then expand to refresh.

## Grid chrome levers

- **Search / Export**: toolbar Actions — hide per-view via `<HiddenActions>` (IDs `FullTextSearch`, `Export`).
- **Pager + page-size selector**: not model-exposed. In `OnViewControlsCreated`: `(View.Editor as DxGridListEditor)?.GetGridAdapter() is DxGridAdapter a` → `a.GridModel.PagerVisible = false; a.GridModel.PageSizeSelectorVisible = false;`. `ShowAllRows="True"` (Blazor model) renders one page.
- **Row selection**: `GridSelectionMode` has no `None` (XAF hardcodes `Multiple`, checkbox column always rendered). Off-switch: `a.SelectionColumnModel.Visible = false; a.GridModel.AllowSelectRowByClick = false;`. These props aren't re-synced from the model, so they stick.

## SimpleListEditor add/delete are dead without AllowEdit

The custom `[SimpleListEditor]` (`Source/SBFrameDx/SB.XafEditors.Blazor/Editors/SimpleListEditor/`, a subtree) gates its inline "+ Zeile" and per-row delete on the nested `<ListView>` node's `AllowEdit`, which **defaults to false**. Omit `AllowEdit="True"` and the add button renders disabled and silently early-returns. Set `AllowEdit="True"` on the collection's ListView node.

## RichEdit custom color picker

Built-in RichEdit color buttons are fixed-palette with no seam for custom hex/RGB; replacing them means a custom button + your own popup hosting the internal `DxColorPicker`, wired on the **Ribbon** (not Toolbar) for the Stilvorlagen editors. Full recipe, per-context apply-API map, and gotchas: see [richedit-color-picker.md](richedit-color-picker.md).
