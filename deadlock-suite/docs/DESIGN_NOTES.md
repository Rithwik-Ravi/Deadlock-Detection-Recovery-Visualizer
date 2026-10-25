# Design notes: web UI redesign

Scope: `web/` only (HTML, CSS, JS, vendored fonts). No changes to `core/`,
`server.py`, `main.py`, `demo_scenarios.py`, `tests/`, API routes, or the JSON
contract.

---

## 1. Audit

### 1.1 Known issues from the brief (all must be fixed)

1. Navy background, neon cyan glow, gradient "RAG" logo tile.
2. Emoji used as icons in tabs, panel headings, and buttons.
3. Every panel is the same rounded dark card with an emoji + title header.
4. Monospace used for nearly all text.
5. Graph uses only the left ~40% of its canvas; a large empty band sits below the controls.
6. Edge labels ("x2", "x3") collide with lines; arrowheads end inside nodes; resource labels are crossed by edges.
7. At step 0 every unfinished process is amber "Blocked", which is false.
8. Banner "Executing detection step 0 of 5..." adds nothing.
9. Long "Viva key takeaway" block competes with the algorithm state.
10. Layout does not scale: tiny text and wasted space at 2560 px.

### 1.2 Additional defects found in the source

Browser screenshots could not be captured: the browser agent got
`net::ERR_ABORTED` on `http://127.0.0.1:8000` twice while the server was
answering requests. These findings come from reading the code. Screenshots will
be added once browser access works.

**Figure (`rag.js`)**

| # | Defect | Cause |
|---|--------|-------|
| F1 | Drawing doesn't fill the plate; dead space at wide aspect ratios | Fixed `viewBox 0 0 960 500` with `meet`; processes pinned at x=180, resources at x=760 |
| F2 | Arrowheads stop inside resource boxes and at varying depths in circles | Marker `refX` hard-coded (26/32/28) while the rect is 110×64 and the circle r=25; edges run center to center |
| F3 | Edges cross the resource title text | Title "A (2/7 Free)" is drawn inside the box at y=-14; edges aim at the box center |
| F4 | Multiplicity labels sit off their curve and overlap | Label placed at the straight-line midpoint while the path is a quadratic offset by ±20 px; no background, no collision handling |
| F5 | Allocation and request edges between the same pair cross each other | Opposite fixed control offsets (±20) instead of parallel offset curves |
| F6 | Curve shape jumps after a node is dragged | `render` uses a ±20 offset but `updateNodePositions` uses ±25 |
| F7 | Node order ignores edges, so crossings are high | Nodes placed in index order |
| F8 | Instances capped at 10 with a "+N" overflow, all in one row | Hard limit in the dot loop |
| F9 | Step highlight fights the re-render | `animateProcessRelease` sets the fill to green and r=32, then `render()` overwrites it right away |
| F10 | Tooltip shows uppercase state and uses inline color styles | `d.state.toUpperCase()` |
| F11 | PNG export has a navy background and a stretched aspect ratio | Fills `#070a12`; draws into a fixed 1700×1160 canvas |
| F12 | Recovery and detection share one tooltip element; colors live in JS, not tokens | Hard-coded hex values throughout |

**Playback (`playback.js`)**

| # | Defect |
|---|--------|
| P1 | Step 0 marks every process without an initial finish as `"blocked"` (amber), which is false. |
| P2 | Status banner narrates progress ("Executing detection step..."). |
| P3 | Work flashes on every step, even when unchanged; Finish changes aren't marked. |
| P4 | No "last step" control; no Home/End keys; speed is a native select that includes 0.25x. |
| P5 | Step counter reads "Step 0 / 5"; the initial state isn't named. |
| P6 | The trace is a plain list of divs, not a numbered sequence. |

**Layout and CSS (`style.css`, `index.html`)**

