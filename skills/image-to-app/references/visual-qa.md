# Visual QA checklist

Compare the rendered app with the accepted references in matched states.

## Contract

- Required views exist and secondary chrome has not multiplied.
- Every reference departure has an explicit Preserve, Reinterpret, or Reject decision.
- Information hierarchy, whitespace, density, typography, and component language are cohesive across views.
- Real content fits without clipping, accidental wrapping, or hidden actions.
- Hover-only metadata has a keyboard-accessible equivalent.

## Interaction

- Primary pointer actions work.
- Keyboard navigation, shortcuts, Escape behavior, and focus return work.
- Focus indicators are visible in light and dark themes.
- Quick capture, filters, grouping, detail surfaces, and persistence behave as specified.
- One surface owns each shortcut; browser-reserved shortcuts are not claimed as web behavior.

## States

- Populated, empty, loading, error, folded/collapsed, selected, and in-flight states are legible where relevant.
- A cold reload shows the expected persisted state rather than the state created during the test path only.
- Time-based UI updates without layout jitter.
- Live dashboards preserve focus, overlay state, and scroll position while data refreshes.
- Lifecycle, workflow stage, attention, hierarchy, and grouping are verified independently.

## Viewports and themes

- Web app: the main desktop viewport and one narrow viewport with deliberate overflow or reflow behavior.
- Mobile app: the target device, including a cold launch of the installed build.
- Exactly one scroll owner per axis, with an obvious affordance when more content is available.
- System, Light, and Dark theme behavior when the product supports them.
- Reduced-motion behavior for non-essential animation.

## Evidence

- Mark evidence as visual direction, fixture-backed prototype, live-source integration, or installed runtime.
- Capture screenshots after a cold load.
- Exercise a fresh connected state, stale/incompatible protocol state, empty state, and one realistic long-content state when applicable.
- Verify the canonical checkout and identify the serving PID/process before capture; do not review a stale port or cached build.
- Record exact viewport sizes and commands.
- Name remaining differences as contract gaps, acceptable render variation, or deferred integration work.
