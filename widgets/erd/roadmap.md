# ERD Editor — Production Roadmap

> Goal: take the current ERD editor from a feature-rich tool (~7/10) to a polished, production-ready editor that competes head-on with **pgAdmin's ERD**, **DBeaver's diagrams**, **draw.io's DB shapes**, and meaningfully overlaps with **MySQL Workbench** and **dbdiagram.io**.
>
> Living document. Each phase is ordered by user-visible impact ÷ engineering cost and references the file(s) most likely to change.

---

## What's already built (April 2026)

### Core editing
- **Crow's-foot tables** with header, schema badge, columns, PK/FK indicators (`items/table_item.py`).
- **Chen notation**: entities, weak entities, attribute ellipses, relationship diamonds (`items/entity_item.py`, `weak_entity_item.py`, `attribute_item.py`, `relationship_diamond_item.py`).
- **Notes** and **subject areas** (`items/note_item.py`, `subject_area_item.py`).
- **Resizable items** with hit-tested handles, padded `boundingRect` + `shape` (`items/resizable.py`).
- **Connection ports** with hover highlighting; **drag-to-connect** with floating preview, drag-distance threshold, snap-to-anchor.
- **Self-loops** with cubic Bezier (`items/connection_item.py:updateSelfLoopPath`).
- **Animated flow dashes** (forward / backward / bidirectional).
- **Connection slot offsets** so multiple FKs between the same pair of tables stack neatly.

### Routing
- **A\* orthogonal router** with grid + obstacles (`routing.py:ERDRouter`).
- **Direct-vertical optimization** when shapes are stacked.
- **Per-side preferred-side scoring**, candidate enumeration, Manhattan forcing.
- **Slot-aware anchor placement** for parallel relationships.
- **Per-shape boundary intersection** for Chen anchors (ellipse / diamond / rect).