| # | Defect |
|---|--------|
| L1 | `body { min-width: 1100px; overflow-x: auto }` forces horizontal scroll below 1100 px. |
| L2 | All sizes are fixed px (11–13 px text), so the UI looks tiny at 2560 px. |
| L3 | `backdrop-filter`, radial-gradient body, glow and drop shadows on every card. |
| L4 | Fixed heights: recovery canvas 520 px, attributes table max 240 px, viva list max 650 px. Causes dead bands and inner scrolling. |
| L5 | Many inline `style=""` attributes in HTML and JS-generated markup, so tokens can't apply. |
| L6 | All-caps labels: "SELECT RECOVERY STRATEGY:", "MIN", "BEST", "FAIREST", "REPAID", "OPEN", "SUSP", "ABORT". |
| L7 | Middle-dot meta strings in header and footer ("BCSE303L • Silberschatz..."). |
| L8 | Errors shown with `alert()`. |

**Recovery tab (`recovery_view.js`)**

| # | Defect |
|---|--------|
| R1 | Strategy chooser uses pill buttons with no descriptions; selection is shown only by color. |
| R2 | The attributes table shows only priority, progress, and work units. `rollback_fraction` and `restartable` are sent to the API but can't be edited. Invalid input silently falls back to defaults. |
| R3 | Ledger has no "owed by" column, though `debtor_set` is in the response; status uses emoji. |
| R4 | Blame bars aren't sorted. |
| R5 | Comparison is a dense table with all-caps winner tags; there's no visual comparison. |
| R6 | Recovery animation is a fire-and-forget `setInterval`: no plan list, no current-action highlight, no step control. Clicking run twice starts two intervals. |
| R7 | "Proposed" is a gradient badge; the benchmark row uses a "★". |

**Custom matrix and theory**

| # | Defect |
|---|--------|
| C1 | Process and resource names can't be renamed. |
| C2 | One shared error box; no per-cell validation messages. |
| C3 | No empty state. |
| T1 | Viva Q&A is rendered as cards with numbered questions; there's no theory prose, formulas, or table of contents. |
| T2 | The scenario's viva note appears only after the scenario changes, not on first load. |

---

## 2. Token system

### 2.1 Color

```css
--sheet:      #F7F9FB;  /* page */
--plate:      #FFFFFF;  /* figure, tables */
--grid-minor: #E6ECF2;
--grid-major: #D3DCE6;
--ink:        #26323F;  /* 12.9:1 on sheet */
--ink-soft:   #5A6877;  /* 5.6:1 on sheet, 5.9:1 on plate */
--rule:       #D5DCE4;
--pen-blue:   #1F4FBF;  /* 7.4:1 on plate */
--pen-red:    #C62828;  /* 5.6:1 on plate */
--marker:     #FFE45C;  /* multiply, 85% opacity; ink on marker 11:1 */
--ok:         #1E7B4F;  /* 5.4:1 */
--suspend:    #6B4FA3;  /* 6.6:1 */
--abort:      #8A94A0;  /* 3.0:1 on plate: used only for marks and bars, never text */
```

Contrast ratios are estimates and will be re-checked with a calculator during
verification. `--abort` text labels will use `--ink-soft` instead.

### 2.2 Type

| Role | Family | Weights |
|------|--------|---------|
| UI, labels, buttons, tabs | Atkinson Hyperlegible Next | 400, 600 |
| Headings, explanations, prose, viva | Source Serif 4 | 400, 600 |
| Vectors, matrices, trace only | JetBrains Mono, `tabular-nums` | 400, 600 |

- Vendored as `.woff2` in `web/vendor/fonts/` (Latin subset), `font-display: swap`.
- `html { font-size: clamp(15px, 0.35vw + 13px, 21px); }`, which gives about 17.5 px at 1280, 19.7 px at 1920, and 21 px at 2560.
- Scale (rem): `--t-sm .875`, `--t-base 1`, `--t-md 1.125`, `--t-lg 1.375`, `--t-xl 1.75`.
- Prose: `max-width: 68ch`, `line-height: 1.55`.

### 2.3 Spacing, radius, motion

