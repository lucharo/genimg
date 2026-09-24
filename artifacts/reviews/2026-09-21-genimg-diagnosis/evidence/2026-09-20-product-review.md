# GenIMG release candidate review

## tldr

Hold release for the skill installer’s data-loss bug. Fix two broken skill recipes, Studio’s clipped Generate button, light-mode search contrast, and inaccurate automation documentation before launch. The package and main workflows are broadly in place. Publication remains on hold; this review makes no product changes.

**Recommended next action:** fix the reproduced defects below as one bounded release-preparation change.

<details>
<summary>Five findings, with evidence and smallest fixes</summary>

### 1. P1 — Updating or uninstalling skills can delete user-owned files

Both commands recursively remove a same-named directory without checking that GenIMG owns it. Normal install preserves a collision but explicitly recommends `skills update`, which then destroys it. The default target is all supported agents, so the scope can be wider than one folder.

Reproduced with the real CLI and disposable skill roots, each containing `genimg/user-authored.md`: install preserved the file; update deleted it and created a symlink; uninstall deleted it. All three commands exited zero. No actual installed skills were touched.

**Fix:** replace or unlink only a recognised GenIMG-owned symlink. Preserve directories and foreign links, with an actionable collision message. `install --force` uses the same deletion pattern and belongs in this correction.

