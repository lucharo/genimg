# Review tickets at handoff

24 September 2026, Europe/London. Live GitHub issues own current status. This snapshot preserves the agreed scope and acceptance checks. All seven findings remain open.

<details>
<summary>#5: [P1] Preserve user-owned skills and adopt the shared skills installer</summary>

[[P1] Preserve user-owned skills and adopt the shared skills installer](https://github.com/lucharo/genimg/issues/5)

## What

Prevent `skills update`, `skills uninstall` and `skills install --force` from deleting directories or foreign links owned by the user. Move the supported installation path towards `npx skills` instead of maintaining another installer.

## Why

A disposable same-named `genimg/` directory containing `user-authored.md` survived normal install, but update and uninstall deleted it; both exited 0. Install itself recommends the unsafe update command. The existing ticket also identified brittle links into package virtual environments.

## How

Preserve unknown directories and links. Replace/unlink only demonstrably GenIMG-owned entries; give an actionable collision message. Before retiring the old installer, provide a safe migration for its recognised symlinks and update installation docs/skills. The user's preferred direction is `npx skills add lucharo/genimg` (repository access required while private); do not build the older proposed custom embedded-file installer.

## Validation

- Regression checks for normal install, force, update and uninstall with a user directory, foreign symlink, recognised symlink and missing target; user sentinel bytes must survive.
- Fresh install plus migration/update/uninstall in disposable project roots for supported agents. Verify all companion files, not only `SKILL.md`.
- Skills CLI 1.7.0 already installed four skills for Codex, Claude Code and Cursor in a fresh fixture; all 58 files matched. This does **not** prove collision or migration safety. No global skills were changed.

## References

`src/genimg/cli.py` around update/uninstall; `probe-results.json` and `skills-install-manifest.json` in the review bundle. Supersedes this ticket's earlier custom-copy implementation proposal, retaining its upgrade/reliability objective.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

<details>
<summary>#39: [P2] Make bundled generation recipes work from a clean configuration</summary>

[[P2] Make bundled generation recipes work from a clean configuration](https://github.com/lucharo/genimg/issues/39)

## What

Correct the main skill's OpenAI 16:9 example and the refinement skill/docs examples so they work without a saved default model.

## Why

The portfolio recipe fails before generation at implicit 1K; adding `-r 2K` passes dry-run validation. Refinement's initial and retry commands omit `-m`, despite the deliberate absence of a built-in default; the initial command fails with “no model specified”.

## How

Use a supported aspect/resolution pair and an explicit model in standalone recipes. Label saved-default shortcuts. Sweep README/docs and bundled copies for the same examples.

## Validation

Run the changed examples in disposable clean config roots with `--dry-run`, assert success and resolved model/size, and retain a negative control for the prior recipe. No paid generation is needed for this contract.

## References

`skills/genimg/SKILL.md:141`, `skills/genimg-agent-refinement/SKILL.md:20,27`, `docs/skills/genimg-agent-refinement.md`.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

<details>
<summary>#40: [P2] Keep Draw Studio Generate reachable when the prompt expands</summary>

[[P2] Keep Draw Studio Generate reachable when the prompt expands](https://github.com/lucharo/genimg/issues/40)

## What

Make Generate reachable with a source image and expanded prompt at smaller desktop/tablet-sized browser viewports.

## Why

At 1024×769 CSS pixels, Generate occupied y=789–835 and scrolling could not reveal it. Collapsing the prompt restored y=704–750. A later 1023×768 capture wrapped more controls and reproduced the obstruction.

## How

Let the central card shrink or scroll while keeping the main action reachable. Inspect the viewport-height, `overflow:hidden` body and 340px canvas minimum together; keep this correction bounded.

## Validation

Cold-load with a source image at 1024×769 and 1280×800; expand/collapse prompt and verify visible, clickable Generate plus usable canvas and scrolling. Include narrow wrapping behaviour. Physical iPad/Pencil and real generation remain separately unverified.

## References

`src/genimg/draw.py:547,652`; `shots/studio-expanded.png` and surface probe results.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

<details>
<summary>#41: [P2] Restore docs search contrast in the light theme</summary>

[[P2] Restore docs search contrast in the light theme](https://github.com/lucharo/genimg/issues/41)

## What

Give the docs search trigger readable text/icon and visible hover/focus states against the persistent charcoal header.

## Why

In light mode its computed text was `rgba(0,0,0,0.87)` over a translucent black control on `rgb(28,25,23)`. The screenshot confirms the problem. Search itself returned nine “profiles” results.

## How

Extend the header theme to the search trigger and its icon, including keyboard focus and hover. Preserve the existing light/dark theme behaviour.

## Validation

Render light and dark modes, inspect actual contrast and focus visibility, and perform a real search in both modes. Keep before/after captures at the same crop.

## References

`docs/stylesheets/extra.css:30`; `shots/docs-light.png` and surface probe results.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

<details>
<summary>#42: [P2] Align README and automation docs with the actual CLI contract</summary>

[[P2] Align README and automation docs with the actual CLI contract](https://github.com/lucharo/genimg/issues/42)

## What

Correct four promises in the README, CLI reference, agent guide and grid docs.

## Why

- “Every verb” has `--json` is false: `genimg skills list --json` exits 2.
- Exit 2 does not prove a provider request was sent: an unknown option exits 2 while parsing, even with `--dry-run`.
- Human output can abbreviate home paths as `~`; it does not always print absolute paths.
- `#carousel-2` does not restore the gallery selection; `?view=carousel&i=2` does survive reload.

## How

Document current behaviour accurately rather than adding JSON to every command or changing routing for this release. Keep machine JSON and human display contracts distinct.

## Validation

Exercise every corrected example, parser negative control and carousel cold reload; build docs strictly and check relative links. Do not infer request billing or delivery from an exit code alone.

## References

`README.md:28`, `docs/reference/cli.md:66`, `docs/agents.md:41`, `docs/surfaces/grid.md:27`.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

<details>
<summary>#43: [P3] Review first-use hierarchy in the docs and Draw Studio</summary>

[[P3] Review first-use hierarchy in the docs and Draw Studio](https://github.com/lucharo/genimg/issues/43)

## What

Visually compare small improvements to the install → setup → one image → compare → iterate path, then implement the chosen layout.

## Why

The docs mix onboarding and maintainer navigation in a busy tree. Studio gives substantial space to an empty Generated panel while the editable prompt is collapsed. These are design trade-offs, not confirmed functional defects or release blockers.

## How

Present lettered visual options before changing layout. Keep real product captures beside proposed explanations. Use the current local Studio; the separate hosted Studio proposal #3 is not a prerequisite. Related workflow-skills proposal: #23.

## Validation

Obtain a concrete layout choice, then verify the first-use path in rendered docs/Studio at desktop and narrow widths. Preserve access to maintainer docs and the prompt; do not add new hosted infrastructure.

## References

README/docs pages and product/UX assessment in the review bundle.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

<details>
<summary>#44: [P3] Decide package licence and add PyPI project links before publication</summary>

[[P3] Decide package licence and add PyPI project links before publication](https://github.com/lucharo/genimg/issues/44)

## What

Choose the intended package licence and add source/documentation links to package metadata before the public release.

## Why

`pyproject.toml` has no project URLs or package licence declaration, and no root licence file was present. The adapted infographic skill has its own licence, which does not establish the intended licence for the whole package.

## How

Get the maintainer's explicit licence choice; do not invent one. Add the corresponding root declaration/metadata and preserve third-party notices. Add source and documentation URLs, ensuring public docs exist before advertising them as live.

## Validation

Build wheel/sdist, inspect metadata and licence/notice inclusion, run metadata validation, and check the destination URLs at release time. This ticket does not authorise a visibility change or publication.

## References

`pyproject.toml`; release tracker #2. Licence selection remains a maintainer decision.
[Visual review bundle](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/README.md) · [Full evidence](https://github.com/lucharo/genimg/blob/main/artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md). Audited baseline: `a9fb227`. Findings are diagnosed, not fixed. Publication remains held.


</details>

Release coordination: [#2](https://github.com/lucharo/genimg/issues/2). Publication held; release PR #37 stays open.