- Spacing (rem): `--s-1 .25`, `--s-2 .5`, `--s-3 .75`, `--s-4 1`, `--s-5 1.5`, `--s-6 2`, `--s-7 3`.
- Radius: `--r-control 4px` (buttons, inputs), `--r-chip 999px`, plate `0`, nodes are circles.
- Rules: `1px solid var(--rule)`. The only shadow is on the plate: `0 1px 0 var(--rule), 0 2px 6px rgb(38 50 63 / .05)`.
- Motion: `--dur 180ms`, `--ease cubic-bezier(.2,.7,.3,1)` (ease-out). The only continuous animation is `stroke-dashoffset` on deadlock-cycle edges. Under `prefers-reduced-motion: reduce`, durations are 0 and the dash is static.
- Focus: `outline: 2px solid var(--pen-blue); outline-offset: 2px` via `:focus-visible`.

### 2.4 Highlighter motif

One SVG/CSS treatment used in four places: current process node, current trace
row, changed Work/Finish cells, and the candidate's matrix rows.

- HTML: `background` made of a `--marker` band at 85% opacity, `mix-blend-mode: multiply`, with slightly uneven radius (`border-radius: 3px 6px 4px 7px / 6px 3px 7px 4px`) and a small skew so it reads as a hand stroke.
- SVG: a `path` with the same uneven rounded shape behind the node, `fill: var(--marker)`, `opacity: .85`, `mix-blend-mode: multiply`.

---

## 3. Shared components

| Component | Markup | Used in |
|-----------|--------|---------|
| Header | `.masthead` wordmark + `.tabs` + `.toolbar` | all |
| Figure plate | `.figure` > `.figure-tools` (edge toggles, zoom, Fit) + `.plate` (svg) + `figcaption` + `.legend` | Detection, Recovery |
| Transport bar | `.transport` (6 icon buttons, scrubber with ticks, speed segmented control) | Detection, Recovery plan |
| Key-value table | `.kv` | State section, metrics |
| Section | `.section` > `h2.section-title` + content; separated by `border-top: 1px solid var(--rule)` | right columns, recovery |
| Data table | `.data` (mono numbers, sticky headers, `.is-current` highlighter row, `.is-done` soft row) | matrix strip, ledger, editor, attributes |
| Icon set | inline `<svg>` symbols in `index.html` (`#i-first`, `#i-prev`, `#i-play`, `#i-pause`, `#i-next`, `#i-last`, `#i-zoom-in`, `#i-zoom-out`, `#i-fit`), 24-unit grid, 1.5 px stroke, round caps | transport, zoom |

The figure is one class, `RAGVisualizer`, instantiated twice, so detection and
recovery share every rendering rule.

---

## 4. Wireframes

### 4.1 Detection (≥ 1100 px)

```
+--------------------------------------------------------------------------------------+
| Deadlock detection and recovery   Detection  Recovery  Custom matrix  Theory         |
|                        Scenario [Classic Silberschatz v]  [Run detection]  [Export v]|
+-----------------------------------------------------------+--------------------------+
| Allocations  Requests                      [-] [+] [Fit]  | Step 3 of 5              |
| +-------------------------------------------------------+ | P1 can finish: its       |
| | graph paper                                           | | request [2,0,2] fits in  |
| |  (P0)  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   A  2 of 7  | | Work [3,1,3].            |
| |  (P1)  ~~~~~~~~ curved edges ~~~~~~~~~~~   [o o o .]  | |--------------------------|
| |  (P2)  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   B  0 of 2  | | Available  3 3 2         |
| |  (P3)                                       [o o]     | | Work       5 1 3  (band) |
| |  (P4)                                       C  ...    | | Finish     T F T F F     |
| +-------------------------------------------------------+ |--------------------------|
| Figure: resource allocation graph for Classic ... (safe). | Safe order P0 → P2 → P1  |
| (ring) unresolved (check) finished (hatch) deadlocked ... |--------------------------|
|-----------------------------------------------------------| Trace                    |
| |<  <  (>)  >  >|   |--|--|--|--|--|  step 3   0.5x 1x 2x 4x | 1 P0 ... 2 P2 ...(band)|
+-----------------------------------------------------------+--------------------------+
| Allocation          | Request             | Available                               |
|    A B C            |    A B C            |  A B C                                  |
| P0 0 1 0            | P0 0 0 0            |  0 0 0                                  |
| P1 2 0 0  (band)    | P1 2 0 2  (band)    |                                         |
+--------------------------------------------------------------------------------------+
| > Viva note                         BCSE303L Operating Systems. Sri Krishna (...) ...|
+--------------------------------------------------------------------------------------+
```

