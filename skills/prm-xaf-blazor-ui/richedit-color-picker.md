# RichEdit custom color picker (custom hex/RGB)

Reference for replacing the DevExpress Blazor RichEdit's fixed-palette color buttons with a custom
picker that supports hex/RGB. Editor = `RichTextPropertyEditor` (used by `StyleTemplate.Content` /
"Stilvorlagen" and `TextTemplate.Content`). DX 25.2.5. Line numbers point-in-time — verify against
current source; delegate DX API checks to the `dx-lookup` skill.

## The constraint

The built-in RichEdit color buttons (`RichEditBarItemNames.FontColor`, `HighlightText`, `PageColor`,
`TableCellShading`, `ParagraphShading`, `FloatingObjectFillColor/OutlineColor`, `TableBorderColor`)
render a **fixed palette with no custom hex/RGB input, and this cannot be changed on the built-in
button**. RichEdit's internal `ColorEdit.razor` hardcodes `<DxColorPicker>` without ever setting
`EnableCustomColors` (defaults `false`); there is no `DxRichEditModel` parameter, no cascading value,
no DI default, and `AddCustomColorEdit` renders through the same dialog. `BarItemCollection` factories
(`AddCustomButton`, `AddCustomDropDown`, `AddCustomColorEdit`) accept **no** RenderFragment/template,
so you can't host a picker inside a toolbar/ribbon item.

## The color-picker component

- There is **no public `DxColorPicker`** in `DevExpress.Blazor` — only `DxColorPalette` (fixed tiles,
  no hue/hex/RGB). The rich HSV+hex+RGB `DxColorPicker` lives in **`DevExpress.Blazor.Internal`** only
  (accepted upgrade risk; precedent for using Internal types: `LayoutAndFilteringModule.Blazor/Controllers/ViewVariantsController.cs`).
- Internal `DxColorPicker` binds `@bind-Color` to a **non-nullable `System.Drawing.Color`** +
  `EnableCustomColors="true"`. With custom colors on, it shows its **own** OK/Cancel sub-panel that
  can't be hidden — so drive it with `Color=@Service.Current ColorChanged=OnColorChanged` (immediate
  apply on palette click / custom-OK) rather than adding your own confirm buttons.

## BarMode decides which hook fires — check this first

The Stilvorlagen/TextTemplate editors run in **Ribbon** mode: `StyleTemplate_DetailView` and
`TextTemplate_DetailView` set `<PropertyEditor Id="Content" BarMode="Ribbon" .../>` in
`Source/Prod/PRM.Module/Model.DesignedDiffs.xafml`, which wins over the Blazor app-level
`BarMode="None"` default. So `CustomizeToolbar` **never fires** for these views — a toolbar-only
implementation produces zero visible change. Customize the **ribbon**: chain (don't overwrite)
`CustomizeRibbon` on `IRibbon`, reach `ribbon.Tabs[RichEditRibbonTabNames.Home].Groups[RichEditRibbonGroupNames.HomeFont]`
(an `IBarGroup`), and reuse the same `AddColorButtons(IBarGroup, …)` helper. In a flat toolbar the only
color button present is FontColor; table/floating buttons live only in dynamic ribbon **context tabs**.

## Recipe (the only path to custom hex)

1. Hide the stock button: `group.Items[itemName].GetVisible = () => false;` (`IBarItem` has **no**
   `Visible` bool — `GetVisible` is a settable `Func<bool>`). Setting both toolbar+ribbon callbacks is
   harmless — only the active BarMode's renders.
2. Add a custom `AddCustomButton(text, Func<Task>)` whose click opens your own popup hosting the
   internal `DxColorPicker EnableCustomColors="true"`. `IBarButton.IconUrl` accepts a data-URI SVG
   (multi-color, unlike a CSS mask).
3. Anchor the popup under the button with **`DxDropDown`** (`PositionTarget` CSS selector,
   `PositionMode=Bottom`, `CloseOnOutsideClick`) — **not `DxPopup`** (centered modal, no anchoring).
   `IBarButton` exposes `CssClass` but **no `Id`** → tag each color button a unique CssClass and point
   the shared dropdown's `PositionTarget` at `.that-class`.
4. Host must live once at root layout (`CustomMainFormTemplateComponent.razor`) + a **per-circuit scoped
   service** exposing `Task<Color?> PickAsync(current, anchorSelector)` (TaskCompletionSource). Resolve
   in controllers via `ObjectSpace.ServiceProvider.GetRequiredService<T>()` — verify it's the circuit
   scope (same instance the injected component uses).
5. Fake the stock **split button** with **two** custom buttons: a main one (icon-only,
   `TextDisplayMode.None`) that re-applies the remembered color, and a `"▾"` one that opens the picker.
   Remember the last color in the **service** (`GetLastColor/SetLastColor` keyed by anchor CssClass) —
   **not** a closure local, because `CustomizeToolbar`/`CustomizeRibbon` re-run the add-button code on
   every toolbar rebuild and would reset a captured variable.

## Apply-API map (per context, source-verified DX 25.2)

| Button | Apply API | Type | Reachable? |
|---|---|---|---|
| FontColor | `CharacterProperties.ForegroundColor` via `GetTextSpanAsync`→`ChangePropertiesAsync` | `Color?` | ✅ |
| HighlightText | `CharacterProperties.HighlightColor` (same text-span path) | `Color?` | ✅ |
| ParagraphShading | `ParagraphProperties.BackgroundColor` | `Color?` | ✅ (Home tab) |
| TableCellShading | `TableCellProperties.BackgroundColor` | `Color` | ✅ (Table context tab) |
| TableBorderColor | `TableBorder.Color` via `TableCellProperties.Borders` | `Color` | ✅ (Table context tab) |
| FloatingObjectOutlineColor | `ImageProperties.Outline.Color` | `Color` | ✅ (Floating context tab) |
| PageColor | — no public API (SectionProperties has no bg color) | — | ❌ |
| FloatingObjectFillColor | — no public API (ImageProperties has Outline only) | — | ❌ |

`TextSpan.ChangePropertiesAsync(...)` returns a **`ValueTask`** → `.AsTask()` to fit a `Func<…,Task>`.
PageColor + FloatingObjectFillColor have no programmatic apply API → leave stock or hide.

## Where it lives

`SB.XafEditors.Blazor/Editors/RichEditColorPicker/` (`RichEditColorPickerService.cs` scoped +
`RichEditColorPickerHost.razor`), registered `AddScoped<RichEditColorPickerService>()` in
`XafEditorsBlazorModuleApplicationBuilderExtensions.AddXafEditors`; host placed in
`CustomMainFormTemplateComponent.razor`; buttons wired in `CustomizeRichTextEditorBarItemsModeController`
(chains both `CustomizeToolbar` and `CustomizeRibbon`). `SB.XafEditors.Blazor` is a git **subtree** —
edit with care.

**Deploy gotcha:** `PRM.Blazor.Server` build fails with MSB3027/MSB3021 file-lock errors while the app
runs under VS/IIS Express — fully STOP the app before rebuild or the new `SB.XafEditors.Blazor.dll`
won't copy over the locked one.
