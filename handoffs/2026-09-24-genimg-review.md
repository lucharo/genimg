# GenIMG review handoff

## tldr

The visual review is preserved in this repository. Fix the installer data-loss issue first, then the four P2 findings. Read the [illustrated review and ticket index](../artifacts/reviews/2026-09-21-genimg-diagnosis/README.md). Keep the repository private; release PR #37, PyPI upload and docs deployment remain held pending explicit approval.

**Next action:** reproduce and fix [#5](https://github.com/lucharo/genimg/issues/5) in a fresh worktree.

<details>
<summary>Work remaining and acceptance checks</summary>

The live tracker owns status. Every ticket contains evidence and validation criteria; the committed [ticket snapshot](../artifacts/reviews/2026-09-21-genimg-diagnosis/tickets.md) preserves this handoff's contents offline.

| Priority | Work | Ticket |
| --- | --- | --- |
| P1 | Preserve user-owned skills; safely move towards `npx skills` | [#5](https://github.com/lucharo/genimg/issues/5) |
| P2 | Make skill recipes work from clean config | [#39](https://github.com/lucharo/genimg/issues/39) |
| P2 | Keep Studio Generate reachable | [#40](https://github.com/lucharo/genimg/issues/40) |
| P2 | Restore light-theme docs search contrast | [#41](https://github.com/lucharo/genimg/issues/41) |
| P2 | Correct README/docs automation promises | [#42](https://github.com/lucharo/genimg/issues/42) |
| P3 | Review first-use hierarchy visually | [#43](https://github.com/lucharo/genimg/issues/43) |
| P3 | Decide licence and add package links | [#44](https://github.com/lucharo/genimg/issues/44) |

[#2](https://github.com/lucharo/genimg/issues/2) remains the release tracker. The P3 first-use item is design polish, not a release blocker. Licence selection is a maintainer decision before publication. The existing hosted Studio proposal #3 and workflow-skills proposal #23 remain separate work.

The user proposed `npx skills`. Skills CLI 1.7.0 installed all four skills and their 58 files into a disposable project for Codex, Claude Code and Cursor; contents matched. This establishes fresh-install completeness only. Test collisions, existing symlinks, update and removal before migrating. Do not delete unknown directories.

</details>

<details>
<summary>What is complete, and what was actually verified</summary>

The unfinished Max session, “genimg and audit release prep”, was recovered and read with three transcript readers, covering 2,464 main records and 269 records from its three subagents. Source snapshots were structurally inspected, not independently audited byte by byte. A session ending did not mean its launch objective was complete.

Documentation corrections [PR #38](https://github.com/lucharo/genimg/pull/38) were merged. PyPI pending-publisher configuration was saved and read back on 20 September; this is configuration, not publication. That same baseline passed 321 tests with two skips, lint, strict docs build, wheel/sdist checks, and isolated installs including OpenAI 3.16.2. Requalify the final candidate before release.

The [product review](../artifacts/reviews/2026-09-21-genimg-diagnosis/evidence/2026-09-20-product-review.md) and [visual QA](../artifacts/reviews/2026-09-21-genimg-diagnosis/QA.md) record the actual probes and their limits. The six generated diagrams explain the diagnosis; the screenshots and CLI results are evidence. Findings remain **diagnosed, not fixed**.

No paid product generation was performed. Exact-model serving, real Studio generation/retry, native clipboard image formats, terminal graphics, physical iPad/Pencil interaction and public PyPI installation remain unverified. A source-level concern about Retry using current state was not reproduced and is not a confirmed defect.

</details>

<details>
<summary>Release and checkout boundaries</summary>

The user's instruction “not the public toggle just yet” remains active. Do not change visibility, merge [release PR #37](https://github.com/lucharo/genimg/pull/37), tag a release, upload to PyPI or dispatch `release.yml`. Its manual dispatch merges the release proposal and publishes; it is not a harmless test. A PyPI source distribution would expose code even while GitHub stays private. Obtain explicit publication scope before doing any of these.

The original review baseline is `a9fb22778936b3b27c7a7ea7fca84781c95b4150`, tree-equivalent to takeover commit `19d76c98167e4efc97332d3df53d17fcd07fe927`. This handoff contains documentation and review artifacts only. The canonical checkout was dirty and divergent on 24 September and was preserved. Fetch current remote state and use a fresh worktree; do not reset, stash or overwrite the canonical checkout to resume.

The portable bundle contains the self-contained HTML, six selected illustrations, three superseded renders labelled as such, four screenshots, prompts, evidence and checksums. It needs no prior host, service, session transcript or local home path. Original local artifacts and their private viewing service were retained as an additional copy.

</details>

<details>
<summary>Suggested skills</summary>

- `worktree-pr-mechanics`: isolate changes and preserve the dirty canonical checkout.
- `testing-conventions`: load before adding regression tests; use real disposable skill roots for #5.
- `skills-management`: use the shared installer and verify every requested adapter and companion file.
- `visual-review` and `visual-exploration`: diagnose with evidence; show lettered options before layout changes.
- `zensical-docs-site`: render and validate the docs corrections.
- `uv-python-package-release`: qualify the exact release candidate after approval.
- `wrapup`: land finished fixes and reconcile their tickets; retain the publication hold.

</details>

---

24 September 2026, Europe/London. This is a handoff of open work, not a release approval.
