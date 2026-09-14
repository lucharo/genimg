# image-to-app

Take generated mockups, wireframes, screenshots or a chosen visual direction to a working,
visually verified application. Images are treated as design evidence, not as an executable
specification: the selected visual language is preserved while accessibility, interaction,
responsive layout, real data and application state are resolved in code.

## The staged workflow

1. Freeze the product contract. Outcome and non-goals, the views and states the app must
   have, what data is authoritative versus derived, the delivery surface, the reference images
   and what each contributes. Behaviour stays constant across visual variants.
2. Generate coherent directions. One design system at a time, the same fixed view set
   per direction, stable filenames (`quiet-ledger-01-kanban.png`), `--diverse` or tailored
   `--deltas` for genuinely different systems. Prompts, model, quality and references are
   retained.
3. Review and choose. Every candidate at full resolution in one `genimg grid`; each
   departure from the contract labelled Preserve, Reinterpret or Reject; a synthesis written
   out explicitly when the answer combines directions.
4. Record answered decisions. Chosen system and rejected alternatives, navigation, data
   ownership, responsive and theme behaviour, integration contract.
5. Hand off implementation precisely and **verify visual parity** in a browser against
   the reference images, with the evidence ladder from visual direction to fixture-backed
   prototype to live integration to installed runtime.

The skill carries three references an agent fills in along the way: a decision record, an
implementation handoff and a visual-QA checklist.

Read the skill: [skills/image-to-app/SKILL.md](https://github.com/lucharo/genimg/blob/main/skills/image-to-app/SKILL.md).
