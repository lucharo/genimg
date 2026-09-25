# Implementation handoff

Give an implementation agent this evidence packet:

1. Outcome and non-goals.
2. Exact product contract: views, states, interactions, keyboard behaviour, persistence and responsive behaviour.
3. State ownership: which source is authoritative, what the UI derives, and which data the user owns.
4. Where to work: repository and branch, existing repo instructions, stack and commands, the delivery surface (browser, desktop, device) and its local URL or port, and which layer owns each keyboard shortcut.
5. Absolute paths to the accepted images, with a one-line role for each.
6. The accepted synthesis, for example "shell from A; cards and capture language from B".
7. The ADRs and `CONTEXT.md`, including the Preserve, Reinterpret or Reject label for each departure from the images.
8. The real integration contract, or a typed fixture-backed substitute with its isolation and retirement plan.
9. The evidence rung required and the positive control that proves it was reached.
10. Functional tests, and the viewports and states for visual QA.
11. The completion report expected: commit, checks, screenshots, installed-runtime evidence where it applies, and honest deferrals.

For a visual specialist or image-to-web model, allow image inspection explicitly and pass screenshot paths directly. If code already exists, pass the repo path and require a look at the rendered page before any edit.

Write every responsibility as a named component, layout, behaviour or piece of evidence. A handoff such as "make it like this image", "mix these two designs", "polish the UI" or "use the screenshot as the spec" leaves the implementer guessing.