- Grid: `grid-template-rows: auto 1fr auto auto` on `body` at `100dvh`. The main row is `minmax(0,1fr) clamp(20rem, 28vw, 30rem)`.
- The trace list is the only element that scrolls internally, so the page never scrolls at ≥1280×720.
- Below 1100 px the right column drops under the figure and the page scrolls normally. The plate gets `min-height: 60vh`.

### 4.2 Recovery

```
+----------------------+------------------------------------+---------------------+
| Strategy             | Allocations  Requests   [-][+][Fit]| Plan                |
| ( ) Abort all        | +--------------------------------+ | 1 Suspend P0 ...    |
|     Kill every ...   | | same figure plate              | | 2 Lend 1 B ...(band)|
| ( ) Abort one by one | |  suspended (pause mark)        | |---------------------|
| ( ) Preempt and roll | |  aborted (struck label)        | | Ledger              |
| (o) Debt-Ledger Rec. | |  purple ledger curves          | | creditor res units  |
|     Proposed method¹ | +--------------------------------+ | owed by  status     |
|----------------------| Figure: recovery for ... (DLR).    |---------------------|
| Process attributes   | |< < (>) > >|  ticks ... 1x 2x     | Blame               |
| P  prio prog work rb | |                                  | P1 ======== 0.420   |
| P0 [5] [.3] [50][.5]x|                                    | P2 ====     0.210   |
| [Run recovery]       |                                    |                     |
+----------------------+------------------------------------+---------------------+
| Comparison   [Compare all strategies]  [Run on 200 random systems]               |
| Lost work      Processes aborted   Recovery steps   Total cost     Fairness     |
| |█ 12.0        |█ 2               |█ 6             |█ 4.1         |█ .82        |
| |█ 8.0         ...                                                              |
| |█ 0.0 (blue, underlined = best)                                                |
| Aggregate over 200 random systems (plain table)                                  |
+----------------------------------------------------------------------------------+
```

