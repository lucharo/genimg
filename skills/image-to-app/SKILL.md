---
name: image-to-app
description: "Turn generated mockups, wireframes, screenshots, or selected visual directions into a working and visually verified application. Use for image-to-web or image-to-app tasks, design-direction exploration before implementation, multi-view UI systems generated with genimg, implementation handoffs to frontend specialists, and visual-parity QA against reference images."
---

# Image to app

Treat images as design evidence, not as an executable specification. Preserve the selected visual language while resolving accessibility, interaction, responsive layout, real data, and application-state details in code.

## Workflow

### 1. Freeze the product contract

Before generating or coding, record:

- The user outcome and non-goals.
- Required views, states, actions, data, keyboard behavior, and persistence.
- The exact reference-image paths and what each reference contributes.
- Constraints that must survive visual exploration, such as tab count, density, theme, or platform feel.

Keep product behavior constant across visual variants. Do not compare design systems that quietly change the information architecture.

### 2. Generate coherent directions

Load the `genimg` skill before using the CLI. Verify the live CLI and model catalog rather than relying on remembered aliases. For text-heavy UI, start with the current GPT Image model intended for reliable typography; use a structurally stronger model when spatial layout matters more.

Generate one coherent design system at a time. If the app has several important views, produce the same fixed view set for every direction. Use stable IDs and filenames, for example `quiet-ledger-01-kanban.png` and `quiet-ledger-02-ideas.png`.

Use `--diverse` or tailored `--deltas` to explore genuinely different systems. Do not ask one image to contain a contact sheet. Retain prompts, model, quality, references, and original index.

### 3. Review and choose

Inspect every candidate at full resolution. Build one `genimg grid` containing the comparable set and use its carousel for human review. Evaluate hierarchy, density, navigation, state clarity, interaction discoverability, and cross-view consistency, not only atmosphere.

When the strongest answer combines directions, write the synthesis explicitly: base shell, component language, typography, spacing, and interaction model. Never tell an implementation agent to “mix A and B” without naming which parts come from each.

If a visual specialist is available, pass absolute image paths or screenshots. For code-design work, also pass the app/repo path and ask the specialist to inspect the rendered result, not only source code.

### 4. Record answered decisions

Write concise accepted decision records before implementation. Phrase the design grill as answered questions so later agents can see both the decision and the pressure behind it. Use [decision-record.md](references/decision-record.md).

Record at least:

- Chosen design system and rejected alternatives.
- Navigation and view count.
- Data ownership and persistence boundaries.
- Responsive and theme behavior.
- Integration contract and deliberate deferrals.

### 5. Hand off implementation precisely

Use an isolated branch or worktree for substantial builds. Give the implementer the fixed product contract, exact reference paths, accepted decision records, expected interactions, test commands, and visual-QA requirements. Use [implementation-handoff.md](references/implementation-handoff.md).

Ask for a working app, not a static screenshot recreation. Require realistic states and interactions. Make fixture-backed boundaries explicit when the real integration is intentionally deferred.

### 6. Verify the real app

Run functional checks, then browser QA at the main desktop viewport and at least one narrow viewport. Capture the implemented app in the same states as the references and compare them side by side. Use [visual-qa.md](references/visual-qa.md).

Verify cold reload after changing persisted state. Exercise keyboard navigation, focus visibility, overflow, empty/loading/error states, theme switching, and reduced motion where relevant. A passing build does not prove the visual or interaction contract.

### 7. Iterate with bounded loops

Fix the largest contract mismatch first. Re-render and compare after each meaningful change. Stop after two or three review rounds unless a remaining issue blocks the accepted contract; otherwise review churn starts redesigning the app.

Preserve generated directions, selection rationale, decision records, final screenshots, and verification commands as durable project evidence. Mark superseded artifacts; do not delete the decision trail.

## Completion criteria

Finish only when:

- The selected visual direction and product contract are named precisely.
- Required interactions work with realistic state.
- The app has been visually inspected at desktop and narrow sizes.
- Persisted state survives a cold reload.
- Tests and checks have positive, read evidence.
- The integration boundary and any fixture-backed portion are stated honestly.
