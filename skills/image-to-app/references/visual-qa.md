# Visual QA checklist

Compare the rendered app with the accepted references in matched states.

## Contract

- Required views exist and secondary chrome has not multiplied.
- Information hierarchy, whitespace, density, typography, and component language are cohesive across views.
- Real content fits without clipping, accidental wrapping, or hidden actions.
- Hover-only metadata has a keyboard-accessible equivalent.

## Interaction

- Primary pointer actions work.
- Keyboard navigation, shortcuts, Escape behavior, and focus return work.
- Focus indicators are visible in light and dark themes.
- Quick capture, filters, grouping, detail surfaces, and persistence behave as specified.

## States

- Populated, empty, loading, error, folded/collapsed, selected, and in-flight states are legible where relevant.
- A cold reload shows the expected persisted state rather than the state created during the test path only.
- Time-based UI updates without layout jitter.

## Viewports and themes

- Main desktop viewport.
- One narrow viewport with deliberate overflow or reflow behavior.
- System, Light, and Dark theme behavior when the product supports them.
- Reduced-motion behavior for non-essential animation.

## Evidence

- Capture screenshots after a cold load.
- Record exact viewport sizes and commands.
- Name remaining differences as contract gaps, acceptable render variation, or deferred integration work.