- Top region fills the viewport like Detection. Comparison sits below and the page scrolls to reach it (it's a separate reading task).
- The recovery transport bar uses the same component. Actions are stepped from `report.actions` and their `snapshot`; play uses the chosen speed.
- "Recovery steps" = `actions.length` for each strategy in the compare response. I'll confirm the key exists. If it doesn't, the chart is omitted and listed under "Needs backend".

### 4.3 Custom matrix

```
| Custom matrix                    Load a scenario   Add process  Add resource     |
| Available   A[3] B[3] C[2]  (resource headers renamable in place)                |
| Allocation (sticky row/col headers)      Request                                 |
|        A   B   C                                A   B   C                        |
| [P0]  [0] [1] [0]  Remove                [P0]  [0] [0] [0]                       |
|  "Allocation for P2 cannot be negative."  (pen-red, under the cell)              |
|                                                       [Run detection]            |
```

- "Remove" text buttons sit on each row and column header (replaces the old pop-last buttons; same underlying operation, applied to the chosen index).
- Validation runs on input. "Run detection" is disabled while errors exist.
- Empty state (0 processes or 0 resources): one sentence plus a "Load a scenario" link.

### 4.4 Theory

```
| Contents            | Deadlock detection (serif h1)                                 |
| Coffman conditions  | prose, 68ch                                                   |
| Detection algorithm | | Work = Available                (mono, plate, blue left rule)|
| Recovery strategies | | Finish[i] = (Allocation[i] == 0)                            |
| Debt-Ledger Recov.  | Viva questions                                                |
| Viva questions      | > What is the difference between detection and avoidance?    |
|                     | > ...                                                        |
```

- The existing viva Q&A text is kept verbatim, minus the leading "1." numbering, which `<details>` order makes redundant. Search stays as a plain input above the list.
- Theory prose: short sections built only from content already in the app (algorithm steps, the DLR invariants already stated in the viva answers). No new claims.

---

## 5. Figure algorithm

1. **Measure** the plate with `ResizeObserver` and set `viewBox = 0 0 W H` to the plate's pixel size. No `meet` letterboxing.
2. **Order** nodes with a barycenter heuristic: 4 alternating sweeps, ties broken by index.
3. **Columns**: processes at `x = pad + R`, resources at `x = W - pad - boxW/2`. The empty channel between them holds the curves.
4. **Vertical spacing**: even, across the full usable height, with a clamped minimum gap.
5. **Sizes**: R = clamp(22, H/(2.6n), 34) px. Box width comes from the instance grid (≤ 4 rows). Labels above boxes with fixed padding.
6. **Edges**: cubic Bezier with horizontal tangents (`C x1+k,y1  x2-k,y2  x2,y2`). Endpoints are clipped to the circle (along the tangent direction, i.e. `±R` in x at the node's y, offset for parallel pairs) and to the box's left edge. Arrowheads are drawn as separate path triangles at the clipped end (no `refX` guessing). Same-pair alloc/request pairs get a parallel ±6 px vertical offset.
7. **Multiplicity pills**: at t = 0.3 from the process end. Collision pass: sort by y and push overlapping pills apart along their curve's t (0.2–0.45). If still overlapping, nudge vertically.
8. **Grid paper**: `<pattern>` in user space (24/120 px) on a rect inside the zoomed group, so it zooms with the drawing.
9. **States**: marks are drawn per state (check, hatch, pause, strike, dashed ring). The highlighter path sits behind the node.
10. **Focus mode**: hover or focus dims unrelated edges to 8% and shows the tooltip. Click pins; Escape clears. Nodes get `tabindex="0"` and an `aria-label`.
11. **Fit**: computes the content bounding box and applies a d3 zoom transform. Runs on load, resize, scenario change, and the Fit button.

---

## 6. Banned-list check against this plan

| Banned item | Plan status |
|-------------|-------------|
| Emoji | None. Ledger status uses text plus a small SVG mark. |
| Gradients | None. The highlighter is a flat fill with multiply. |
| Glow / neon | None. The cycle uses a red stroke plus dash flow only. |
| Navy/cyan | Replaced by the cool-white sheet and blue/red pens. |
| Cream | `--sheet` is cool `#F7F9FB`. |
| Terracotta/clay | Not used. |
| Identical cards | Removed. Sections are separated by rules; one plate only. |
| Panel drop shadows | Only the plate has a faint paper-edge shadow. |
| All-caps / letter-spacing | Removed (L6). Sentence case everywhere. |
| Eyebrow labels | None. |
| Middle-dot meta | The footer is one plain sentence with commas. |
| Spaced em-dash labels | None. |
| Arrows on buttons | None. Arrows appear only in the safe order. |
| Mono for non-data | Mono only in vectors, matrices, trace, formulas. |
| Fade/slide entrances | None. |
| Hover lift | None. Hover changes only color or underline. |
| Color-only state dots | Legend uses the real marks (ring, check, hatch, pause, strike). |
| Narrating banner | Removed. Replaced by "Step n of N" plus the algorithm's own explanation. |
| Large empty areas | Viewport grid; the figure fills its plate. |

**Revisions made after the check**

- First draft: "Proposed" as a small blue chip next to DLR. Revised to plain text "Proposed method" with a footnote link, because a colored chip is a badge.
- First draft: Finish shown as colored T/F cells. Revised to T/F text with the highlighter only on cells that changed this step, so color isn't the only signal.
- First draft: a green check badge next to "Safe order". Removed as decoration; the line itself says "Safe order".

---

## 7. Needs backend (so far)

- None identified yet. Ledger "owed by" uses the existing `debtor_set`. Matrix strip uses `report.matrices`. "Recovery steps" will be computed client-side from `actions.length` if the compare response includes actions; otherwise it's listed here.