### Forward engineering (DDL) — present
- `generate_sql_script()` in `widget.py:80` — dialect-aware DDL generation.
- **Topological sort (Kahn's algorithm)** so FK targets emit before referrers.
- **Dialects:** PostgreSQL, SQLite, generic. (MySQL, MSSQL not yet.)
- Identifier quoting per dialect; `CREATE TABLE`, `PRIMARY KEY`, `FOREIGN KEY`.
- `SQLPreviewDialog` with copy / save-as `.sql`.
- Toolbar button + `Alt+Ctrl+S` shortcut.

### Reverse engineering (live DB) — present
- Live schema import via the parent `DB_Explorer` app's connection layer — `schema_data` dict is fed in at `ERDWidget.__init__` (`widget.py:242`), then `load_schema()` materializes tables, columns, FKs, and groups into Subject Areas via connected-component detection.
- *Not yet:* SQL file (`.sql`) import, DBML import.

### Auto-layout — present
- **Sugiyama-style hierarchical layout** in `widget.py:auto_layout` (line 751):
  - Connected-component detection.
  - Dependency-rank assignment (BFS over FK DAG).
  - Crossing-reduction via centrality / barycenter heuristic within each rank.
  - Independent placement per component, vertical stacking by size.

### Export — present
- `save_as_image(ext)` in `widget.py:1028`:
  - **PNG / JPG** — 2× supersampled, 16K max-dim safety, transparent or white fill.
  - **SVG** — `QSvgGenerator` with viewBox; vector-correct.
  - **PDF** — `QPdfWriter` at 300 DPI.
- Uses `scene.itemsBoundingRect()` + 50 px margin.

### UX
- **Search bar** (`Ctrl+F`) — dim non-matching tables, Enter to centre on first hit (`widget.py:419-456`, `scene.py:apply_search_filter`).
- **Zoom in/out** (`Ctrl++`, `Ctrl+-`).
- **Undo / redo** via `QUndoStack` for adds / deletes / moves / resizes / connection changes (`commands.py`).
- **Property panel**, **palette**, **dialogs**.
- **Save / load diagram** as JSON with view-state versioning (`view_state.version = 3`).

### Honest residual gaps
- **No automated tests** — the recent `boundingRect` regression and connection-gap regression would have been caught by a single routing test.
- **Code duplication** — port-press / resize plumbing repeated across the 5 shape items.
- **No dark mode / themes** — colours hard-coded across `paint()` methods.
- **No SQL file (`.sql`) import** — only live-DB import.
- **No DBML round-trip**.
- **No schema diff / migration SQL**.
- **No MySQL or MSSQL DDL dialects**.
- **No minimap, no align/distribute, no smart guides**.
- **No in-canvas column edit** (everything goes through the property panel / dialog).
- **Performance on very large schemas (200+ tables)** is unverified.

---

## Guiding principles

1. **No new feature without a test.** A handful of `pytest-qt` tests would have prevented both regressions we hit recently.
2. **Prefer mixin extraction over duplication.** Port handling and resize handling are repeated 5×.
3. **Extend, don't replace.** DDL, auto-layout, and export already exist — improve them, don't rewrite.
4. **Match user mental models from pgAdmin / DBeaver / Workbench**, not invent new ones.
5. **Ship every phase as a self-contained release** users can adopt without reading docs.

---

## Phase 0 — Stabilize (1–2 weeks)

Lock in the current feature set. No new user-visible features.

- [ ] **Test harness**
  - Add `pytest-qt` to `requirements.txt`.
  - `tests/erd/test_routing.py`: anchor positions for tables & Chen items, direct-vertical condition, slot offsets, padded-`boundingRect` vs `item_visual_scene_rect` invariants, `get_dynamic_anchor` correctness.
  - `tests/erd/test_connection_lifecycle.py`: drag-from-port → drop-on-target → `AddConnectionCommand` → undo → redo, drag-threshold cancellation, dangling-on-empty-release.
  - `tests/erd/test_resize.py`: handle hit-test inside padded `boundingRect()`, resize undo command roundtrip.
  - `tests/erd/test_ddl.py`: `generate_sql_script` round-trip for sample schemas in PG / SQLite.
  - `tests/erd/test_layout.py`: `auto_layout` non-overlap on a sample schema.
- [ ] **Refactor: `PortMixin`**
  - Extract `arm_port_drag` / `maybe_start_port_drag` / `cancel_port_drag` plumbing from the 5 shape items into a single mixin.
  - Goal: ~250 lines of duplication removed, single place to fix port bugs.
- [ ] **Refactor: routing's source of truth**
  - Document why `boundingRect()` is padded (handles) and that routing must use `item_visual_scene_rect()` instead.
  - Audit remaining `sceneBoundingRect()` usages in `routing.py`, `connection_item.py`.
- [ ] **Bug triage pass**
  - Self-loop label position.
  - Connection re-route on table resize: verify `_router_cache` invalidation.
  - Drag-side detection in `floating_connection.updatePath` after the visual-rect fix.

**Exit criteria:** CI green; no known visual regression in any of the 5 shape types.

---

## Phase 1 — DDL, Round Two (1–1.5 weeks)

Forward engineering already exists; round it out.

- [ ] **MySQL dialect** in `generate_sql_script()` — backtick quoting, `AUTO_INCREMENT`, `ENGINE=InnoDB`, charset/collation.
- [ ] **MSSQL dialect** — bracket quoting, `IDENTITY(1,1)`, `nvarchar` defaults.
- [ ] **More constraint types** — `UNIQUE`, `CHECK`, `DEFAULT`, `NOT NULL`: audit and complete.
- [ ] **`COMMENT ON`** for tables/columns (PG) / inline `COMMENT '...'` (MySQL).
- [ ] **Indexes** — promote to first-class metadata; emit `CREATE INDEX`.
- [ ] **Per-table "Copy DDL"** right-click action.
- [ ] **Live DDL preview pane** (optional) — collapsible side panel that updates as the diagram changes.
- [ ] **Promote model** — `model.py` is 1.7 KB; introduce typed dataclasses (`Table`, `Column`, `ForeignKey`, `Index`, `Check`) so DDL generation, diff, and import all share one model.

**Exit criteria:** PG / MySQL / SQLite / MSSQL DDL round-trips through their respective servers and recreates an identical schema.

---

## Phase 2 — SQL & DBML Import (1.5 weeks)

Today only live-DB import works; add file-based import.

- [ ] **SQL file importer** — adopt `sqlglot` (MIT, supports PG / MySQL / SQLite / MSSQL / Oracle / Snowflake). Parse `CREATE TABLE` / `ALTER TABLE ... ADD CONSTRAINT` into model objects.
- [ ] **DBML importer** (`pydbml`) — dbdiagram.io compatibility.
- [ ] **DBML exporter** — emit DBML for round-trip.
- [ ] **Drag-and-drop `.sql` / `.dbml` files** onto the canvas.
- [ ] **"Open SQL…" menu entry**.
- [ ] **Auto-layout on import** so a 50-table import doesn't dump at (0,0) — already exists, just call after import.

**Exit criteria:** import `pagila.sql` and get a usable diagram in <5 s; round-trip through DBML and back without data loss.

---

## Phase 3 — Schema Diff & Migration (2 weeks)

The differentiator. pgAdmin and DBeaver have weak UIs here; Workbench has it but it's clunky.

- [ ] **Snapshot model** — `model_snapshot()` deep-copies the current model; persist as JSON beside the diagram (or alongside saved view-state).
- [ ] **Diff engine** — new `widgets/erd/diff.py`:
  - Added / dropped / renamed (ID + name heuristic) tables, columns, FKs, indexes.
  - Type changes, nullability flips, default changes, comment changes.
- [ ] **Diff viewer** — three-pane: baseline / current / generated migration SQL.
- [ ] **Migration emitter** — dialect-aware `ALTER TABLE … ADD COLUMN`, `RENAME COLUMN`, `DROP CONSTRAINT`, `ALTER TYPE`, etc.
- [ ] **"Compare with live DB"** — diff current model against the parent app's connected DB.
- [ ] **"Apply migration"** — pipe the SQL to the parent app's query executor.

**Exit criteria:** rename a column, add an index, drop a FK → migration SQL applies cleanly to the live DB.

---

## Phase 4 — UX Polish (2–3 weeks of focused work)

- [ ] **Dark mode** — single `theme.py` with palette dict; replace hard-coded colours (`#FFF7ED`, `#5F6368`, `#1A73E8`, …) across all `paint()` methods. Light/dark/system toggle.
- [ ] **In-canvas column editing** — double-click a column row to edit name + type inline (currently only via property panel).
- [ ] **Drag-to-reorder columns** within a table.
- [ ] **Smart pan/zoom** — zoom toward cursor on `Ctrl+wheel`, middle-mouse pan, pinch on trackpad, fit-to-selection (`F`), reset zoom (`Ctrl+0`).
- [ ] **Minimap** — bottom-right overview, click/drag to navigate. Second `QGraphicsView` on the same scene at small scale.
- [ ] **Selection box** rubber-band over empty canvas (verify; likely already partial).
- [ ] **Multi-select operations** — group move (works), group resize, **align** (left/right/top/bottom/centre), **distribute** (horizontal/vertical).
- [ ] **Smart guides / snap** — alignment lines to neighbours when dragging (Figma-style).
- [ ] **Status bar** — "X tables, Y relationships, Z selected", current zoom %.
- [ ] **Empty-state onboarding** — first-launch help overlay pointing at the palette.
- [ ] **Keyboard shortcuts cheat-sheet** — `?` opens a modal.
- [ ] **Search → highlight + flash + select** instead of just dimming non-matches.

---

## Phase 5 — Performance (1–2 weeks)

Do *before* big-schema users hit it.

- [ ] **Viewport culling** — items outside `view.viewport()` skip `paint()` early.
- [ ] **Smart route cache** — `routing.py` already has `_router_cache`; verify correct invalidation, memoize `(source_id, target_id, side_hint, source_pos, target_pos)`.
- [ ] **Lazy column rendering** — `_visible_row_limit` already exists; extend to viewport-aware limits.
- [ ] **Batch route updates** — when N tables move during a multi-drag, recompute routes once on `mouseRelease`, not per `mouseMove`.
- [ ] **Profile** — `cProfile` a 200-table diagram pan; target 60 fps interaction.

**Exit criteria:** 200-table diagram pans at >30 fps on a mid-range laptop.

---

## Phase 6 — Differentiators (ongoing)

Things commercial tools don't do well that you uniquely could.

- [ ] **Chen ↔ crow's-foot conversion** — pick a Chen ER diagram, generate the relational implementation. Almost no tool does this.
- [ ] **Normalization analyzer** — flag 1NF / 2NF / 3NF / BCNF violations from FK + column metadata; suggest splits.
- [ ] **Anti-pattern lint** — warn on EAV, missing indexes on FKs, columns named `data` / `info` / `misc`, denormalized JSON-blob columns.
- [ ] **Sample data generation** — emit `INSERT`s respecting FKs with `Faker`. Pipes to the parent app's query executor.
- [ ] **Diagram-as-code export** — round-trip to DBML / PlantUML / Mermaid for git workflows.
- [ ] **AI-assisted documentation** — auto-generate column comments / table descriptions from naming conventions and FK relationships (optional, gated behind settings).

---

## Phase 7 — Collaboration & Cloud (optional, 4+ weeks)

Skip unless targeting teams.

- [ ] **Git-friendly serialisation** — stable key ordering, one item per line where possible (reviewable diffs).
- [ ] **Optional sync backend** — websocket-based CRDT (`y-py`) for multi-user editing.
- [ ] **Comments** — pin a comment thread to a table or relationship.
- [ ] **Share-as-image link** — opt-in upload to a self-hosted gallery.

---

## Cross-cutting tech debt

- [ ] **Reduce per-shape duplication** — `PortMixin` (Phase 0); also consider extracting common `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` skeletons.
- [ ] **Type hints** in `routing.py`, `commands.py`, `model.py`, then `mypy --strict` for `widgets/erd/`.
- [ ] **Logging** — replace stray `print` calls (if any) with `logging.getLogger(__name__)`.
- [ ] **Centralise icons** — one `widgets/erd/icons.py` instead of inline `qta.icon(...)` calls.
- [ ] **Constants** — move magic numbers (4 px drag threshold, 8 px handle, 12 px padding, 18 px crow-foot length, 22 px slot spacing, 50 px export margin, 16 K max-dim) into `constants.py` with names.
- [ ] **DDL function decomposition** — `generate_sql_script` is one ~160-line function in `widget.py`; move to its own `widgets/erd/ddl.py` and split per-dialect.

---

## Competitor parity map (where each phase lands you)

| Competitor                  | Today                                              | After Phase 1 | After Phase 2          | After Phase 3 | After Phase 4–5     |
| --------------------------- | -------------------------------------------------- | ------------- | ---------------------- | ------------- | ------------------- |
| **draw.io DB shapes**       | Roughly even                                       | Past          | Past                   | Past          | Past                |
| **pgAdmin ERD**             | Better in routing/Chen, behind in DDL coverage     | Even          | Past                   | Past          | Past                |
| **DBeaver ER Diagrams**     | Better in editing, behind in DDL                   | Even          | Past (live DB diff)    | Past          | Past                |
| **MySQL Workbench**         | Behind in DDL/diff                                 | Closer        | Closer                 | Even          | Past in editing UX  |
| **dbdiagram.io**            | Behind in polish, ahead in Chen                    | Closer        | Even (via DBML)        | Past          | Past                |
| **Lucidchart**              | Out of scope                                       | —             | —                      | —             | Closer with Phase 7 |
| **ER/Studio, ERwin**        | Out of scope (governance)                          | —             | —                      | —             | —                   |

---

## Suggested release cadence

- **0.x → 1.0** = Phase 0 + 1 (~3 weeks). Stabilise + MySQL/MSSQL DDL + indexes/comments. *"a real ERD editor with first-class DDL".*
- **1.x → 2.0** = Phase 2 + 4 (~5 weeks). SQL/DBML import + UX polish + dark mode. *"open any schema, edit it visually".*
- **2.x → 3.0** = Phase 3 + 5 (~4 weeks). Schema diff + perf. *"design, diff, deploy".*
- **3.x+** = Phase 6 differentiators.

---

## Open questions

1. Do we standardise on a single **typed model** (`@dataclass Table`) before Phase 1, or evolve from the existing `schema_data` dicts?
2. **MSSQL** priority — many shops still use it; worth bumping to Phase 1 vs deferring?
3. **`sqlglot` as the universal parser** for both forward (re-parse to validate) and reverse (Phase 2)?
4. Diagram **persistence format**: keep current JSON (versioned) or move to a more structured format (sqlite file with revisions)?
5. Should the parent app expose a single **`db_executor.execute(sql, params)`** API the ERD editor can rely on for "Apply migration" (Phase 3)?
