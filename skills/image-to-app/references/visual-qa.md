# Visual QA checklist

Compare the rendered app with the accepted images in matched states. Done when every line below is checked or named as a gap.

## Contract

- Required views exist and secondary chrome has not multiplied.
- Every departure from the images has an explicit Preserve, Reinterpret or Reject decision.
- Information hierarchy, whitespace, density, typography and component language are cohesive across views.
- Real content fits without clipping, accidental wrapping or hidden actions.
- Hover-only metadata has a keyboard-accessible equivalent.

## Interaction

- Primary pointer actions work.
- Keyboard navigation, shortcuts, Escape and focus return work.
- Focus indicators are visible in light and dark themes.
- Every specified interaction and persistence path behaves as specified.
- One surface owns each shortcut, and the web app claims no browser-reserved shortcut.

## States

- Populated, empty, loading, error, collapsed, selected and in-flight states are legible where relevant.
- A cold reload shows the expected persisted state, not only the state the test path created.
- Time-based UI updates without layout jitter.
- Live data refreshes keep focus, open overlays and scroll position.

## Viewports and themes

- Web app: the main desktop viewport and one narrow viewport, with deliberate overflow or reflow.
- Mobile app: the target device, including a cold launch of the installed build.
- Exactly one scroll owner per axis, with an obvious affordance when more content is available.
- System, light and dark themes when the product supports them.
- Reduced motion for non-essential animation.

## Evidence

- Label each claim with its rung on the ladder in `SKILL.md`.
- Capture screenshots after a cold load, from the canonical checkout, after confirming which process serves the port; a stale port or cached build reviews the wrong app.
- Exercise an empty state, one realistic long-content state, and a stale or disconnected data state where the app has one.
- Record exact viewport sizes and commands.
- Name each remaining difference as a contract gap, acceptable render variation or deferred integration work.