Source: [update](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/src/genimg/cli.py#L957), [uninstall](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/src/genimg/cli.py#L975).

### 2. P2 — Two bundled recipes fail from a clean configuration

The main skill’s OpenAI portfolio example requests 16:9 without `-r 2K`. It exits 1 before generation because the implicit 1K size is unsupported; adding 2K passed the same dry-run validation. The refinement skill’s initial and retry examples omit `-m`, despite there deliberately being no built-in default. Its initial command exits 1 with “no model specified” on a clean configuration. The refinement docs repeat it.

**Fix:** make every standalone recipe explicit about its model and use a supported aspect/resolution pair. Keep saved-default shortcuts labelled as such.

Source: [portfolio recipe](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/skills/genimg/SKILL.md#L141), [refinement recipes](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/skills/genimg-agent-refinement/SKILL.md#L20).

### 3. P2 — Opening the prompt can hide Studio’s Generate button

At a measured 1024 × 769 CSS viewport, with a source image inserted and the prompt expanded, Generate occupied y=789–835, below the visible area. A downward scroll did not bring it into view. Collapsing the prompt restored the button to y=704–750. The 340px canvas minimum and a non-scrolling, viewport-height body compete with the toolbar and expanded prompt.

**Fix:** allow the central card to shrink or scroll while keeping the main action reachable. Check both prompt states at this size and at 1280 × 800. This is a browser-window defect; no claim is made about physical iPad or Pencil behaviour.

Source: [body overflow](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/src/genimg/draw.py#L547), [canvas minimum](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/src/genimg/draw.py#L652).

### 4. P2 — Docs search is almost invisible in light mode

The header remains charcoal in light mode, but its Search button renders black text: computed text `rgba(0,0,0,0.87)` over a translucent black button on `rgb(28,25,23)`. The rendered screenshot confirms the poor contrast. Search itself worked and returned nine results for “profiles”.

**Fix:** explicitly theme the search trigger and its icon for the persistent dark header, including focus and hover. The existing header text override does not reach this control.

Source: [header overrides](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/docs/stylesheets/extra.css#L30).

### 5. P2/P3 — The documented automation contract overpromises

- README says every verb has `--json`; `genimg skills list --json` exits 2 because it does not. Describe the specific commands that offer JSON.
- CLI docs say exit 2 means generation failed after sending a request. An unknown option also exits 2 during parsing, even with `--dry-run`. Agents cannot infer whether a request was sent from that code alone.
- The agent guide promises printed absolute paths; the tested dry-run abbreviates the home directory as `~`. Distinguish human-readable output from JSON history paths.
- Grid docs promise `#carousel-2`. Opening that link returned the grid and removed the hash. The actual `?view=carousel&i=2` link restored image 2 after reload.

**Fix:** align the documentation with the existing behaviour; there is no need to add JSON to every command or change grid routing for this release.

Sources: [README](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/README.md#L28), [exit codes](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/docs/reference/cli.md#L66), [paths](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/docs/agents.md#L41), [grid links](https://github.com/lucharo/genimg/blob/a9fb22778936b3b27c7a7ea7fca84781c95b4150/docs/surfaces/grid.md#L27).

</details>

<details>
<summary>Product and UX assessment</summary>

The strongest first-use path is **install → setup → one image → compare → iterate**. Keep it prominent. The CLI, four skills, gallery, history and canvas are useful parts of that path; they do not need a new hosted product to be releasable.

Studio’s source insertion, prompt editing and provider-specific controls worked in the browser. The prompt survived a model switch. Its initial screen gives substantial space to an empty Generated panel while the editable prompt is collapsed. That is a design trade-off worth reviewing after the layout defect, not a release blocker or authority to redesign it.

The grid is direct and useful: stable candidate numbers, carousel navigation, reloadable query state and winner text. Copy Text returned `I choose #2 (fox-2.webp)` on readback. The history fixture showed all four outputs and updated the selected image and details with `j`; its portable preview is coarse but usable. Native terminal graphics were not tested here.

The docs use real GenIMG output and have a coherent warm visual style. Search works and a measured 582px-wide layout had no horizontal document overflow. User onboarding and maintainer material share a busy navigation tree; reducing first-use choices would be polish, not missing functionality.

The specialist skills provide meaningful workflows: infographic layout/style references, a bounded refinement loop, and an image-to-app decision/handoff process. Their availability in the built package was verified earlier. This pass checked their instruction contracts and 64 relative Markdown links across docs and skills, all of which resolved; it did not audit every style paragraph or execute paid workflows.

Package metadata omits project URLs and a root package licence declaration; only the adapted infographic skill has its own licence. Decide the package’s intended licence before public release, and add PyPI source/docs links. This is a maintainer decision, not something the review silently chooses.

</details>

<details>
<summary>Coverage, limits and evidence</summary>

Reviewed the CLI/package interface, all four skill entry points, primary onboarding/reference/surface docs, rendered docs in light and dark modes, Draw Studio, a grid built from existing real docs images, and a history render using explicitly labelled fixture metadata.

Earlier validation on the same runtime tree passed: 321 tests, 2 skips, lint, strict docs build, wheel/sdist checks and clean installation smoke tests. This review adds real CLI failure reproductions and browser checks; it does not repeat those broad tests.

No paid generation ran in this review. Exact-model serving, a real end-to-end Studio generation/retry, native clipboard image formats, physical iPad/Pencil interaction and a public PyPI install remain outside its verified coverage. A source-level concern about Retry using current canvas/prompt state has not been reproduced and is not counted among the confirmed findings.

The repository stays private. PR #37 remains the unreleased 0.1.0 release proposal. No upload, release merge, visibility change or new deployment was performed for this review.

Evidence: [CLI probe results](probe-results.json), [surface probe results](surface-probe-results.json), [history fixture render](history-review-fixture.svg). Browser screenshots and measured bounds are retained in the task transcript.

</details>

---
Reviewed 20 September 2026, Europe/London. Status: review complete; findings open. Repository: lucharo/genimg. Baseline: main `a9fb22778936b3b27c7a7ea7fca84781c95b4150`, same tree as local `19d76c98167e4efc97332d3df53d17fcd07fe927`. Session: `01a0bff9-c3b0-79d2-971e-fb5c41ff7b07`. File: `LOCAL_HOME/.codex/session-artifacts/2026-09-20-genimg-takeover-01a0bff9/2026-09-20-product-review.md`.
