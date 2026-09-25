# Implementation handoff

Give an implementation agent this evidence packet:

1. Outcome and non-goals.
2. Exact product contract: views, states, interactions, keyboard behavior, persistence, and responsive behavior.
3. State ownership matrix: authoritative source, derived UI, and human-owned data; entity lifecycle, stage, attention, hierarchy, and grouping.
4. Canonical repository/worktree, running-process owner, target delivery surface, endpoint/port, and which layer owns each shortcut.
5. Absolute paths to selected images and a one-line role for each image.
6. Accepted synthesis, for example “shell from A; cards and capture language from B”.
7. Accepted ADRs and `CONTEXT.md`, including the Preserve/Reinterpret/Reject label for each reference departure.
8. Existing repo instructions, stack, commands, and worktree boundary.
9. Real integration contract or typed fixture-backed substitute, plus fixture isolation and retirement plan.
10. Required evidence tier and the positive control for reaching it.
11. Functional tests and visual-QA viewports/states.
12. Required completion report: commit, checks, screenshots, installed-runtime evidence where applicable, and honest deferrals.

For a visual specialist or image-to-web model, explicitly allow image inspection. Pass screenshot paths directly. If code already exists, pass the repo path and require rendered-browser inspection before edits.

Reject these vague handoffs:

- “Make it like this image.”
- “Mix these two designs.”
- “Polish the UI.”
- “Use the screenshot as the spec.”

Replace them with named component, layout, behavior, and evidence responsibilities.
